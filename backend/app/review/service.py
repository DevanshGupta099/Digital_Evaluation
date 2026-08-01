from typing import List, Dict
import logging
import difflib
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException

from app.database.models import (
    AnswerScript, AnswerScriptStatus, EvaluationRun, RunType,
    ReviewFlag, FlagType, FlagStatus, Student, SegmentationRun, RubricItem
)
from app.review.schemas import (
    ReviewFlagResponse, ScriptDetailResponse, QuestionEvaluationResponse, 
    ModelPassResponse, PointEvaluationSchema, OverrideDetail, OverrideSubmitRequest
)

logger = logging.getLogger(__name__)

async def compute_script_status(db: AsyncSession, answer_script_id: str) -> AnswerScriptStatus:
    """
    Checks if there are any open ReviewFlags for this script.
    If yes -> provisional
    If no (and flags exist or grading is done) -> final
    """
    script = await db.get(AnswerScript, answer_script_id)
    if not script:
        raise HTTPException(status_code=404, detail="Answer script not found")
        
    flags_res = await db.execute(
        select(ReviewFlag).where(ReviewFlag.answer_script_id == answer_script_id)
    )
    flags = flags_res.scalars().all()
    
    # Check if any open flags
    has_open = any(f.status == FlagStatus.open for f in flags)
    
    # If the script hasn't been graded at all, we shouldn't bump it to final
    # But for MVP, if it was graded or provisional, we decide based on flags.
    if has_open:
        new_status = AnswerScriptStatus.provisional
    else:
        new_status = AnswerScriptStatus.final
        
    script.status = new_status
    await db.commit()
    return new_status

async def reconcile_evaluations(db: AsyncSession, answer_script_id: str):
    """
    Compares ai_pass_1 and ai_pass_2 for the script.
    Creates high_variance flags if difference >= 1.0.
    Calculates initial totals.
    """
    eval_res = await db.execute(
        select(EvaluationRun)
        .where(EvaluationRun.answer_script_id == answer_script_id)
    )
    eval_runs = eval_res.scalars().all()
    
    script = await db.get(AnswerScript, answer_script_id)
    if not script:
        return
    
    # Group by question_number + subpart_id
    grouped: Dict[str, Dict[str, EvaluationRun]] = {}
    for run in eval_runs:
        key = f"{run.question_number}_{run.subpart_id}" if run.subpart_id else run.question_number
        if key not in grouped:
            grouped[key] = {}
        grouped[key][run.run_type.value] = run
        
    # Threshold
    VARIANCE_THRESHOLD = 1.0
    
    flags_to_add = []
    
    for key, runs in grouped.items():
        pass1 = runs.get(RunType.ai_pass_1.value)
        pass2 = runs.get(RunType.ai_pass_2.value)
        
        if pass1 and pass2:
            diff = abs(float(pass1.marks_awarded) - float(pass2.marks_awarded))
            if diff >= VARIANCE_THRESHOLD:
                # Check if flag already exists
                existing = await db.execute(
                    select(ReviewFlag)
                    .where(ReviewFlag.answer_script_id == answer_script_id)
                    .where(ReviewFlag.question_number == pass1.question_number)
                    .where(ReviewFlag.subpart_id == pass1.subpart_id)
                    .where(ReviewFlag.flag_type == FlagType.high_variance)
                    .where(ReviewFlag.status == FlagStatus.open)
                )
                if not existing.scalars().first():
                    flag = ReviewFlag(
                        answer_script_id=answer_script_id,
                        question_number=pass1.question_number,
                        subpart_id=pass1.subpart_id,
                        flag_type=FlagType.high_variance,
                        notes=f"AI Pass 1 awarded {pass1.marks_awarded}, AI Pass 2 awarded {pass2.marks_awarded}"
                    )
                    flags_to_add.append(flag)
                    
        # --- Similarity Check ---
        if pass1 and pass1.evidence_quote and len(pass1.evidence_quote) > 20:
            # Fetch peers
            stmt = (
                select(EvaluationRun)
                .join(AnswerScript)
                .where(AnswerScript.class_offering_id == script.class_offering_id)
                .where(EvaluationRun.answer_script_id != answer_script_id)
                .where(EvaluationRun.question_number == pass1.question_number)
                .where(EvaluationRun.run_type == RunType.ai_pass_1)
            )
            if pass1.subpart_id:
                stmt = stmt.where(EvaluationRun.subpart_id == pass1.subpart_id)
                
            peer_res = await db.execute(stmt)
            peers = peer_res.scalars().all()
            
            for peer in peers:
                if peer.evidence_quote and len(peer.evidence_quote) > 20:
                    ratio = difflib.SequenceMatcher(None, pass1.evidence_quote, peer.evidence_quote).ratio()
                    if ratio > 0.85:
                        existing_sim = await db.execute(
                            select(ReviewFlag)
                            .where(ReviewFlag.answer_script_id == answer_script_id)
                            .where(ReviewFlag.question_number == pass1.question_number)
                            .where(ReviewFlag.subpart_id == pass1.subpart_id)
                            .where(ReviewFlag.flag_type == FlagType.suspicious_similarity)
                            .where(ReviewFlag.status == FlagStatus.open)
                        )
                        if not existing_sim.scalars().first():
                            flag = ReviewFlag(
                                answer_script_id=answer_script_id,
                                question_number=pass1.question_number,
                                subpart_id=pass1.subpart_id,
                                flag_type=FlagType.suspicious_similarity,
                                notes=f"High similarity ({ratio:.2f}) with script {peer.answer_script_id[-4:]}"
                            )
                            flags_to_add.append(flag)
                        break # Only flag once per question per script if any peer is similar
                    
    if flags_to_add:
        db.add_all(flags_to_add)
        await db.commit()
        
    # Recompute script status
    await compute_script_status(db, answer_script_id)

