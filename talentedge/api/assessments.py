import json
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from database import get_db
from models import Candidate, PipelineLog, CustomAssessment
from auth.utils import require_auth
from services.assessment_engine import get_questions, score_assessment
from api.schemas import AssessmentStartRequest, AssessmentSubmitRequest, AssessmentResponse

router = APIRouter(prefix="/api/assessments", tags=["Assessments"])


@router.post("/start")
def start_assessment(data: AssessmentStartRequest, request: Request, db: Session = Depends(get_db)):
    """Get assessment questions for a candidate."""
    cand = db.query(Candidate).filter(Candidate.candidate_id == data.candidate_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found")

    # Check for custom assessment
    custom = db.query(CustomAssessment).filter(
        CustomAssessment.candidate_id == data.candidate_id
    ).order_by(CustomAssessment.id.desc()).first()

    if custom and custom.questions_json:
        import random
        questions = json.loads(custom.questions_json)
        random.shuffle(questions)
        questions = questions[:data.num_questions]
    else:
        questions = get_questions(cand.role_applied, data.num_questions)

    duration = cand.assessment_duration_mins or 20

    return {
        "candidate_id": data.candidate_id,
        "candidate_name": cand.name,
        "role": cand.role_applied,
        "questions": questions,
        "duration_minutes": duration,
        "total_questions": len(questions),
    }


@router.post("/submit", response_model=AssessmentResponse)
def submit_assessment(data: AssessmentSubmitRequest, db: Session = Depends(get_db)):
    """Submit assessment answers and get score."""
    cand = db.query(Candidate).filter(Candidate.candidate_id == data.candidate_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found")

    if cand.assessment_result_json:
        raise HTTPException(status_code=400, detail="Assessment already submitted")

    # Reconstruct questions (from custom or built-in)
    custom = db.query(CustomAssessment).filter(
        CustomAssessment.candidate_id == data.candidate_id
    ).order_by(CustomAssessment.id.desc()).first()

    if custom and custom.questions_json:
        questions = json.loads(custom.questions_json)
    else:
        questions = get_questions(cand.role_applied, 30)

    result = score_assessment(questions, data.answers)

    # Update candidate
    cand.assessment_score = result["score_percent"]
    cand.assessment_decision = result["decision"]
    cand.assessment_result_json = json.dumps(result)
    cand.status = "Passed Assessment" if result["decision"] == "PASS" else "Failed Assessment"

    # Log
    log = PipelineLog(
        candidate_db_id=cand.id, candidate_id=data.candidate_id,
        stage="ASSESSMENT", decision=result["decision"],
        score=f"{result['correct']}/{result['total']} ({result['score_percent']}%)",
        reason=f"Score: {result['score_percent']}%",
        next_action="Interview" if result["decision"] == "PASS" else "Rejection",
    )
    db.add(log)
    db.commit()

    return result


@router.get("/questions/{candidate_id}")
def get_assessment_questions(candidate_id: str, db: Session = Depends(get_db)):
    """Get questions for candidate (for candidate portal)."""
    cand = db.query(Candidate).filter(Candidate.candidate_id == candidate_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found")

    custom = db.query(CustomAssessment).filter(
        CustomAssessment.candidate_id == candidate_id
    ).order_by(CustomAssessment.id.desc()).first()

    if custom:
        questions = json.loads(custom.questions_json)
    else:
        questions = get_questions(cand.role_applied, 30)

    # Strip answers for candidate view
    safe_questions = []
    for q in questions:
        safe_questions.append({
            "q": q["q"], "options": q["options"],
            "topic": q.get("topic", ""), "difficulty": q.get("difficulty", ""),
        })

    return {
        "candidate_name": cand.name, "role": cand.role_applied,
        "questions": safe_questions, "duration_minutes": cand.assessment_duration_mins or 20,
    }
