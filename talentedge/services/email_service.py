import smtplib
import json
import secrets
import string
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from models import EmailLog, AssessmentCredential, Candidate
from config import settings


def _send_smtp(to_email: str, subject: str, html: str) -> tuple:
    """Send HTML email via SMTP. Returns (success, detail)."""
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        return False, "SMTP not configured"
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_USER}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(html, "html", "utf-8"))
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as s:
            s.ehlo(); s.starttls(); s.ehlo()
            s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            s.sendmail(settings.SMTP_USER, to_email, msg.as_string())
        return True, "Sent successfully"
    except Exception as e:
        return False, str(e)


def _log_email(db: Session, candidate_db_id, to_email, subject, email_type, status, detail):
    log = EmailLog(
        candidate_db_id=candidate_db_id, to_email=to_email,
        subject=subject, email_type=email_type,
        status=status, detail=detail,
    )
    db.add(log)
    db.commit()
    return log


def _generate_password(length=10):
    chars = string.ascii_letters + string.digits + "!@#$%"
    pw = [random.choice(string.ascii_uppercase), random.choice(string.ascii_lowercase),
          random.choice(string.digits), random.choice("!@#$%")]
    pw += [random.choice(chars) for _ in range(length - 4)]
    random.shuffle(pw)
    return "".join(pw)


def _email_wrap(title_emoji, title, body_html):
    return f"""
    <div style="font-family:Inter,Arial,sans-serif;max-width:600px;margin:0 auto;background:#f8fafc;border-radius:16px;overflow:hidden">
        <div style="background:linear-gradient(135deg,#4F46E5,#7C3AED);padding:35px 30px;text-align:center">
            <h1 style="color:white;margin:0;font-size:24px">{title_emoji} {title}</h1>
            <p style="color:#C7D2FE;margin-top:8px;font-size:14px">TalentEdge AI Recruitment Platform</p>
        </div>
        <div style="padding:30px">{body_html}</div>
        <div style="padding:15px 30px;border-top:1px solid #E2E8F0;text-align:center;color:#94A3B8;font-size:12px">
            &copy; 2025 TalentEdge AI. All rights reserved.
        </div>
    </div>"""


def send_assessment_invitation(db: Session, candidate: Candidate):
    """Send assessment link + credentials to candidate. Returns token."""
    if not candidate.email:
        _log_email(db, candidate.id, "", "Assessment Invitation", "Assessment Invitation", "FAILED", "No email")
        return None

    token = secrets.token_hex(8)
    username = candidate.name.lower().replace(" ", ".") + f".{random.randint(100,999)}"
    password = _generate_password()

    # Store credentials
    cred = AssessmentCredential(
        token=token, username=username, password=password,
        candidate_id=candidate.candidate_id, candidate_name=candidate.name,
    )
    db.add(cred)
    db.commit()

    link = f"{settings.APP_URL}/assess?token={token}"
    deadline = (datetime.now() + timedelta(days=2)).strftime("%B %d, %Y")
    duration = candidate.assessment_duration_mins or 20

    html = _email_wrap("\U0001f4dd", "Assessment Invitation", f"""
        <h2 style="color:#1E293B;margin-top:0">Hi {candidate.name},</h2>
        <p style="color:#64748B;line-height:1.7">Thank you for applying for the <strong>{candidate.role_applied}</strong> role.
        We'd like you to complete an online assessment.</p>
        <div style="background:#EEF2FF;border:2px solid #C7D2FE;border-radius:12px;padding:20px;margin:20px 0">
            <p style="margin:0 0 8px;font-weight:700;color:#4F46E5">Assessment Details:</p>
            <p style="margin:4px 0;color:#334155">\u2022 Duration: <strong>{duration} minutes</strong></p>
            <p style="margin:4px 0;color:#334155">\u2022 Deadline: <strong>{deadline}</strong></p>
            <p style="margin:4px 0;color:#334155">\u2022 Complete in one sitting</p>
        </div>
        <div style="background:#F0FDF4;border:2px solid #BBF7D0;border-radius:12px;padding:20px;margin:20px 0">
            <p style="margin:0 0 8px;font-weight:700;color:#065F46">Your Login Credentials:</p>
            <p style="margin:4px 0;color:#334155">\U0001f464 Username: <strong>{username}</strong></p>
            <p style="margin:4px 0;color:#334155">\U0001f511 Password: <strong>{password}</strong></p>
        </div>
        <div style="text-align:center;margin:25px 0">
            <a href="{link}" style="background:linear-gradient(135deg,#4F46E5,#7C3AED);color:white;padding:14px 40px;border-radius:12px;text-decoration:none;font-weight:700;font-size:16px;display:inline-block">Start Assessment</a>
        </div>
        <div style="background:#FEF3C7;border:1px solid #FDE68A;border-radius:8px;padding:12px;margin:15px 0">
            <p style="color:#92400E;margin:0;font-size:13px">\u26a0 Do NOT share your credentials. Tab switching is monitored.</p>
        </div>
        <p style="color:#94A3B8;font-size:12px;word-break:break-all">Direct link: {link}</p>
    """)

    ok, detail = _send_smtp(candidate.email, f"Assessment for {candidate.role_applied} - TalentEdge", html)
    status = "SENT" if ok else "QUEUED"
    _log_email(db, candidate.id, candidate.email, f"Assessment Invitation - {candidate.role_applied}", "Assessment Invitation", status, detail)
    return token


