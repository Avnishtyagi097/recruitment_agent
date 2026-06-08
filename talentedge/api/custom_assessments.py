import json
import csv
import io
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from sqlalchemy.orm import Session
from database import get_db
from models import CustomAssessment, Candidate, User
from auth.utils import require_auth

router = APIRouter(prefix="/api/custom-assessments", tags=["Custom Assessments"])


def _get_user(request: Request, db: Session) -> User:
    user_data = require_auth(request)
    user = db.query(User).filter(User.id == int(user_data["sub"])).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _validate_questions(questions: list) -> list:
    """Validate question format. Returns cleaned questions or raises error."""
    if not isinstance(questions, list) or len(questions) == 0:
        raise HTTPException(status_code=400, detail="Questions must be a non-empty list")
    
    cleaned = []
    for i, q in enumerate(questions):
        if not isinstance(q, dict):
            raise HTTPException(status_code=400, detail=f"Question {i+1} must be an object")
        if "q" not in q or "options" not in q or "answer" not in q:
            raise HTTPException(status_code=400, detail=f"Question {i+1} missing required fields: q, options, answer")
        if not isinstance(q["options"], list) or len(q["options"]) != 4:
            raise HTTPException(status_code=400, detail=f"Question {i+1} must have exactly 4 options")
        if not isinstance(q["answer"], int) or q["answer"] not in [0, 1, 2, 3]:
            raise HTTPException(status_code=400, detail=f"Question {i+1} answer must be 0, 1, 2, or 3")
        cleaned.append({
            "q": str(q["q"]),
            "options": [str(o) for o in q["options"]],
            "answer": int(q["answer"]),
            "topic": str(q.get("topic", "General")),
            "difficulty": str(q.get("difficulty", "medium")),
        })
    return cleaned


