from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from fastapi import Request, HTTPException, status
from sqlalchemy.orm import Session
from config import settings
import bcrypt
import secrets


# ── Password Hashing (bcrypt direct — no passlib) ──

def hash_password(password: str) -> str:
    pw = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    pw = plain_password.encode("utf-8")[:72]
    return bcrypt.checkpw(pw, hashed_password.encode("utf-8"))


# ── JWT Tokens ──

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=settings.JWT_ACCESS_TOKEN_EXPIRE_HOURS))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


# ── Get current user from cookie ──

def get_current_user_from_cookie(request: Request) -> Optional[dict]:
    token = request.cookies.get("access_token")
    if not token:
        return None
    if token.startswith("Bearer "):
        token = token[7:]
    return decode_token(token)


def require_auth(request: Request) -> dict:
    user = get_current_user_from_cookie(request)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


# ── Rate Limiting ──

def check_rate_limit(user_record, max_attempts: int = 5, lockout_minutes: int = 15) -> bool:
    if user_record.locked_until and user_record.locked_until > datetime.now(timezone.utc):
        return True
    if user_record.locked_until and user_record.locked_until <= datetime.now(timezone.utc):
        user_record.failed_login_attempts = 0
        user_record.locked_until = None
    return False


def record_failed_login(user_record, db: Session, max_attempts: int = 5, lockout_minutes: int = 15):
    user_record.failed_login_attempts = (user_record.failed_login_attempts or 0) + 1
    if user_record.failed_login_attempts >= max_attempts:
        user_record.locked_until = datetime.now(timezone.utc) + timedelta(minutes=lockout_minutes)
    db.commit()


def reset_failed_logins(user_record, db: Session):
    user_record.failed_login_attempts = 0
    user_record.locked_until = None
    db.commit()


def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)