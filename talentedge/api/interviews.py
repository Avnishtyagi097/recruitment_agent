import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session
from database import get_db
from models import Candidate, PipelineLog, User
from auth.utils import require_auth

router = APIRouter(prefix="/api/interviews", tags=["Interviews"])


def _get_user(request: Request, db: Session) -> User:
    user_data = require_auth(request)
    user = db.query(User).filter(User.id == int(user_data["sub"])).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ── Schemas ────────────────────────────────────────────────────
class PanelMember(BaseModel):
    name: str
    email: str
    role: str = "Interviewer"

class ScheduleRequest(BaseModel):
    candidate_id: str
    slots: List[str]
    panel: List[PanelMember]
    notes: Optional[str] = ""
    duration_minutes: int = 45

class ConfirmRequest(BaseModel):
    confirmed_slot: str
    meeting_link: Optional[str] = ""


# ── 1. Eligible candidates (Passed Assessment) ────────────────
@router.get("/eligible")
def get_eligible_candidates(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    candidates = (
        db.query(Candidate)
        .filter(
            Candidate.owner_id == user.id,
            Candidate.status == "Passed Assessment",
            Candidate.interview_scheduled == False,
        )
        .order_by(Candidate.updated_at.desc())
        .all()
    )
    return {
        "total": len(candidates),
        "candidates": [
            {
                "candidate_id": c.candidate_id,
                "name": c.name,
                "email": c.email,
                "role_applied": c.role_applied,
                "ats_score": c.ats_score,
                "assessment_score": c.assessment_score,
                "status": c.status,
            }
            for c in candidates
        ],
    }


# ── 2. Schedule interview ─────────────────────────────────────
@router.post("/schedule")
def schedule_interview(
    data: ScheduleRequest, request: Request, db: Session = Depends(get_db)
):
    user = _get_user(request, db)

    candidate = (
        db.query(Candidate)
        .filter(Candidate.candidate_id == data.candidate_id, Candidate.owner_id == user.id)
        .first()
    )
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if candidate.interview_scheduled:
        raise HTTPException(status_code=400, detail="Interview already scheduled")
    if len(data.slots) == 0:
        raise HTTPException(status_code=400, detail="At least one time slot required")
    if len(data.panel) == 0:
        raise HTTPException(status_code=400, detail="At least one panel member required")

    interview_data = {
        "slots": data.slots,
        "duration_minutes": data.duration_minutes,
        "notes": data.notes,
        "scheduled_at": datetime.now().isoformat(),
        "confirmed_slot": None,
        "meeting_link": "",
    }
    panel_data = [p.dict() for p in data.panel]

    candidate.interview_scheduled = True
    candidate.interview_slots_json = json.dumps(interview_data)
    candidate.interview_panel_json = json.dumps(panel_data)
    candidate.status = "Interview Scheduled"
    db.commit()

    log = PipelineLog(
        candidate_db_id=candidate.id,
        candidate_id=candidate.candidate_id,
        stage="INTERVIEW_SCHEDULING",
        decision="SCHEDULED",
        score=str(candidate.assessment_score or ""),
        reason=f"Interview scheduled with {len(data.panel)} panel member(s). Slots: {len(data.slots)}",
        next_action="Confirm interview slot",
    )
    db.add(log)
    db.commit()

    try:
        from services.email_service import send_interview_invitation, send_recruiter_notification
        send_interview_invitation(db, candidate, data.slots)
        send_recruiter_notification(db, user.email, candidate, "Interview Scheduled")
    except Exception:
        pass

    return {
        "message": f"Interview scheduled for {candidate.name}",
        "candidate_id": candidate.candidate_id,
        "slots": data.slots,
        "panel": panel_data,
        "status": "Interview Scheduled",
    }


# ── 3. List all scheduled interviews ──────────────────────────
@router.get("/")
def list_interviews(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    candidates = (
        db.query(Candidate)
        .filter(Candidate.owner_id == user.id, Candidate.interview_scheduled == True)
        .order_by(Candidate.updated_at.desc())
        .all()
    )

    interviews = []
    for c in candidates:
        slots_data = json.loads(c.interview_slots_json) if c.interview_slots_json else {}
        panel_data = json.loads(c.interview_panel_json) if c.interview_panel_json else []
        interviews.append({
            "candidate_id": c.candidate_id,
            "name": c.name,
            "email": c.email,
            "role_applied": c.role_applied,
            "ats_score": c.ats_score,
            "assessment_score": c.assessment_score,
            "status": c.status,
            "slots": slots_data.get("slots", []),
            "duration_minutes": slots_data.get("duration_minutes", 45),
            "notes": slots_data.get("notes", ""),
            "confirmed_slot": slots_data.get("confirmed_slot"),
            "meeting_link": slots_data.get("meeting_link", ""),
            "scheduled_at": slots_data.get("scheduled_at", ""),
            "panel": panel_data,
        })

    return {"total": len(interviews), "interviews": interviews}


# ── 4. Confirm a slot ─────────────────────────────────────────
@router.patch("/{candidate_id}/confirm")
def confirm_interview(
    candidate_id: str, data: ConfirmRequest, request: Request, db: Session = Depends(get_db)
):
    user = _get_user(request, db)
    candidate = (
        db.query(Candidate)
        .filter(Candidate.candidate_id == candidate_id, Candidate.owner_id == user.id)
        .first()
    )
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if not candidate.interview_scheduled:
        raise HTTPException(status_code=400, detail="No interview scheduled")

    slots_data = json.loads(candidate.interview_slots_json) if candidate.interview_slots_json else {}
    slots_data["confirmed_slot"] = data.confirmed_slot
    slots_data["meeting_link"] = data.meeting_link or ""
    candidate.interview_slots_json = json.dumps(slots_data)
    candidate.status = "Interview Confirmed"
    db.commit()

    log = PipelineLog(
        candidate_db_id=candidate.id,
        candidate_id=candidate.candidate_id,
        stage="INTERVIEW_CONFIRMED",
        decision="CONFIRMED",
        reason=f"Confirmed slot: {data.confirmed_slot}",
        next_action="Conduct interview",
        owner="RECRUITER",
    )
    db.add(log)
    db.commit()

    return {"message": f"Interview confirmed for {candidate.name}", "confirmed_slot": data.confirmed_slot}


# ── 5. Cancel interview ───────────────────────────────────────
@router.delete("/{candidate_id}/cancel")
def cancel_interview(candidate_id: str, request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    candidate = (
        db.query(Candidate)
        .filter(Candidate.candidate_id == candidate_id, Candidate.owner_id == user.id)
        .first()
    )
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if not candidate.interview_scheduled:
        raise HTTPException(status_code=400, detail="No interview scheduled")

    candidate.interview_scheduled = False
    candidate.interview_slots_json = None
    candidate.interview_panel_json = None
    candidate.status = "Passed Assessment"
    db.commit()

    log = PipelineLog(
        candidate_db_id=candidate.id,
        candidate_id=candidate.candidate_id,
        stage="INTERVIEW_CANCELLED",
        decision="CANCELLED",
        reason="Interview cancelled by recruiter",
        next_action="Reschedule or review",
        owner="RECRUITER",
    )
    db.add(log)
    db.commit()

    return {"message": f"Interview cancelled for {candidate.name}"}


# ── 6. Mark interview result (Hired / Rejected) ───────────────
@router.patch("/{candidate_id}/result")
def interview_result(
    candidate_id: str, decision: str, request: Request, db: Session = Depends(get_db)
):
    user = _get_user(request, db)
    if decision not in ("Hired", "Rejected"):
        raise HTTPException(status_code=400, detail="Decision must be 'Hired' or 'Rejected'")

    candidate = (
        db.query(Candidate)
        .filter(Candidate.candidate_id == candidate_id, Candidate.owner_id == user.id)
        .first()
    )
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    candidate.status = decision
    db.commit()

    log = PipelineLog(
        candidate_db_id=candidate.id,
        candidate_id=candidate.candidate_id,
        stage="INTERVIEW_RESULT",
        decision=decision.upper(),
        reason=f"Candidate {decision.lower()} after interview",
        next_action="Send offer" if decision == "Hired" else "Archive",
        owner="RECRUITER",
    )
    db.add(log)
    db.commit()

    return {"message": f"Candidate marked as {decision}"}