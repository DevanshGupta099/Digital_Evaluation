import uuid
from datetime import datetime, timezone
import enum
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, Float, ForeignKey, JSON, 
    Enum as SQLAlchemyEnum, DateTime, Text, UniqueConstraint, Numeric, Boolean
)
from sqlalchemy.orm import declarative_base, relationship

class UserRole(str, enum.Enum):
    admin = "admin"
    exam_coordinator = "exam_coordinator"
    evaluator = "evaluator"
    read_only = "read_only"
    student = "student"


Base = declarative_base()

def get_uuid() -> str:
    return uuid.uuid4().hex

def get_now() -> datetime:
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"
    id = Column(String(32), primary_key=True, default=get_uuid)
    username = Column(String(100), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    role = Column(SQLAlchemyEnum(UserRole), nullable=False, default=UserRole.read_only)
    department_id = Column(String(32), ForeignKey("departments.id"), nullable=True) # Optional scoping

class Department(Base):
    __tablename__ = "departments"
    id = Column(String(32), primary_key=True, default=get_uuid)
    name = Column(String(200), nullable=False)

class Course(Base):
    __tablename__ = "courses"
    id = Column(String(32), primary_key=True, default=get_uuid)
    name = Column(String(200), nullable=False)
    department_id = Column(String(32), ForeignKey("departments.id"), nullable=False)

class Section(Base):
    __tablename__ = "sections"
    id = Column(String(32), primary_key=True, default=get_uuid)
    name = Column(String(100), nullable=False)
    course_id = Column(String(32), ForeignKey("courses.id"), nullable=False)

class AcademicTerm(Base):
    __tablename__ = "academic_terms"
    id = Column(String(32), primary_key=True, default=get_uuid)
    semester = Column(String(50), nullable=False)
    year = Column(Integer, nullable=False)
    
    __table_args__ = (
        UniqueConstraint('semester', 'year', name='uq_academic_term_semester_year'),
    )

class Subject(Base):
    __tablename__ = "subjects"
    id = Column(String(32), primary_key=True, default=get_uuid)
    name = Column(String(200), nullable=False)

class ClassOffering(Base):
    __tablename__ = "class_offerings"
    id = Column(String(32), primary_key=True, default=get_uuid)
    department_id = Column(String(32), ForeignKey("departments.id"), nullable=False)
    course_id = Column(String(32), ForeignKey("courses.id"), nullable=False)
    section_id = Column(String(32), ForeignKey("sections.id"), nullable=False)
    academic_term_id = Column(String(32), ForeignKey("academic_terms.id"), nullable=False)
    subject_id = Column(String(32), ForeignKey("subjects.id"), nullable=False)
    results_published = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            'department_id', 'course_id', 'section_id', 'academic_term_id', 'subject_id', 
            name='uq_class_offering'
        ),
    )

class Student(Base):
    __tablename__ = "students"
    id = Column(String(32), primary_key=True, default=get_uuid)
    roll_number = Column(String(100), nullable=False, unique=True)
    name = Column(String(200), nullable=False)
    section_id = Column(String(32), ForeignKey("sections.id"), nullable=False)

class QuestionPaper(Base):
    __tablename__ = "question_papers"
    id = Column(String(32), primary_key=True, default=get_uuid)
    class_offering_id = Column(String(32), ForeignKey("class_offerings.id"), unique=True, nullable=False)
    original_file_path = Column(String(600), nullable=False)
    page_count = Column(Integer, nullable=False)

class AnswerKey(Base):
    __tablename__ = "answer_keys"
    id = Column(String(32), primary_key=True, default=get_uuid)
    class_offering_id = Column(String(32), ForeignKey("class_offerings.id"), unique=True, nullable=False)
    original_file_path = Column(String(600), nullable=False)
    page_count = Column(Integer, nullable=False)

class RubricStatus(str, enum.Enum):
    draft = "draft"
    approved = "approved"
    locked = "locked"

