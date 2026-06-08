import json
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models import Candidate, PipelineLog, EmailLog, User
from auth.utils import require_auth

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


def _get_user(request: Request, db: Session) -> User:
    user_data = require_auth(request)
    user = db.query(User).filter(User.id == int(user_data["sub"])).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/")
def get_analytics(request: Request, db: Session = Depends(get_db)):
    """Comprehensive analytics for the recruiter dashboard."""
    user = _get_user(request, db)

    candidates = db.query(Candidate).filter(Candidate.owner_id == user.id).all()
    total = len(candidates)

    if total == 0:
        return {
            "overview": {
                "total_candidates": 0, "passed_ats": 0, "failed_ats": 0,
                "manual_review": 0, "assessment_sent": 0, "passed_assessment": 0,
                "failed_assessment": 0, "interview_scheduled": 0,
                "interview_confirmed": 0, "hired": 0, "rejected": 0,
            },
            "ats_pass_rate": 0, "assessment_pass_rate": 0, "avg_ats_score": 0,
            "pipeline_funnel": [], "status_breakdown": [], "role_breakdown": [],
            "ats_score_distribution": [],
            "email_stats": {"sent": 0, "queued": 0, "failed": 0, "total": 0},
            "monthly_trend": [], "top_roles": [], "recent_activity": [],
        }

    # ── 1. Overview Counts ──
    status_counts = Counter(c.status for c in candidates)
    ats_counts = Counter(c.ats_decision for c in candidates)

    passed_ats = ats_counts.get("PASS", 0)
    failed_ats = ats_counts.get("FAIL", 0)
    manual_review = status_counts.get("Manual Review", 0)
    assessment_sent = status_counts.get("Assessment Sent", 0)
    passed_assessment = status_counts.get("Passed Assessment", 0)
    failed_assessment = status_counts.get("Failed Assessment", 0)
    interview_scheduled = status_counts.get("Interview Scheduled", 0)
    interview_confirmed = status_counts.get("Interview Confirmed", 0)
    hired = status_counts.get("Hired", 0)
    rejected = status_counts.get("Rejected", 0)

    overview = {
        "total_candidates": total, "passed_ats": passed_ats, "failed_ats": failed_ats,
        "manual_review": manual_review, "assessment_sent": assessment_sent,
        "passed_assessment": passed_assessment, "failed_assessment": failed_assessment,
        "interview_scheduled": interview_scheduled, "interview_confirmed": interview_confirmed,
        "hired": hired, "rejected": rejected,
    }

    # ── 2. Rates ──
    ats_pass_rate = round((passed_ats / total) * 100, 1) if total > 0 else 0
    assessment_total = passed_assessment + failed_assessment
    assessment_pass_rate = round((passed_assessment / assessment_total) * 100, 1) if assessment_total > 0 else 0

    # ── 3. Average ATS Score ──
    scores = [c.ats_score for c in candidates if c.ats_score is not None]
    avg_ats_score = round(sum(scores) / len(scores), 1) if scores else 0

    # ── 4. Pipeline Funnel ──
    pipeline_funnel = [
        {"stage": "Applied", "count": total},
        {"stage": "Passed ATS", "count": passed_ats},
        {"stage": "Assessment Sent", "count": assessment_sent + passed_assessment + failed_assessment + interview_scheduled + interview_confirmed + hired},
        {"stage": "Passed Assessment", "count": passed_assessment + interview_scheduled + interview_confirmed + hired},
        {"stage": "Interview", "count": interview_scheduled + interview_confirmed + hired + rejected},
        {"stage": "Hired", "count": hired},
    ]

    # ── 5. Status Breakdown ──
    status_breakdown = [
        {"status": s, "count": c} for s, c in sorted(status_counts.items(), key=lambda x: -x[1])
    ]

    # ── 6. Role Breakdown ──
    role_counts = Counter(c.role_applied for c in candidates if c.role_applied)
    role_breakdown = [
        {"role": r, "count": c} for r, c in sorted(role_counts.items(), key=lambda x: -x[1])
    ]

    # ── 7. ATS Score Distribution ──
    buckets = {"0-20": 0, "21-40": 0, "41-60": 0, "61-80": 0, "81-100": 0}
    for s in scores:
        if s <= 20: buckets["0-20"] += 1
        elif s <= 40: buckets["21-40"] += 1
        elif s <= 60: buckets["41-60"] += 1
        elif s <= 80: buckets["61-80"] += 1
        else: buckets["81-100"] += 1
    ats_score_distribution = [{"range": k, "count": v} for k, v in buckets.items()]

    # ── 8. Email Stats ──
    candidate_ids = [c.id for c in candidates]
    email_logs = db.query(EmailLog).filter(EmailLog.candidate_db_id.in_(candidate_ids)).all() if candidate_ids else []
    email_status_counts = Counter(e.status for e in email_logs)
    email_stats = {
        "sent": email_status_counts.get("SENT", 0),
        "queued": email_status_counts.get("QUEUED", 0),
        "failed": email_status_counts.get("FAILED", 0),
        "total": len(email_logs),
    }

    # ── 9. Monthly Trend ──
    six_months_ago = datetime.now() - timedelta(days=180)
    monthly = defaultdict(lambda: {"candidates": 0, "passed": 0, "failed": 0})
    for c in candidates:
        if c.created_at and c.created_at >= six_months_ago:
            month_key = c.created_at.strftime("%Y-%m")
            monthly[month_key]["candidates"] += 1
            if c.ats_decision == "PASS": monthly[month_key]["passed"] += 1
            elif c.ats_decision == "FAIL": monthly[month_key]["failed"] += 1
    monthly_trend = [
        {"month": k, **v} for k, v in sorted(monthly.items())
    ]

    # ── 10. Top Roles ──
    top_roles = [{"role": r, "count": c} for r, c in role_counts.most_common(5)]

    # ── 11. Recent Activity ──
    recent_logs = (
        db.query(PipelineLog).filter(PipelineLog.candidate_db_id.in_(candidate_ids))
        .order_by(PipelineLog.timestamp.desc()).limit(10).all()
    ) if candidate_ids else []
    recent_activity = [
        {
            "candidate_id": log.candidate_id, "stage": log.stage,
            "decision": log.decision, "reason": (log.reason or "")[:100],
            "timestamp": str(log.timestamp) if log.timestamp else "",
            "owner": log.owner or "AI_AGENT",
        }
        for log in recent_logs
    ]

    return {
        "overview": overview, "ats_pass_rate": ats_pass_rate,
        "assessment_pass_rate": assessment_pass_rate, "avg_ats_score": avg_ats_score,
        "pipeline_funnel": pipeline_funnel, "status_breakdown": status_breakdown,
        "role_breakdown": role_breakdown, "ats_score_distribution": ats_score_distribution,
        "email_stats": email_stats, "monthly_trend": monthly_trend,
        "top_roles": top_roles, "recent_activity": recent_activity,
    }