def send_rejection_email(db: Session, candidate: Candidate, stage: str = "ATS"):
    if not candidate.email:
        return
    reason = "After reviewing your profile" if stage == "ATS" else "After evaluating your assessment"
    html = _email_wrap("\U0001f4e8", "Application Update", f"""
        <h2 style="color:#1E293B;margin-top:0">Hi {candidate.name},</h2>
        <p style="color:#64748B;line-height:1.7">Thank you for your interest in the <strong>{candidate.role_applied}</strong> position.</p>
        <p style="color:#64748B;line-height:1.7">{reason}, we will not be moving forward with your application at this stage.</p>
        <p style="color:#64748B;line-height:1.7">We encourage you to apply again for future roles that match your experience.</p>
        <p style="color:#64748B;line-height:1.7">Wishing you all the best.</p>
    """)
    ok, detail = _send_smtp(candidate.email, f"Application Update - {candidate.role_applied}", html)
    _log_email(db, candidate.id, candidate.email, f"Rejection - {stage}", "Rejection", "SENT" if ok else "QUEUED", detail)


def send_interview_invitation(db: Session, candidate: Candidate, slots: list):
    if not candidate.email:
        return
    slots_html = "".join([f'<p style="margin:4px 0;color:#334155">\u2022 {s}</p>' for s in slots[:6]])
    html = _email_wrap("\U0001f389", "Interview Invitation", f"""
        <h2 style="color:#1E293B;margin-top:0">Congratulations, {candidate.name}!</h2>
        <p style="color:#64748B;line-height:1.7">You've passed the assessment for <strong>{candidate.role_applied}</strong>.
        We'd like to schedule your interview.</p>
        <div style="background:#EEF2FF;border:2px solid #C7D2FE;border-radius:12px;padding:20px;margin:20px 0">
            <p style="margin:0 0 8px;font-weight:700;color:#4F46E5">Available Slots:</p>
            {slots_html}
        </div>
        <p style="color:#64748B">Please reply to confirm your preferred slot.</p>
    """)
    ok, detail = _send_smtp(candidate.email, f"Interview for {candidate.role_applied} - TalentEdge", html)
    _log_email(db, candidate.id, candidate.email, f"Interview Invitation", "Interview Invitation", "SENT" if ok else "QUEUED", detail)


def send_recruiter_notification(db: Session, recruiter_email: str, candidate: Candidate, event: str):
    if not recruiter_email:
        return
    html = _email_wrap("\U0001f514", f"Candidate Update: {event}", f"""
        <h2 style="color:#1E293B;margin-top:0">{event}</h2>
        <div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;padding:15px;margin:15px 0">
            <p style="margin:4px 0"><strong>Candidate:</strong> {candidate.name}</p>
            <p style="margin:4px 0"><strong>Email:</strong> {candidate.email or 'N/A'}</p>
            <p style="margin:4px 0"><strong>Role:</strong> {candidate.role_applied}</p>
            <p style="margin:4px 0"><strong>ATS Score:</strong> {candidate.ats_score}</p>
            <p style="margin:4px 0"><strong>Status:</strong> {candidate.status}</p>
        </div>
        <div style="text-align:center;margin:20px 0">
            <a href="{settings.APP_URL}/dashboard" style="background:linear-gradient(135deg,#4F46E5,#7C3AED);color:white;padding:12px 30px;border-radius:10px;text-decoration:none;font-weight:700">View Dashboard</a>
        </div>
    """)
    ok, detail = _send_smtp(recruiter_email, f"[TalentEdge] {event}: {candidate.name}", html)
    _log_email(db, candidate.id, recruiter_email, f"Recruiter: {event}", "Recruiter Notification", "SENT" if ok else "QUEUED", detail)