@router.post("/upload-json")
async def upload_json(
    request: Request,
    file: UploadFile = File(...),
    role: str = Form("General"),
    candidate_id: str = Form(None),
    duration_minutes: int = Form(20),
    db: Session = Depends(get_db),
):
    """Upload a JSON file containing assessment questions."""
    user = _get_user(request, db)
    
    content = await file.read()
    try:
        questions = json.loads(content.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON file")
    
    cleaned = _validate_questions(questions)
    
    assessment = CustomAssessment(
        candidate_id=candidate_id,
        role=role,
        questions_json=json.dumps(cleaned),
        duration_minutes=duration_minutes,
        created_by_id=user.id,
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    
    return {
        "id": assessment.id,
        "questions_count": len(cleaned),
        "role": role,
        "candidate_id": candidate_id,
        "duration_minutes": duration_minutes,
        "message": f"Uploaded {len(cleaned)} questions successfully",
    }


@router.post("/upload-csv")
async def upload_csv(
    request: Request,
    file: UploadFile = File(...),
    role: str = Form("General"),
    candidate_id: str = Form(None),
    duration_minutes: int = Form(20),
    db: Session = Depends(get_db),
):
    """Upload a CSV file containing assessment questions.
    Columns: question, option_a, option_b, option_c, option_d, correct_answer (A/B/C/D), topic, difficulty
    """
    user = _get_user(request, db)
    
    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid CSV file encoding")
    
    reader = csv.DictReader(io.StringIO(text))
    required = {"question", "option_a", "option_b", "option_c", "option_d", "correct_answer"}
    
    if not required.issubset(set(reader.fieldnames or [])):
        missing = required - set(reader.fieldnames or [])
        raise HTTPException(status_code=400, detail=f"Missing CSV columns: {', '.join(missing)}")
    
    answer_map = {"A": 0, "B": 1, "C": 2, "D": 3, "a": 0, "b": 1, "c": 2, "d": 3}
    questions = []
    for i, row in enumerate(reader):
        ans = answer_map.get(row["correct_answer"].strip())
        if ans is None:
            raise HTTPException(status_code=400, detail=f"Row {i+2}: correct_answer must be A, B, C, or D")
        questions.append({
            "q": row["question"],
            "options": [row["option_a"], row["option_b"], row["option_c"], row["option_d"]],
            "answer": ans,
            "topic": row.get("topic", "General"),
            "difficulty": row.get("difficulty", "medium"),
        })
    
    if not questions:
        raise HTTPException(status_code=400, detail="CSV has no data rows")
    
    assessment = CustomAssessment(
        candidate_id=candidate_id,
        role=role,
        questions_json=json.dumps(questions),
        duration_minutes=duration_minutes,
        created_by_id=user.id,
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    
    return {
        "id": assessment.id,
        "questions_count": len(questions),
        "role": role,
        "candidate_id": candidate_id,
        "duration_minutes": duration_minutes,
        "message": f"Uploaded {len(questions)} questions from CSV",
    }


@router.post("/add-question")
def add_question(
    request: Request,
    question: str = Form(...),
    option_a: str = Form(...),
    option_b: str = Form(...),
    option_c: str = Form(...),
    option_d: str = Form(...),
    correct_answer: str = Form(...),
    topic: str = Form("General"),
    difficulty: str = Form("medium"),
    assessment_id: int = Form(None),
    role: str = Form("General"),
    candidate_id: str = Form(None),
    db: Session = Depends(get_db),
):
    """Add a single question manually. If assessment_id is provided, append to existing."""
    user = _get_user(request, db)
    
    answer_map = {"A": 0, "B": 1, "C": 2, "D": 3}
    ans = answer_map.get(correct_answer.strip().upper())
    if ans is None:
        raise HTTPException(status_code=400, detail="correct_answer must be A, B, C, or D")
    
    new_q = {
        "q": question, "options": [option_a, option_b, option_c, option_d],
        "answer": ans, "topic": topic, "difficulty": difficulty,
    }
    
    if assessment_id:
        # Append to existing assessment
        assessment = db.query(CustomAssessment).filter(
            CustomAssessment.id == assessment_id, CustomAssessment.created_by_id == user.id
        ).first()
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")
        existing = json.loads(assessment.questions_json) if assessment.questions_json else []
        existing.append(new_q)
        assessment.questions_json = json.dumps(existing)
        db.commit()
        return {"message": f"Question added. Total: {len(existing)}", "assessment_id": assessment_id, "count": len(existing)}
    else:
        # Create new assessment with this one question
        assessment = CustomAssessment(
            candidate_id=candidate_id, role=role,
            questions_json=json.dumps([new_q]),
            duration_minutes=20, created_by_id=user.id,
        )
        db.add(assessment)
        db.commit()
        db.refresh(assessment)
        return {"message": "Question added. New assessment created.", "assessment_id": assessment.id, "count": 1}


@router.get("/")
def list_assessments(request: Request, db: Session = Depends(get_db)):
    """List all custom assessments for current user."""
    user = _get_user(request, db)
    items = db.query(CustomAssessment).filter(CustomAssessment.created_by_id == user.id).order_by(CustomAssessment.id.desc()).all()
    result = []
    for a in items:
        qs = json.loads(a.questions_json) if a.questions_json else []
        result.append({
            "id": a.id, "role": a.role, "candidate_id": a.candidate_id,
            "questions_count": len(qs), "duration_minutes": a.duration_minutes,
            "created_at": str(a.created_at) if a.created_at else "",
        })
    return {"assessments": result}


@router.get("/{assessment_id}")
def get_assessment(assessment_id: int, request: Request, db: Session = Depends(get_db)):
    """Get a specific custom assessment with all questions."""
    user = _get_user(request, db)
    a = db.query(CustomAssessment).filter(CustomAssessment.id == assessment_id, CustomAssessment.created_by_id == user.id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Assessment not found")
    qs = json.loads(a.questions_json) if a.questions_json else []
    return {
        "id": a.id, "role": a.role, "candidate_id": a.candidate_id,
        "questions": qs, "duration_minutes": a.duration_minutes,
        "created_at": str(a.created_at) if a.created_at else "",
    }


@router.delete("/{assessment_id}")
def delete_assessment(assessment_id: int, request: Request, db: Session = Depends(get_db)):
    """Delete a custom assessment."""
    user = _get_user(request, db)
    a = db.query(CustomAssessment).filter(CustomAssessment.id == assessment_id, CustomAssessment.created_by_id == user.id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Assessment not found")
    db.delete(a)
    db.commit()
    return {"message": "Assessment deleted"}