class RubricVersion(Base):
    __tablename__ = "rubric_versions"
    id = Column(String(32), primary_key=True, default=get_uuid)
    question_paper_id = Column(String(32), ForeignKey("question_papers.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    status = Column(SQLAlchemyEnum(RubricStatus), default=RubricStatus.draft, nullable=False)
    approved_by = Column(String(200), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_now, nullable=False)

    items = relationship("RubricItem", back_populates="version")

class RubricItem(Base):
    __tablename__ = "rubric_items"
    id = Column(String(32), primary_key=True, default=get_uuid)
    rubric_version_id = Column(String(32), ForeignKey("rubric_versions.id"), nullable=False)
    question_number = Column(String(20), nullable=False)
    subpart_id = Column(String(20), nullable=True)
    max_marks = Column(Float, nullable=False)
    allowed_increments = Column(JSON, nullable=False)  # JSON array e.g. [0, 0.5, 1, 1.5, 2]
    expected_concepts = Column(JSON, nullable=True)
    accepted_alternates = Column(JSON, nullable=True)
    example_full = Column(Text, nullable=True)
    example_partial = Column(Text, nullable=True)
    requires_visual = Column(Boolean, default=False, nullable=False)

    version = relationship("RubricVersion", back_populates="items")

class RubricAddendum(Base):
    __tablename__ = "rubric_addenda"
    id = Column(String(32), primary_key=True, default=get_uuid)
    rubric_item_id = Column(String(32), ForeignKey("rubric_items.id"), nullable=False)
    added_text = Column(Text, nullable=False)
    added_by = Column(String(200), nullable=False)
    added_at = Column(DateTime(timezone=True), default=get_now, nullable=False)

class AnswerScriptStatus(str, enum.Enum):
    uploaded = "uploaded"
    queued = "queued"
    processing = "processing"
    ocr_done = "ocr_done"
    segmented = "segmented"
    graded = "graded"
    provisional = "provisional"
    final = "final"

class AnswerScript(Base):
    __tablename__ = "answer_scripts"
    id = Column(String(32), primary_key=True, default=get_uuid)
    student_id = Column(String(32), ForeignKey("students.id"), nullable=False)
    class_offering_id = Column(String(32), ForeignKey("class_offerings.id"), nullable=False)
    original_file_path = Column(String(600), nullable=False)
    file_hash = Column(String(128), nullable=True)
    status = Column(SQLAlchemyEnum(AnswerScriptStatus), default=AnswerScriptStatus.uploaded, nullable=False)

class OCRPage(Base):
    __tablename__ = "ocr_pages"
    id = Column(String(32), primary_key=True, default=get_uuid)
    answer_script_id = Column(String(32), ForeignKey("answer_scripts.id"), nullable=False)
    page_number = Column(Integer, nullable=False)
    image_path = Column(String(600), nullable=False)
    scale_factor = Column(Float, nullable=False)
    rotation = Column(Integer, nullable=False)
    ocr_json = Column(JSON, nullable=False)
    masked_regions = Column(JSON, nullable=True)

class SegmentationRun(Base):
    __tablename__ = "segmentation_runs"
    id = Column(String(32), primary_key=True, default=get_uuid)
    answer_script_id = Column(String(32), ForeignKey("answer_scripts.id"), nullable=False)
    rubric_version_id = Column(String(32), ForeignKey("rubric_versions.id"), nullable=False)
    mappings = Column(JSON, nullable=False)
    orphaned_content = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_now, nullable=False)

class BatchJobStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"

class BatchJob(Base):
    __tablename__ = "batch_jobs"
    id = Column(String(32), primary_key=True, default=get_uuid)
    class_offering_id = Column(String(32), ForeignKey("class_offerings.id"), nullable=False)
    provider = Column(String(50), nullable=False)  # e.g., 'claude', 'gemini'
    external_batch_id = Column(String(200), nullable=True) # ID from Anthropic
    status = Column(SQLAlchemyEnum(BatchJobStatus), default=BatchJobStatus.pending, nullable=False)
    total_requests = Column(Integer, default=0, nullable=False)
    completed_requests = Column(Integer, default=0, nullable=False)
    failed_requests = Column(Integer, default=0, nullable=False)
    request_mapping = Column(JSON, nullable=True) # maps internal custom_id to (script_id, q_no, subpart_id)
    created_at = Column(DateTime(timezone=True), default=get_now, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

class UsageLog(Base):
    __tablename__ = "usage_logs"
    id = Column(String(32), primary_key=True, default=get_uuid)
    class_offering_id = Column(String(32), ForeignKey("class_offerings.id"), nullable=False)
    provider = Column(String(50), nullable=False)
    input_tokens = Column(Integer, default=0, nullable=False)
    cache_read_input_tokens = Column(Integer, default=0, nullable=False)
    cache_creation_input_tokens = Column(Integer, default=0, nullable=False)
    output_tokens = Column(Integer, default=0, nullable=False)
    estimated_cost_usd = Column(Numeric(precision=10, scale=6), default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_now, nullable=False)

class RunType(str, enum.Enum):
    ai_pass_1 = "ai_pass_1"
    ai_pass_2 = "ai_pass_2"
    human_final = "human_final"

class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"
    id = Column(String(32), primary_key=True, default=get_uuid)
    answer_script_id = Column(String(32), ForeignKey("answer_scripts.id"), nullable=False)
    batch_job_id = Column(String(32), ForeignKey("batch_jobs.id"), nullable=True)
    question_number = Column(String(20), nullable=False)
    subpart_id = Column(String(20), nullable=True)
    run_type = Column(SQLAlchemyEnum(RunType), nullable=False)
    model_used = Column(String(100), nullable=True)
    marks_awarded = Column(Numeric(precision=5, scale=2), nullable=False)
    evidence_quote = Column(Text, nullable=True)
    reasoning = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_now, nullable=False)

class FlagType(str, enum.Enum):
    uncertain_segmentation = "uncertain_segmentation"
    orphaned_content = "orphaned_content"
    low_ocr_confidence = "low_ocr_confidence"
    high_variance = "high_variance"
    possible_wrong_upload = "possible_wrong_upload"
    unmatched_annotation = "unmatched_annotation"
    rubric_addendum_recheck = "rubric_addendum_recheck"
    suspicious_similarity = "suspicious_similarity"

class FlagStatus(str, enum.Enum):
    open = "open"
    resolved = "resolved"

class ReviewFlag(Base):
    __tablename__ = "review_flags"
    id = Column(String(32), primary_key=True, default=get_uuid)
    answer_script_id = Column(String(32), ForeignKey("answer_scripts.id"), nullable=False)
    question_number = Column(String(20), nullable=True)
    subpart_id = Column(String(20), nullable=True)
    flag_type = Column(SQLAlchemyEnum(FlagType), nullable=False)
    status = Column(SQLAlchemyEnum(FlagStatus), default=FlagStatus.open, nullable=False)
    resolved_by = Column(String(200), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)

class MarkType(str, enum.Enum):
    tick = "tick"
    cross = "cross"

class Annotation(Base):
    __tablename__ = "annotations"
    id = Column(String(32), primary_key=True, default=get_uuid)
    answer_script_id = Column(String(32), ForeignKey("answer_scripts.id"), nullable=False)
    page_number = Column(Integer, nullable=False)
    subpart_id = Column(String(20), nullable=True)
    mark_type = Column(SQLAlchemyEnum(MarkType), nullable=False)
    bbox = Column(JSON, nullable=False)
    pdf_coordinates = Column(JSON, nullable=False)

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(String(32), primary_key=True, default=get_uuid)
    class_offering_id = Column(String(32), ForeignKey("class_offerings.id"), nullable=False)
    type = Column(String(50), nullable=False)  # e.g., 'batch_complete', 'flag_raised', 'rubric_addendum'
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_now, nullable=False)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(String(32), primary_key=True, default=get_uuid)
    class_offering_id = Column(String(32), ForeignKey("class_offerings.id"), nullable=False)
    action_type = Column(String(100), nullable=False)
    user_name = Column(String(200), nullable=False)
    user_role = Column(String(50), nullable=False)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_now, nullable=False)
