import json
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from database import get_db
from models import User, Candidate, PipelineLog, EmailLog, CustomAssessment, AssessmentCredential, AppSetting
from auth.utils import require_auth
from config import settings as app_settings

router = APIRouter(prefix="/api/settings", tags=["Settings"])


def _get_user(request: Request, db: Session) -> User:
    user_data = require_auth(request)
    user = db.query(User).filter(User.id == int(user_data["sub"])).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ── Schemas ────────────────────────────────────────────────────
class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    company_name: Optional[str] = None
    phone_number: Optional[str] = None

class ChangePassword(BaseModel):
    current_password: str
    new_password: str

class SMTPSettings(BaseModel):
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_name: str = "TalentEdge Recruitment"

class DeleteAccount(BaseModel):
    password: str


# ── Password helpers ───────────────────────────────────────────
try:
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    def verify_password(plain, hashed):
        return pwd_context.verify(plain, hashed)
    def hash_password(plain):
        return pwd_context.hash(plain)
except ImportError:
    import bcrypt
    def verify_password(plain, hashed):
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    def hash_password(plain):
        return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


# ── 1. Get Profile ────────────────────────────────────────────
@router.get("/profile")
def get_profile(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "company_name": user.company_name,
        "phone_number": user.phone_number or "",
        "role": user.role,
        "created_at": str(user.created_at) if user.created_at else "",
    }


# ── 2. Update Profile ─────────────────────────────────────────
@router.patch("/profile")
def update_profile(data: ProfileUpdate, request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    if data.full_name is not None:
        user.full_name = data.full_name.strip()
    if data.company_name is not None:
        user.company_name = data.company_name.strip()
    if data.phone_number is not None:
        user.phone_number = data.phone_number.strip()
    db.commit()
    return {"message": "Profile updated successfully"}


# ── 3. Change Password ────────────────────────────────────────
@router.post("/change-password")
def change_password(data: ChangePassword, request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    if not verify_password(data.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")
    if data.current_password == data.new_password:
        raise HTTPException(status_code=400, detail="New password must be different from current")
    user.hashed_password = hash_password(data.new_password)
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()
    return {"message": "Password changed successfully"}


# ── 4. Get SMTP Settings ──────────────────────────────────────
@router.get("/smtp")
def get_smtp_settings(request: Request, db: Session = Depends(get_db)):
    _get_user(request, db)
    keys = ["smtp_host", "smtp_port", "smtp_user", "smtp_password", "smtp_from_name"]
    defaults = {
        "smtp_host": app_settings.SMTP_HOST, "smtp_port": str(app_settings.SMTP_PORT),
        "smtp_user": app_settings.SMTP_USER, "smtp_password": app_settings.SMTP_PASSWORD,
        "smtp_from_name": app_settings.SMTP_FROM_NAME,
    }
    result = {}
    for key in keys:
        row = db.query(AppSetting).filter(AppSetting.key == key).first()
        result[key] = row.value if row else defaults.get(key, "")

    # Mask password
    pw = result.get("smtp_password", "")
    if pw and len(pw) > 6:
        result["smtp_password_masked"] = pw[:3] + "•" * (len(pw) - 6) + pw[-3:]
    else:
        result["smtp_password_masked"] = "•" * len(pw) if pw else ""
    result.pop("smtp_password", None)
    return result


# ── 5. Save SMTP Settings ─────────────────────────────────────
@router.post("/smtp")
def save_smtp_settings(data: SMTPSettings, request: Request, db: Session = Depends(get_db)):
    _get_user(request, db)
    settings_map = {
        "smtp_host": data.smtp_host, "smtp_port": str(data.smtp_port),
        "smtp_user": data.smtp_user, "smtp_password": data.smtp_password,
        "smtp_from_name": data.smtp_from_name,
    }
    for key, value in settings_map.items():
        row = db.query(AppSetting).filter(AppSetting.key == key).first()
        if row:
            row.value = value
        else:
            db.add(AppSetting(key=key, value=value))
    db.commit()

    # Update runtime
    app_settings.SMTP_HOST = data.smtp_host
    app_settings.SMTP_PORT = data.smtp_port
    app_settings.SMTP_USER = data.smtp_user
    app_settings.SMTP_PASSWORD = data.smtp_password
    app_settings.SMTP_FROM_NAME = data.smtp_from_name
    return {"message": "SMTP settings saved successfully"}


# ── 6. Test SMTP ──────────────────────────────────────────────
@router.post("/smtp/test")
def test_smtp(request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    from services.email_service import _send_smtp, _email_wrap
    from datetime import datetime
    html = _email_wrap("✅", "SMTP Test Successful", f"""
<h3>Hello {user.full_name},</h3>
<p>This is a test email from <strong>TalentEdge AI</strong>.</p>
<p>Your email configuration is working correctly! 🎉</p>
<p style="color:#64748B;font-size:.85rem">Sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
""")
    ok, detail = _send_smtp(user.email, "TalentEdge — SMTP Test Email", html)
    if ok:
        return {"message": f"Test email sent to {user.email}", "status": "success"}
    else:
        raise HTTPException(status_code=500, detail=f"Email failed: {detail}")


# ── 7. Delete Account ─────────────────────────────────────────
@router.delete("/account")
def delete_account(data: DeleteAccount, request: Request, db: Session = Depends(get_db)):
    user = _get_user(request, db)
    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect password")

    candidates = db.query(Candidate).filter(Candidate.owner_id == user.id).all()
    candidate_ids = [c.id for c in candidates]
    if candidate_ids:
        db.query(PipelineLog).filter(PipelineLog.candidate_db_id.in_(candidate_ids)).delete(synchronize_session=False)
        db.query(EmailLog).filter(EmailLog.candidate_db_id.in_(candidate_ids)).delete(synchronize_session=False)
        db.query(AssessmentCredential).filter(
            AssessmentCredential.candidate_id.in_([c.candidate_id for c in candidates])
        ).delete(synchronize_session=False)
    db.query(Candidate).filter(Candidate.owner_id == user.id).delete(synchronize_session=False)
    db.query(CustomAssessment).filter(CustomAssessment.created_by_id == user.id).delete(synchronize_session=False)
    db.delete(user)
    db.commit()
    return {"message": "Account deleted successfully"}