async def get_review_queue(db: AsyncSession, class_offering_id: str) -> List[ReviewFlagResponse]:
    """
    Fetches all OPEN flags for a class offering, sorted by priority.
    Priority 1: possible_wrong_upload, high_variance
    Priority 2: uncertain_segmentation, unmatched_annotation, rubric_addendum_recheck
    Priority 3: orphaned_content, low_ocr_confidence
    """
    # Join with AnswerScript to filter by class_offering_id
    stmt = (
        select(ReviewFlag)
        .join(AnswerScript)
        .where(AnswerScript.class_offering_id == class_offering_id)
        .where(ReviewFlag.status == FlagStatus.open)
    )
    res = await db.execute(stmt)
    flags = res.scalars().all()
    
    results = []
    for f in flags:
        # Determine tier
        tier = 3
        if f.flag_type in [FlagType.possible_wrong_upload, FlagType.high_variance]:
            tier = 1
        elif f.flag_type in [FlagType.uncertain_segmentation, FlagType.unmatched_annotation, FlagType.rubric_addendum_recheck, FlagType.suspicious_similarity]:
            tier = 2
            
        results.append(ReviewFlagResponse(
            id=f.id,
            answer_script_id=f.answer_script_id,
            question_number=f.question_number,
            subpart_id=f.subpart_id,
            flag_type=f.flag_type.value,
            status=f.status.value,
            notes=f.notes,
            priority_tier=tier
        ))
        
    # Sort by tier ascending
    results.sort(key=lambda x: x.priority_tier)
    return results

async def resolve_flag(db: AsyncSession, flag_id: str, resolver_name: str, notes: str = None) -> AnswerScriptStatus:
    flag = await db.get(ReviewFlag, flag_id)
    if not flag:
        raise HTTPException(status_code=404, detail="Review flag not found")
        
    if flag.status == FlagStatus.resolved:
        raise HTTPException(status_code=400, detail="Flag is already resolved")
        
    flag.status = FlagStatus.resolved
    flag.resolved_by = resolver_name
    flag.resolved_at = datetime.now(timezone.utc)
    if notes:
        flag.notes = f"{flag.notes}\nResolution notes: {notes}"
        
    await db.commit()
    
    # Re-evaluate parent script status
    return await compute_script_status(db, flag.answer_script_id)

