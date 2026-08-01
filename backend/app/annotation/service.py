import logging
import os
import fitz
import rapidfuzz
from typing import List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException

from app.database.models import (
    AnswerScript, OCRPage, EvaluationRun, Annotation, 
    MarkType, ReviewFlag, FlagType, RubricItem, RubricVersion, SegmentationRun
)

logger = logging.getLogger(__name__)

def _get_boxes_for_match(
    evidence_quote: str,
    ocr_words: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Concatenates OCR words and uses rapidfuzz to find the substring match.
    Returns grouped bounding boxes per line_id or fallback grouping.
    """
    if not evidence_quote or not ocr_words:
        return []
        
    # Build text and track character offsets for each word
    full_text = ""
    word_offsets = []
    
    for w in ocr_words:
        start_idx = len(full_text)
        text = w.get("text", "")
        full_text += text + " "
        end_idx = len(full_text) - 1 # exclude the space
        word_offsets.append((start_idx, end_idx, w))
        
    full_text = full_text.strip()
    
    # Rapidfuzz partial_ratio_alignment
    try:
        align = rapidfuzz.fuzz.partial_ratio_alignment(evidence_quote, full_text)
        if not align or align.score < 80.0:
            return []
            
        dest_start = align.dest_start
        dest_end = align.dest_end
        
        # Find which words overlap with [dest_start, dest_end]
        matched_words = []
        for start_idx, end_idx, w in word_offsets:
            # Overlap condition
            if start_idx <= dest_end and end_idx >= dest_start:
                matched_words.append(w)
                
        if not matched_words:
            return []
            
        # Group by line_id (or approximate y-coordinate if missing)
        lines = {}
        for w in matched_words:
            line_id = w.get("line_id")
            if not line_id:
                # Fallback to y grouping (approx 10 pixels)
                y1 = w.get("bbox", [0,0,0,0])[1]
                line_id = f"approx_{int(y1 // 10)}"
                
            if line_id not in lines:
                lines[line_id] = []
            lines[line_id].append(w)
            
        # Compute combined bbox for each line
        line_bboxes = []
        for line_id, words in lines.items():
            min_x = min(w["bbox"][0] for w in words)
            min_y = min(w["bbox"][1] for w in words)
            max_r = max(w["bbox"][0] + w["bbox"][2] for w in words)
            max_b = max(w["bbox"][1] + w["bbox"][3] for w in words)
            
            line_bboxes.append({
                "x": min_x,
                "y": min_y,
                "w": max_r - min_x,
                "h": max_b - min_y
            })
            
        return line_bboxes
    except Exception as e:
        logger.error(f"Fuzzy match failed: {e}")
        return []

async def annotate_script(db: AsyncSession, answer_script_id: str) -> str:
    # 1. Fetch script
    script = await db.get(AnswerScript, answer_script_id)
    if not script:
        raise HTTPException(status_code=404, detail="Answer script not found")
        
    if not script.original_file_path or not os.path.exists(script.original_file_path):
        raise HTTPException(status_code=400, detail="Original PDF not found")
        
    # 2. Fetch evaluation runs (using ai_pass_1 as primary for MVP)
    eval_res = await db.execute(
        select(EvaluationRun)
        .where(EvaluationRun.answer_script_id == answer_script_id)
        .where(EvaluationRun.run_type == "ai_pass_1")
    )
    eval_runs = eval_res.scalars().all()
    
    # 3. Fetch Rubric to get max marks per question
    seg_res = await db.execute(
        select(SegmentationRun)
        .where(SegmentationRun.answer_script_id == answer_script_id)
        .order_by(SegmentationRun.created_at.desc())
    )
    seg_run = seg_res.scalars().first()
    
    max_marks_dict = {}
    if seg_run:
        ri_res = await db.execute(
            select(RubricItem)
            .where(RubricItem.rubric_version_id == seg_run.rubric_version_id)
        )
        for ri in ri_res.scalars().all():
            key = f"{ri.question_number}_{ri.subpart_id}" if ri.subpart_id else ri.question_number
            max_marks_dict[key] = ri.max_marks
            
    # 4. Fetch all OCR Pages
    ocr_res = await db.execute(
        select(OCRPage)
        .where(OCRPage.answer_script_id == answer_script_id)
    )
    pages_dict = {p.page_number: p for p in ocr_res.scalars().all()}
    
    # We will open the PDF and draw
    doc = fitz.open(script.original_file_path)
    
    drawn_totals = set() # Track to only draw total on first page of question
    
    for run in eval_runs:
        q_key = f"{run.question_number}_{run.subpart_id}" if run.subpart_id else run.question_number
        max_marks = max_marks_dict.get(q_key, 0)
        
        # Determine mark type
        if run.marks_awarded == max_marks and max_marks > 0:
            mtype = MarkType.tick
            color = (0, 0.8, 0) # Green
        elif run.marks_awarded == 0:
            mtype = MarkType.cross
            color = (0.8, 0, 0) # Red
        else:
            mtype = MarkType.tick # We can use tick for partial, just different color
            color = (0.8, 0.5, 0) # Orange
            
        # Find which pages this question is mapped to
        mapped_pages = []
        if seg_run:
            for m in seg_run.mappings:
                if m.get("question_number") == run.question_number:
                    mapped_pages.extend(m.get("pages", []))
        mapped_pages = sorted(list(set(mapped_pages)))
        
        # We need to find the evidence quote on one of these pages.
        # For simplicity, we concat the OCR words of all mapped pages, but map them back to page numbers.
        # Actually, it's easier to search page by page and take the best match.
        best_match_bboxes = []
        matched_page_num = None
        
        if run.evidence_quote and run.evidence_quote != "N/A":
            for pnum in mapped_pages:
                if pnum not in pages_dict:
                    continue
                p_obj = pages_dict[pnum]
                words = p_obj.ocr_json.get("words", [])
                bboxes = _get_boxes_for_match(run.evidence_quote, words)
                if bboxes:
                    best_match_bboxes = bboxes
                    matched_page_num = pnum
                    break # Found it
                    
        if not best_match_bboxes and run.evidence_quote:
            # Flag unmatched annotation
            flag = ReviewFlag(
                answer_script_id=answer_script_id,
                question_number=run.question_number,
                subpart_id=run.subpart_id,
                flag_type=FlagType.unmatched_annotation,
                notes=f"Could not place evidence quote: '{run.evidence_quote[:50]}...'"
            )
            db.add(flag)
            continue
            
        if best_match_bboxes and matched_page_num:
            # Transform and draw
            p_obj = pages_dict[matched_page_num]
            scale = p_obj.scale_factor
            pdf_page = doc[matched_page_num - 1]
            
            # Rotation handling: PyMuPDF's draw primitives are sensitive to the coordinate system.
            # Usually dividing by scale gives coords relative to the unrotated cropbox IF image was rendered unrotated.
            # But in Phase 0, we rendered the page with rotation. So pixel coordinates are in rotated space.
            # PyMuPDF pdf_page coordinates are unrotated. 
            # To draw properly, we can use standard points and a transformation matrix, but often simply dividing by scale is close enough if we rotate the rect.
            # For this MVP, let's divide by scale_factor directly.
            
            for bbox in best_match_bboxes:
                pdf_x = bbox["x"] / scale
                pdf_y = bbox["y"] / scale
                pdf_w = bbox["w"] / scale
                pdf_h = bbox["h"] / scale
                
                # Draw a mark next to it
                # Put it slightly to the right of the bounding box
                mark_x = pdf_x + pdf_w + 5
                mark_y = pdf_y + (pdf_h / 2)
                
                if mtype == MarkType.tick:
                    p1 = fitz.Point(mark_x, mark_y)
                    p2 = fitz.Point(mark_x + 5, mark_y + 10)
                    p3 = fitz.Point(mark_x + 15, mark_y - 10)
                    pdf_page.draw_polyline([p1, p2, p3], color=color, width=1.5)
                else: # cross
                    pdf_page.draw_line(fitz.Point(mark_x, mark_y - 5), fitz.Point(mark_x + 10, mark_y + 5), color=color, width=1.5)
                    pdf_page.draw_line(fitz.Point(mark_x, mark_y + 5), fitz.Point(mark_x + 10, mark_y - 5), color=color, width=1.5)
                    
                # Save annotation record
                ann = Annotation(
                    answer_script_id=answer_script_id,
                    page_number=matched_page_num,
                    subpart_id=run.subpart_id,
                    mark_type=mtype,
                    bbox=bbox,
                    pdf_coordinates={"x": pdf_x, "y": pdf_y, "w": pdf_w, "h": pdf_h}
                )
                db.add(ann)
                
        # Draw total for this question on the first mapped page
        if mapped_pages and run.question_number not in drawn_totals:
            first_page = mapped_pages[0]
            pdf_page = doc[first_page - 1]
            
            # Arbitrary placement at top right for MVP
            text = f"Q{run.question_number}: {float(run.marks_awarded)}/{float(max_marks)}"
            if len(mapped_pages) > 1:
                text += f"\n(cont. on p.{mapped_pages[-1]})"
                
            pdf_page.draw_rect(fitz.Rect(pdf_page.rect.width - 120, 20, pdf_page.rect.width - 20, 60), color=(0,0,0), fill=(1,1,1))
            pdf_page.insert_text(fitz.Point(pdf_page.rect.width - 115, 35), text, fontsize=10, color=(0,0,0))
            
            drawn_totals.add(run.question_number)
            
    await db.commit()
    
    # Save the annotated PDF
    base, ext = os.path.splitext(script.original_file_path)
    out_path = f"{base}_annotated{ext}"
    doc.save(out_path)
    doc.close()
    
    return out_path
