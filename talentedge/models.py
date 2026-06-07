from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    """Recruiter/Admin user accounts."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    company_name = Column(String(255), nullable=False)
    phone_number = Column(String(50), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), default="recruiter")  # recruiter, admin
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Password reset
    reset_token = Column(String(255), nullable=True)
    reset_token_expiry = Column(DateTime(timezone=True), nullable=True)

    # Rate limiting
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    candidates = relationship("Candidate", back_populates="owner")

    def __repr__(self):
        return f"<User {self.email}>"


class Candidate(Base):
    """Candidate pipeline record."""
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(String(100), unique=True, nullable=False, index=True)  # CAND-20250601...
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Multi-tenancy

    # Basic info
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    role_applied = Column(String(255), nullable=False)
    cv_text = Column(Text, nullable=True)

    # ATS
    ats_score = Column(Float, default=0)
    ats_decision = Column(String(20), default="")  # PASS, FAIL, REVIEW
    ats_result_json = Column(Text, nullable=True)  # Full ATS result as JSON

    # Assessment
    assessment_score = Column(Float, nullable=True)
    assessment_decision = Column(String(20), nullable=True)
    assessment_result_json = Column(Text, nullable=True)
    assessment_duration_mins = Column(Integer, default=20)

    # Status
    status = Column(String(100), default="Pending")
    # Pending → Passed ATS → Assessment Sent → Passed/Failed Assessment → Interview Scheduled → Hired/Rejected

    # Interview
    interview_scheduled = Column(Boolean, default=False)
    interview_slots_json = Column(Text, nullable=True)
    interview_panel_json = Column(Text, nullable=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    owner = relationship("User", back_populates="candidates")
    logs = relationship("PipelineLog", back_populates="candidate", cascade="all, delete-orphan")
    emails = relationship("EmailLog", back_populates="candidate", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Candidate {self.name} ({self.status})>"


class PipelineLog(Base):
    """Audit trail for every decision in the pipeline."""
    __tablename__ = "pipeline_logs"

    id = Column(Integer, primary_key=True, index=True)
    candidate_db_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    candidate_id = Column(String(100), nullable=False)  # CAND-xxx for display
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    stage = Column(String(100), nullable=False)
    decision = Column(String(50), nullable=False)
    score = Column(String(50), nullable=True)
    reason = Column(Text, nullable=True)
    next_action = Column(String(255), nullable=True)
    owner = Column(String(50), default="AI_AGENT")

    candidate = relationship("Candidate", back_populates="logs")


class EmailLog(Base):
    """Log of all emails sent."""
    __tablename__ = "email_logs"

    id = Column(Integer, primary_key=True, index=True)
    candidate_db_id = Column(Integer, ForeignKey("candidates.id"), nullable=True)
    to_email = Column(String(255), nullable=False)
    subject = Column(String(500), nullable=True)
    email_type = Column(String(100), nullable=True)
    status = Column(String(20), nullable=False)  # SENT, FAILED, QUEUED
    detail = Column(Text, nullable=True)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())

    candidate = relationship("Candidate", back_populates="emails")


class AssessmentCredential(Base):
    """Candidate assessment login credentials."""
    __tablename__ = "assessment_credentials"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(100), unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=False)
    password = Column(String(255), nullable=False)  # Plain text (temp credential)
    candidate_id = Column(String(100), nullable=False)
    candidate_name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CustomAssessment(Base):
    """Recruiter-uploaded custom assessment questions."""
    __tablename__ = "custom_assessments"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(String(100), nullable=True)  # NULL = role-level default
    role = Column(String(255), nullable=True)
    questions_json = Column(Text, nullable=False)
    duration_minutes = Column(Integer, default=20)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AppSetting(Base):
    """Key-value store for app settings (SMTP config, etc.)."""
    __tablename__ = "app_settings"

    key = Column(String(255), primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