async def get_script_full_detail(db: AsyncSession, script_id: str) -> ScriptDetailResponse:
    script = await db.get(AnswerScript, script_id)
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
        
    student_name = "Anonymous Student"
    if script.student_id:
        student = await db.get(Student, script.student_id)
        if student:
            student_name = student.name
            
    # Get all evaluation runs
    evals_res = await db.execute(select(EvaluationRun).where(EvaluationRun.answer_script_id == script_id))
    all_runs = evals_res.scalars().all()
    
    # Get all flags
    flags_res = await db.execute(select(ReviewFlag).where(ReviewFlag.answer_script_id == script_id))
    all_flags = flags_res.scalars().all()
    
    # Get rubric version from segmentation run
    seg_res = await db.execute(select(SegmentationRun).where(SegmentationRun.answer_script_id == script_id))
    seg_run = seg_res.scalars().first()
    
    rubric_items_by_key = {}
    if seg_run:
        ri_res = await db.execute(select(RubricItem).where(RubricItem.rubric_version_id == seg_run.rubric_version_id))
        for ri in ri_res.scalars().all():
            key = f"{ri.question_number}_{ri.subpart_id}" if ri.subpart_id else ri.question_number
            rubric_items_by_key[key] = ri
            
    grouped = {}
    for run in all_runs:
        key = f"{run.question_number}_{run.subpart_id}" if run.subpart_id else run.question_number
        if key not in grouped:
            grouped[key] = {"runs": [], "flags": []}
        grouped[key]["runs"].append(run)
        
    for flag in all_flags:
        key = f"{flag.question_number}_{flag.subpart_id}" if flag.subpart_id else flag.question_number
        if key in grouped:
            grouped[key]["flags"].append(flag)
            
    evaluations = []
    total_awarded = 0.0
    total_max = 0.0
    
    for key, data in grouped.items():
        runs = data["runs"]
        flags = data["flags"]
        
        pass1_run = next((r for r in runs if r.run_type == RunType.ai_pass_1), None)
        pass2_run = next((r for r in runs if r.run_type == RunType.ai_pass_2), None)
        human_run = next((r for r in runs if r.run_type == RunType.human_final), None)
        
        if not pass1_run:
            continue
            
        ri = rubric_items_by_key.get(key)
        max_marks = float(ri.max_marks) if ri else 0.0
        allowed_increments = ri.allowed_increments if ri else []
        
        # Calculate final marks for this question
        marks_awarded = float(human_run.marks_awarded) if human_run else float(pass1_run.marks_awarded)
        
        total_max += max_marks
        total_awarded += marks_awarded
        
        pass1_resp = None
        if pass1_run:
            pass1_resp = ModelPassResponse(point_evaluations=[
                PointEvaluationSchema(
                    rubric_point_id=f"Point {pass1_run.id[:4]}",
                    marks_awarded=float(pass1_run.marks_awarded),
                    evidence_quote=pass1_run.evidence_quote,
                    reasoning=pass1_run.reasoning
                )
            ])
            
        pass2_resp = None
        if pass2_run:
            pass2_resp = ModelPassResponse(point_evaluations=[
                PointEvaluationSchema(
                    rubric_point_id=f"Point {pass2_run.id[:4]}",
                    marks_awarded=float(pass2_run.marks_awarded),
                    evidence_quote=pass2_run.evidence_quote,
                    reasoning=pass2_run.reasoning
                )
            ])
            
        review_resp = None
        if human_run:
            review_resp = OverrideDetail(
                action=human_run.reasoning.split("|")[1] if human_run.reasoning and "|" in human_run.reasoning else "overridden",
                reviewer=human_run.reasoning.split("|")[0] if human_run.reasoning and "|" in human_run.reasoning else "Unknown",
                final_marks=float(human_run.marks_awarded),
                comment=human_run.evidence_quote
            )
            
        flags_resp = [{"reason": f.notes, "type": f.flag_type.value, "status": f.status.value} for f in flags if f.status == FlagStatus.open]
        
        evaluations.append(QuestionEvaluationResponse(
            id=pass1_run.id,
            question_number=pass1_run.question_number,
            subpart_id=pass1_run.subpart_id,
            max_marks=max_marks,
            marks_awarded=marks_awarded,
            confidence=pass1_run.confidence or 1.0,
            flags=flags_resp,
            pass1=pass1_resp,
            pass2=pass2_resp,
            review=review_resp,
            allowed_increments=allowed_increments
        ))
        
    def sort_key(e):
        try:
            return float(e.question_number)
        except:
            return 999.0
    evaluations.sort(key=sort_key)
    
    return ScriptDetailResponse(
        id=script.id,
        student_name=student_name,
        status=script.status.value,
        evaluations=evaluations,
        summary={"total_awarded": total_awarded, "total_max": total_max}
    )

