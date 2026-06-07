import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database import get_db
from models import AssessmentCredential, Candidate, PipelineLog, CustomAssessment
from services.assessment_engine import get_questions, score_assessment
from services.email_service import send_rejection_email, send_interview_invitation, send_recruiter_notification

router = APIRouter(prefix="/api/assess", tags=["Candidate Assessment"])


@router.get("/verify")
def verify_credentials(token: str, username: str, password: str, db: Session = Depends(get_db)):
    """Verify candidate assessment credentials and return questions."""
    cred = db.query(AssessmentCredential).filter(AssessmentCredential.token == token).first()
    if not cred or cred.username != username or cred.password != password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    cand = db.query(Candidate).filter(Candidate.candidate_id == cred.candidate_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found")

    if cand.assessment_result_json:
        raise HTTPException(status_code=400, detail="Assessment already submitted")

    # Load questions (custom or built-in)
    custom = db.query(CustomAssessment).filter(
        CustomAssessment.candidate_id == cred.candidate_id
    ).order_by(CustomAssessment.id.desc()).first()

    if custom and custom.questions_json:
        import random
        questions = json.loads(custom.questions_json)
        random.shuffle(questions)
    else:
        questions = get_questions(cand.role_applied, 30)

    # Strip answers for candidate
    safe_qs = [{"q": q["q"], "options": q["options"], "topic": q.get("topic", "")} for q in questions]

    # Store full questions in session for scoring later
    cand.ats_result_json = cand.ats_result_json  # keep existing

    return {
        "valid": True, "candidate_id": cred.candidate_id,
        "candidate_name": cand.name, "role": cand.role_applied,
        "questions": safe_qs, "duration_minutes": cand.assessment_duration_mins or 20,
    }


@router.post("/submit")
def submit_assessment(data: dict, db: Session = Depends(get_db)):
    """Submit candidate assessment answers."""
    token = data.get("token")
    candidate_id = data.get("candidate_id")
    answers = data.get("answers", {})

    cred = db.query(AssessmentCredential).filter(AssessmentCredential.token == token).first()
    if not cred:
        raise HTTPException(status_code=401, detail="Invalid token")

    cand = db.query(Candidate).filter(Candidate.candidate_id == candidate_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found")

    if cand.assessment_result_json:
        raise HTTPException(status_code=400, detail="Already submitted")

    # Get full questions (with answers) for scoring
    custom = db.query(CustomAssessment).filter(
        CustomAssessment.candidate_id == candidate_id
    ).order_by(CustomAssessment.id.desc()).first()

    if custom and custom.questions_json:
        questions = json.loads(custom.questions_json)
    else:
        questions = get_questions(cand.role_applied, 30)

    # Convert string keys to match
    str_answers = {str(k): v for k, v in answers.items()}
    result = score_assessment(questions, str_answers)

    # Update candidate
    cand.assessment_score = result["score_percent"]
    cand.assessment_decision = result["decision"]
    cand.assessment_result_json = json.dumps(result)
    cand.status = "Passed Assessment" if result["decision"] == "PASS" else "Failed Assessment"

    # Log
    log = PipelineLog(
        candidate_db_id=cand.id, candidate_id=candidate_id,
        stage="ASSESSMENT", decision=result["decision"],
        score=f"{result['correct']}/{result['total']} ({result['score_percent']}%)",
        reason=f"Score: {result['score_percent']}%",
        next_action="Interview" if result["decision"] == "PASS" else "Rejection",
    )
    db.add(log)

    # Auto-email based on result
    if result["decision"] == "PASS":
        cand.status = "Interview Scheduled"
        cand.interview_scheduled = True
        slots = ["Monday 10:00 AM UTC", "Tuesday 2:30 PM UTC", "Wednesday 11:00 AM UTC"]
        send_interview_invitation(db, cand, slots)
    else:
        send_rejection_email(db, cand, stage="Assessment")

    # Notify recruiter
    from models import User
    owner = db.query(User).filter(User.id == cand.owner_id).first()
    if owner:
        event = "Assessment PASSED" if result["decision"] == "PASS" else "Assessment FAILED"
        send_recruiter_notification(db, owner.email, cand, event)

    db.commit()

    return result
