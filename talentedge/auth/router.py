from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.orm import Session
from database import get_db
from models import User
from auth.schemas import (
    SignUpRequest, SignInRequest, ForgotPasswordRequest,
    ResetPasswordRequest, UserResponse, TokenResponse,
)
from auth.utils import (
    hash_password, verify_password, create_access_token,
    check_rate_limit, record_failed_login, reset_failed_logins,
    generate_reset_token,
)
from auth.email_service import send_welcome_email, send_reset_email

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(data: SignUpRequest, db: Session = Depends(get_db)):
    """Register a new recruiter account."""
    existing = db.query(User).filter(User.email == data.email.lower()).first()
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    user = User(
        full_name=data.full_name,
        email=data.email.lower(),
        company_name=data.company_name,
        phone_number=data.phone_number,
        hashed_password=hash_password(data.password),
        role="recruiter",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    try:
        send_welcome_email(user.email, user.full_name)
    except Exception:
        pass

    return user


@router.post("/login", response_model=TokenResponse)
def login(data: SignInRequest, response: Response, db: Session = Depends(get_db)):
    """Authenticate and return JWT in cookie."""
    user = db.query(User).filter(User.email == data.email.lower()).first()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if check_rate_limit(user):
        remaining = (user.locked_until - datetime.now(timezone.utc)).seconds // 60
        raise HTTPException(status_code=429, detail=f"Account locked. Try again in {remaining + 1} minutes.")

    if not verify_password(data.password, user.hashed_password):
        record_failed_login(user, db)
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account deactivated.")

    reset_failed_logins(user, db)

    token_expiry = timedelta(days=7) if data.remember_me else timedelta(hours=24)
    token_data = {
        "sub": str(user.id),
        "email": user.email,
        "name": user.full_name,
        "company": user.company_name,
        "role": user.role,
    }
    access_token = create_access_token(token_data, expires_delta=token_expiry)

    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=int(token_expiry.total_seconds()),
        samesite="lax",
        secure=False,  # Set True with HTTPS
    )

    return TokenResponse(access_token=access_token, user=UserResponse.model_validate(user))


@router.post("/logout")
def logout(response: Response):
    """Clear auth cookie."""
    response.delete_cookie("access_token")
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
def get_me(request: Request, db: Session = Depends(get_db)):
    """Get current user info."""
    from auth.utils import get_current_user_from_cookie
    user_data = get_current_user_from_cookie(request)
    if not user_data:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = db.query(User).filter(User.id == int(user_data["sub"])).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/forgot-password")
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Send password reset email."""
    generic_msg = "If this email is registered, a reset link has been sent."
    user = db.query(User).filter(User.email == data.email.lower()).first()
    if not user:
        return {"message": generic_msg}

    token = generate_reset_token()
    user.reset_token = token
    user.reset_token_expiry = datetime.now(timezone.utc) + timedelta(minutes=15)
    db.commit()

    try:
        send_reset_email(user.email, user.full_name, token)
    except Exception:
        pass

    return {"message": generic_msg}


@router.post("/reset-password")
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Reset password using email token."""
    user = db.query(User).filter(User.reset_token == data.token).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link.")

    if not user.reset_token_expiry or user.reset_token_expiry < datetime.now(timezone.utc):
        user.reset_token = None
        user.reset_token_expiry = None
        db.commit()
        raise HTTPException(status_code=400, detail="Reset link has expired.")

    user.hashed_password = hash_password(data.new_password)
    user.reset_token = None
    user.reset_token_expiry = None
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()

    return {"message": "Password reset successful. Please log in."}