async def submit_human_override(db: AsyncSession, run_id: str, request: OverrideSubmitRequest):
    base_run = await db.get(EvaluationRun, run_id)
    if not base_run:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
        
    script_id = base_run.answer_script_id
    q_num = base_run.question_number
    s_id = base_run.subpart_id
    
    seg_res = await db.execute(select(SegmentationRun).where(SegmentationRun.answer_script_id == script_id))
    seg_run = seg_res.scalars().first()
    if seg_run:
        stmt = select(RubricItem).where(
            RubricItem.rubric_version_id == seg_run.rubric_version_id,
            RubricItem.question_number == q_num
        )
        if s_id:
            stmt = stmt.where(RubricItem.subpart_id == s_id)
        ri_res = await db.execute(stmt)
        ri = ri_res.scalars().first()
        if ri and ri.allowed_increments:
            if request.final_marks not in ri.allowed_increments:
                raise HTTPException(status_code=400, detail=f"Invalid mark. Allowed increments: {ri.allowed_increments}")
                
    existing_human = await db.execute(
        select(EvaluationRun)
        .where(EvaluationRun.answer_script_id == script_id)
        .where(EvaluationRun.question_number == q_num)
        .where(EvaluationRun.subpart_id == s_id)
        .where(EvaluationRun.run_type == RunType.human_final)
    )
    human_run = existing_human.scalars().first()
    
    if human_run:
        human_run.marks_awarded = request.final_marks
        human_run.evidence_quote = request.comment
        human_run.reasoning = f"{request.reviewer}|{request.action}"
    else:
        new_run = EvaluationRun(
            answer_script_id=script_id,
            question_number=q_num,
            subpart_id=s_id,
            run_type=RunType.human_final,
            model_used="human",
            marks_awarded=request.final_marks,
            evidence_quote=request.comment,
            reasoning=f"{request.reviewer}|{request.action}",
            confidence=1.0
        )
        db.add(new_run)
        
    flags_res = await db.execute(
        select(ReviewFlag)
        .where(ReviewFlag.answer_script_id == script_id)
        .where(ReviewFlag.question_number == q_num)
        .where(ReviewFlag.status == FlagStatus.open)
    )
    for flag in flags_res.scalars().all():
        if not s_id or flag.subpart_id == s_id:
            flag.status = FlagStatus.resolved
            flag.resolved_by = request.reviewer
            flag.resolved_at = datetime.now(timezone.utc)
            flag.notes = f"{flag.notes}\nResolved by human override"
        
    await db.commit()
    
    # Audit logging
    script = await db.get(AnswerScript, script_id)
    if script:
        from app.database.models import AuditLog
        audit = AuditLog(
            class_offering_id=script.class_offering_id,
            action_type="human_override",
            user_name=request.reviewer,
            user_role="unknown", # We don't have the role in this context directly, but frontend could pass it or we use reviewer name
            details={
                "script_id": script_id,
                "question_number": q_num,
                "subpart_id": s_id,
                "old_marks": float(base_run.marks_awarded),
                "new_marks": request.final_marks,
                "action": request.action
            }
        )
        db.add(audit)
        await db.commit()
        
    await compute_script_status(db, script_id)
    return {"status": "success"}

async def finalize_script(db: AsyncSession, script_id: str):
    script = await db.get(AnswerScript, script_id)
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
        
    flags_res = await db.execute(select(ReviewFlag).where(ReviewFlag.answer_script_id == script_id).where(ReviewFlag.status == FlagStatus.open))
    for flag in flags_res.scalars().all():
        flag.status = FlagStatus.resolved
        flag.resolved_by = "System (Force Finalize)"
        flag.resolved_at = datetime.now(timezone.utc)
        
    script.status = AnswerScriptStatus.final
    await db.commit()
    return {"status": "success"}

from app.review.schemas import BulkAcceptRequest, PeerComparisonResponse, PeerComparisonItem

