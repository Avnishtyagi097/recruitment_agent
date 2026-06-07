from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from database import get_db
from models import EmailLog, User
from auth.utils import require_auth

router = APIRouter(prefix="/api/emails", tags=["Email Logs"])


@router.get("/")
def get_email_logs(request: Request, db: Session = Depends(get_db)):
    user_data = require_auth(request)
    user = db.query(User).filter(User.id == int(user_data["sub"])).first()
    if not user:
        return {"emails": []}
    # Get emails for this user's candidates
    from models import Candidate
    cand_ids = [c.id for c in db.query(Candidate).filter(Candidate.owner_id == user.id).all()]
    logs = db.query(EmailLog).filter(EmailLog.candidate_db_id.in_(cand_ids)).order_by(EmailLog.sent_at.desc()).all()
    return {"emails": [{"id": l.id, "to": l.to_email, "subject": l.subject,
             "type": l.email_type, "status": l.status, "detail": l.detail,
             "sent_at": str(l.sent_at) if l.sent_at else ""} for l in logs]}
