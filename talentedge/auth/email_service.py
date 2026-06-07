import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import settings


def _send_email(to_email: str, subject: str, html_body: str) -> bool:
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        print(f"[EMAIL] SMTP not configured. Would send to {to_email}: {subject}")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_USER}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_USER, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return False


def send_welcome_email(to_email: str, full_name: str):
    html = f"""
    <div style="font-family:Inter,Arial,sans-serif; max-width:600px; margin:0 auto; background:#f8fafc; border-radius:16px; overflow:hidden;">
        <div style="background:linear-gradient(135deg,#4F46E5,#7C3AED); padding:40px 30px; text-align:center;">
            <h1 style="color:white; margin:0;">🚀 Welcome to {settings.APP_NAME}!</h1>
        </div>
        <div style="padding:30px;">
            <h2 style="color:#1E293B;">Hi {full_name}!</h2>
            <p style="color:#64748B;">Your account has been created. Start screening candidates with AI-powered tools.</p>
            <div style="text-align:center; margin:30px 0;">
                <a href="{settings.APP_URL}/login" style="background:linear-gradient(135deg,#4F46E5,#7C3AED); color:white; padding:14px 40px; border-radius:12px; text-decoration:none; font-weight:700;">Sign In Now</a>
            </div>
        </div>
    </div>
    """
    _send_email(to_email, f"Welcome to {settings.APP_NAME}!", html)


def send_reset_email(to_email: str, full_name: str, reset_token: str):
    reset_link = f"{settings.APP_URL}/reset-password?token={reset_token}"
    html = f"""
    <div style="font-family:Inter,Arial,sans-serif; max-width:600px; margin:0 auto; background:#f8fafc; border-radius:16px; overflow:hidden;">
        <div style="background:linear-gradient(135deg,#4F46E5,#7C3AED); padding:40px 30px; text-align:center;">
            <h1 style="color:white; margin:0;">🔐 Password Reset</h1>
        </div>
        <div style="padding:30px;">
            <h2 style="color:#1E293B;">Hi {full_name},</h2>
            <p style="color:#64748B;">Click below to reset your password. This link expires in 15 minutes.</p>
            <div style="text-align:center; margin:30px 0;">
                <a href="{reset_link}" style="background:linear-gradient(135deg,#4F46E5,#7C3AED); color:white; padding:14px 40px; border-radius:12px; text-decoration:none; font-weight:700;">Reset Password</a>
            </div>
            <p style="color:#94A3B8; font-size:12px; word-break:break-all;">Link: {reset_link}</p>
        </div>
    </div>
    """
    _send_email(to_email, "Reset Your Password", html)
