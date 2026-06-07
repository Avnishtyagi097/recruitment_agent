from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


class CandidateCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role_applied: str
    cv_text: Optional[str] = None


class CandidateResponse(BaseModel):
    id: int
    candidate_id: str
    name: str
    email: Optional[str]
    role_applied: str
    ats_score: float
    ats_decision: str
    assessment_score: Optional[float]
    assessment_decision: Optional[str]
    status: str
    interview_scheduled: bool
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class CandidateListResponse(BaseModel):
    total: int
    candidates: List[CandidateResponse]


class ATSRequest(BaseModel):
    candidate_id: Optional[str] = None
    name: str
    email: Optional[str] = None
    role_applied: str
    jd_text: str
    cv_text: str


class ATSResponse(BaseModel):
    candidate_id: str
    ats_score: float
    decision: str
    reasoning: str
    matched_skills: List[str]
    missing_skills: List[str]
    experience_match: str
    strengths: List[str]
    gaps: List[str]
    requires_review: bool
    breakdown: dict


class AssessmentStartRequest(BaseModel):
    candidate_id: str
    num_questions: int = 30


class AssessmentSubmitRequest(BaseModel):
    candidate_id: str
    answers: dict  # {"0": 1, "1": 0, ...}


class AssessmentResponse(BaseModel):
    score_percent: float
    correct: int
    total: int
    decision: str
    strength_areas: List[str]
    weak_areas: List[str]


class PipelineLogResponse(BaseModel):
    id: int
    candidate_id: str
    stage: str
    decision: str
    score: Optional[str]
    reason: Optional[str]
    next_action: Optional[str]
    owner: str
    timestamp: Optional[datetime]

    class Config:
        from_attributes = True