async def bulk_accept_evaluations(db: AsyncSession, script_id: str, request: BulkAcceptRequest):
    """
    Bulk accept sub-parts where both models agree and confidence >= threshold.
    """
    eval_res = await db.execute(select(EvaluationRun).where(EvaluationRun.answer_script_id == script_id))
    all_runs = eval_res.scalars().all()

    grouped = {}
    for run in all_runs:
        key = f"{run.question_number}_{run.subpart_id}" if run.subpart_id else run.question_number
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(run)

    accepted_count = 0

    for key, runs in grouped.items():
        pass1 = next((r for r in runs if r.run_type == RunType.ai_pass_1), None)
        pass2 = next((r for r in runs if r.run_type == RunType.ai_pass_2), None)
        human = next((r for r in runs if r.run_type == RunType.human_final), None)

        if human:
            continue # already human verified

        if pass1 and pass2:
            conf1 = pass1.confidence or 1.0
            conf2 = pass2.confidence or 1.0
            if pass1.marks_awarded == pass2.marks_awarded and conf1 >= request.confidence_threshold and conf2 >= request.confidence_threshold:
                # Accept this one
                new_run = EvaluationRun(
                    answer_script_id=script_id,
                    question_number=pass1.question_number,
                    subpart_id=pass1.subpart_id,
                    run_type=RunType.human_final,
                    model_used="human",
                    marks_awarded=pass1.marks_awarded,
                    evidence_quote="Bulk accepted: Models agree with high confidence",
                    reasoning=f"{request.reviewer}|Bulk Accept",
                    confidence=1.0
                )
                db.add(new_run)
                
                # Resolve flags for this subpart
                flags_res = await db.execute(
                    select(ReviewFlag)
                    .where(ReviewFlag.answer_script_id == script_id)
                    .where(ReviewFlag.question_number == pass1.question_number)
                    .where(ReviewFlag.status == FlagStatus.open)
                )
                for flag in flags_res.scalars().all():
                    if not pass1.subpart_id or flag.subpart_id == pass1.subpart_id:
                        flag.status = FlagStatus.resolved
                        flag.resolved_by = request.reviewer
                        flag.resolved_at = datetime.now(timezone.utc)
                        flag.notes = f"{flag.notes}\nResolved by bulk accept"
                
                # Audit log
                script = await db.get(AnswerScript, script_id)
                if script:
                    from app.database.models import AuditLog
                    audit = AuditLog(
                        class_offering_id=script.class_offering_id,
                        action_type="bulk_accept_override",
                        user_name=request.reviewer,
                        user_role="unknown",
                        details={
                            "script_id": script_id,
                            "question_number": pass1.question_number,
                            "subpart_id": pass1.subpart_id,
                            "old_marks": float(pass1.marks_awarded),
                            "new_marks": float(pass1.marks_awarded),
                            "action": "bulk_accept"
                        }
                    )
                    db.add(audit)
                
                accepted_count += 1

    await db.commit()
    await compute_script_status(db, script_id)
    return {"status": "success", "accepted_count": accepted_count}

async def get_peer_comparisons(
    db: AsyncSession, 
    offering_id: str, 
    question_number: str, 
    subpart_id: str, 
    exclude_script_id: str
) -> PeerComparisonResponse:
    # Get 3 scripts in this offering that have a human_final or ai_pass_1 for this subpart
    # For a real system we might randomize, for now just take limit 3
    stmt = (
        select(EvaluationRun)
        .join(AnswerScript)
        .where(AnswerScript.class_offering_id == offering_id)
        .where(EvaluationRun.question_number == question_number)
        .where(EvaluationRun.run_type.in_([RunType.human_final, RunType.ai_pass_1]))
    )
    if subpart_id:
        stmt = stmt.where(EvaluationRun.subpart_id == subpart_id)
    if exclude_script_id:
        stmt = stmt.where(EvaluationRun.answer_script_id != exclude_script_id)
        
    res = await db.execute(stmt)
    runs = res.scalars().all()
    
    # Group by script, prefer human_final
    script_best_run = {}
    for r in runs:
        sid = r.answer_script_id
        if sid not in script_best_run:
            script_best_run[sid] = r
        elif r.run_type == RunType.human_final:
            script_best_run[sid] = r
            
    # Take up to 3
    peers = []
    for sid, r in list(script_best_run.items())[:3]:
        peers.append(PeerComparisonItem(
            script_id=sid,
            marks_awarded=float(r.marks_awarded),
            evidence_quote=r.evidence_quote
        ))
        
    return PeerComparisonResponse(peers=peers)
