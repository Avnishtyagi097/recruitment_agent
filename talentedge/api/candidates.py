import json
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from sqlalchemy.orm import Session
from database import get_db
from models import Candidate, PipelineLog, User
from auth.utils import require_auth
from services.cv_parser import parse_cv, extract_email, extract_name
from services.ats_engine import calculate_ats_score
from api.schemas import ATSRequest, ATSResponse, CandidateResponse, CandidateListResponse

router = APIRouter(prefix="/api/candidates", tags=["Candidates"])


def _get_user(request: Request, db: Session) -> User:
    user_data = require_auth(request)
    user = db.query(User).filter(User.id == int(user_data["sub"])).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/upload-cv")
async def upload_cv(
    request: Request,
    file: UploadFile = File(...),
    role_applied: str = Form(...),
    jd_text: str = Form(...),
    db: Session = Depends(get_db),
):
    """Upload a CV file, parse it, run ATS scoring, and create candidate."""
    user = _get_user(request, db)
    file_bytes = await file.read()
    cv_text = parse_cv(file_bytes, file.filename)

    if not cv_text:
        raise HTTPException(status_code=400, detail="Could not extract text from CV")

    name = extract_name(cv_text) or file.filename.rsplit(".", 1)[0].replace("_", " ").title()
    email = extract_email(cv_text)

    ats = calculate_ats_score(cv_text, jd_text)

    cand_id = f"CAND-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    status = "Passed ATS" if ats["decision"] == "PASS" else ("Manual Review" if ats["requires_review"] else "Failed ATS")

    candidate = Candidate(
        candidate_id=cand_id, owner_id=user.id,
        name=name, email=email, role_applied=role_applied,
        cv_text=cv_text[:1000],
        ats_score=ats["ats_score"], ats_decision=ats["decision"],
        ats_result_json=json.dumps(ats), status=status,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    # Log
    log = PipelineLog(
        candidate_db_id=candidate.id, candidate_id=cand_id,
        stage="ATS_SCREENING", decision=ats["decision"],
        score=str(ats["ats_score"]), reason=ats["reasoning"],
        next_action="Send Assessment" if ats["decision"] == "PASS" else "Send Rejection",
    )
    db.add(log)
    db.commit()

    db.add(log)
    db.commit()

    # ═══ AUTO EMAIL BASED ON ATS RESULT ═══
    from services.email_service import send_assessment_invitation, send_rejection_email, send_recruiter_notification
    from models import User

    owner = db.query(User).filter(User.id == user.id).first()

    if ats["decision"] == "PASS":
        send_assessment_invitation(db, candidate)
        if owner:
            send_recruiter_notification(db, owner.email, candidate, "ATS PASSED — Assessment Sent")

    elif not ats["requires_review"]:
        send_rejection_email(db, candidate, stage="ATS")
        if owner:
            send_recruiter_notification(db, owner.email, candidate, "ATS FAILED — Rejected")
    # ═══ END EMAIL AUTOMATION ═══

    return {
        "candidate_id": cand_id, "name": name, "email": email,
        "status": status, "ats": ats,
    }


# ═══════════════════════════════════════════════════════════════
#  BATCH CV UPLOAD — Process multiple CVs in one request
# ═══════════════════════════════════════════════════════════════
@router.post("/upload-batch")
async def upload_batch(
    request: Request,
    files: List[UploadFile] = File(...),
    role_applied: str = Form(...),
    jd_text: str = Form(...),
    db: Session = Depends(get_db),
):
    """Upload multiple CVs at once. Each file is parsed, ATS-scored, and emailed independently."""
    user = _get_user(request, db)
    owner = db.query(User).filter(User.id == user.id).first()

    from services.email_service import send_assessment_invitation, send_rejection_email, send_recruiter_notification

    results = []
    counters = {"processed": 0, "errors": 0, "passed_ats": 0, "failed_ats": 0, "manual_review": 0}
    batch_ts = datetime.now().strftime("%Y%m%d%H%M%S")

    for idx, file in enumerate(files, start=1):
        filename = file.filename or f"file_{idx}"
        try:
            file_bytes = await file.read()
            cv_text = parse_cv(file_bytes, filename)

            if not cv_text:
                results.append({"file": filename, "success": False, "detail": "Could not extract text from CV"})
                counters["errors"] += 1
                continue

            name = extract_name(cv_text) or filename.rsplit(".", 1)[0].replace("_", " ").title()
            email = extract_email(cv_text)
            ats = calculate_ats_score(cv_text, jd_text)

            cand_id = f"CAND-{batch_ts}-{idx:03d}"
            status = (
                "Passed ATS" if ats["decision"] == "PASS"
                else ("Manual Review" if ats["requires_review"] else "Failed ATS")
            )

            candidate = Candidate(
                candidate_id=cand_id, owner_id=user.id,
                name=name, email=email, role_applied=role_applied,
                cv_text=cv_text[:1000],
                ats_score=ats["ats_score"], ats_decision=ats["decision"],
                ats_result_json=json.dumps(ats), status=status,
            )
            db.add(candidate)
            db.commit()
            db.refresh(candidate)

            log = PipelineLog(
                candidate_db_id=candidate.id, candidate_id=cand_id,
                stage="ATS_SCREENING", decision=ats["decision"],
                score=str(ats["ats_score"]), reason=ats["reasoning"],
                next_action="Send Assessment" if ats["decision"] == "PASS" else "Send Rejection",
            )
            db.add(log)
            db.commit()

            # Auto-email per candidate
            if ats["decision"] == "PASS":
                send_assessment_invitation(db, candidate)
                if owner:
                    send_recruiter_notification(db, owner.email, candidate, "ATS PASSED — Assessment Sent")
                counters["passed_ats"] += 1
            elif ats["requires_review"]:
                counters["manual_review"] += 1
            else:
                send_rejection_email(db, candidate, stage="ATS")
                if owner:
                    send_recruiter_notification(db, owner.email, candidate, "ATS FAILED — Rejected")
                counters["failed_ats"] += 1

            counters["processed"] += 1
            results.append({
                "file": filename, "success": True,
                "candidate_id": cand_id, "name": name, "email": email,
                "ats_score": ats["ats_score"], "ats_decision": ats["decision"], "status": status,
            })

        except Exception as e:
            db.rollback()
            results.append({"file": filename, "success": False, "detail": str(e)})
            counters["errors"] += 1

    return {
        "total": len(files),
        **counters,
        "results": results,
    }


@router.post("/ats-score", response_model=ATSResponse)
def run_ats(data: ATSRequest, request: Request, db: Session = Depends(get_db)):
    """Run ATS scoring on provided CV text and JD."""
    user = _get_user(request, db)
    ats = calculate_ats_score(data.cv_text, data.jd_text)

    cand_id = data.candidate_id or f"CAND-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    status = "Passed ATS" if ats["decision"] == "PASS" else ("Manual Review" if ats["requires_review"] else "Failed ATS")

    candidate = Candidate(
        candidate_id=cand_id, owner_id=user.id,
        name=data.name, email=data.email, role_applied=data.role_applied,
        cv_text=data.cv_text[:1000],
        ats_score=ats["ats_score"], ats_decision=ats["decision"],
        ats_result_json=json.dumps(ats), status=status,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    log = PipelineLog(
        candidate_db_id=candidate.id, candidate_id=cand_id,
        stage="ATS_SCREENING", decision=ats["decision"],
        score=str(ats["ats_score"]), reason=ats["reasoning"],
        next_action="Send Assessment" if ats["decision"] == "PASS" else "Send Rejection",
    )
    db.add(log)
    db.commit()

    # ═══ AUTO EMAIL ═══
    from services.email_service import send_assessment_invitation, send_rejection_email, send_recruiter_notification

    if ats["decision"] == "PASS":
        send_assessment_invitation(db, candidate)
        send_recruiter_notification(db, user.email, candidate, "ATS PASSED — Assessment Sent")
    elif not ats["requires_review"]:
        send_rejection_email(db, candidate, stage="ATS")
        send_recruiter_notification(db, user.email, candidate, "ATS FAILED — Rejected")

    return ATSResponse(candidate_id=cand_id, **ats)


@router.get("/", response_model=CandidateListResponse)
def list_candidates(request: Request, db: Session = Depends(get_db)):
    """List all candidates for the current user (multi-tenant)."""
    user = _get_user(request, db)
    candidates = db.query(Candidate).filter(Candidate.owner_id == user.id).order_by(Candidate.created_at.desc()).all()
    return CandidateListResponse(total=len(candidates), candidates=candidates)


@router.get("/{candidate_id}", response_model=CandidateResponse)
def get_candidate(candidate_id: str, request: Request, db: Session = Depends(get_db)):
    """Get a single candidate by ID."""
    user = _get_user(request, db)
    cand = db.query(Candidate).filter(
        Candidate.candidate_id == candidate_id, Candidate.owner_id == user.id
    ).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return cand


@router.patch("/{candidate_id}/status")
def update_status(candidate_id: str, status: str, request: Request, db: Session = Depends(get_db)):
    """Update candidate status (approve/reject for manual review)."""
    user = _get_user(request, db)
    cand = db.query(Candidate).filter(
        Candidate.candidate_id == candidate_id, Candidate.owner_id == user.id
    ).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found")
    cand.status = status
    if status == "Assessment Sent":
        cand.ats_decision = "PASS"
    elif status == "Failed ATS":
        cand.ats_decision = "FAIL"
    db.commit()

    log = PipelineLog(
        candidate_db_id=cand.id, candidate_id=candidate_id,
        stage="RECRUITER_OVERRIDE", decision="PASS" if "Sent" in status else "FAIL",
        reason=f"Recruiter set status to {status}", owner="RECRUITER",
    )
    db.add(log)
    db.commit()

    # Email on status change
    from services.email_service import send_assessment_invitation, send_rejection_email
    if status == "Assessment Sent":
        send_assessment_invitation(db, cand)
    elif status == "Failed ATS":
        send_rejection_email(db, cand, stage="ATS")

    return {"message": f"Status updated to {status}"}
