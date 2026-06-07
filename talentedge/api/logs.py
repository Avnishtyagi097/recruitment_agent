from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from database import get_db
from models import PipelineLog, Candidate, User
from auth.utils import require_auth

router = APIRouter(prefix="/api/logs", tags=["Pipeline Logs"])


@router.get("/")
def get_logs(request: Request, db: Session = Depends(get_db)):
    user_data = require_auth(request)
    user = db.query(User).filter(User.id == int(user_data["sub"])).first()
    if not user:
        return {"logs": []}
    cand_ids = [c.id for c in db.query(Candidate).filter(Candidate.owner_id == user.id).all()]
    logs = db.query(PipelineLog).filter(PipelineLog.candidate_db_id.in_(cand_ids)).order_by(PipelineLog.id.desc()).all()
    return {"logs": [{"id": l.id, "candidate_id": l.candidate_id,
             "stage": l.stage, "decision": l.decision, "score": l.score,
             "reason": l.reason, "next_action": l.next_action, "owner": l.owner,
             "timestamp": str(l.timestamp) if l.timestamp else ""} for l in logs]}


@router.get("/{candidate_id}")
def get_candidate_logs(candidate_id: str, request: Request, db: Session = Depends(get_db)):
    user_data = require_auth(request)
    logs = db.query(PipelineLog).filter(PipelineLog.candidate_id == candidate_id).order_by(PipelineLog.id.desc()).all()
    return {"logs": [{"id": l.id, "candidate_id": l.candidate_id,
             "stage": l.stage, "decision": l.decision, "score": l.score,
             "reason": l.reason, "next_action": l.next_action, "owner": l.owner,
             "timestamp": str(l.timestamp) if l.timestamp else ""} for l in logs]}
