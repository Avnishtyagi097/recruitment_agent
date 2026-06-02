import streamlit as st
import json
import re
import random
import hashlib
import smtplib
import pandas as pd
from datetime import datetime, timedelta
from collections import Counter
from io import BytesIO
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="TalentEdge AI Recruitment Platform",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# CUSTOM CSS THEME
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Poppins:wght@400;500;600;700;800&display=swap');

:root {
    --primary: #4F46E5;
    --primary-light: #818CF8;
    --secondary: #7C3AED;
    --success: #10B981;
    --success-light: #D1FAE5;
    --danger: #EF4444;
    --danger-light: #FEE2E2;
    --warning: #F59E0B;
    --warning-light: #FEF3C7;
    --info: #3B82F6;
    --info-light: #DBEAFE;
    --dark: #1E293B;
    --darker: #0F172A;
    --light: #F8FAFC;
    --gray: #64748B;
    --border: #E2E8F0;
}

/* ──── Global ──── */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}
.main .block-container {
    padding-top: 2rem;
    padding-bottom: 4rem;
    max-width: 1200px;
}

/* ──── Sidebar ──── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1E293B 0%, #0F172A 100%) !important;
}
[data-testid="stSidebar"] * {
    color: #CBD5E1 !important;
}
[data-testid="stSidebar"] .stMarkdown h1,
[data-testid="stSidebar"] .stMarkdown h2,
[data-testid="stSidebar"] .stMarkdown h3 {
    color: #F1F5F9 !important;
}
[data-testid="stSidebar"] .stRadio > label {
    color: #94A3B8 !important;
    font-weight: 500;
}
[data-testid="stSidebar"] hr {
    border-color: #334155 !important;
}
[data-testid="stSidebar"] .stButton > button {
    background: linear-gradient(135deg, #EF4444, #DC2626) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
}

/* ──── Hero Banner ──── */
.hero-banner {
    background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 50%, #EC4899 100%);
    color: white;
    padding: 2.5rem 3rem;
    border-radius: 20px;
    margin-bottom: 2rem;
    box-shadow: 0 20px 60px rgba(79, 70, 229, 0.3);
    position: relative;
    overflow: hidden;
}
.hero-banner::before {
    content: '';
    position: absolute;
    top: -50%;
    right: -20%;
    width: 400px;
    height: 400px;
    border-radius: 50%;
    background: rgba(255,255,255,0.08);
}
.hero-banner h1 {
    font-family: 'Poppins', sans-serif;
    font-size: 2.2rem;
    font-weight: 800;
    margin-bottom: 0.5rem;
}
.hero-banner p {
    font-size: 1.1rem;
    opacity: 0.9;
    margin: 0;
}

/* ──── Stat Cards ──── */
.stat-card {
    background: white;
    border-radius: 16px;
    padding: 1.5rem;
    box-shadow: 0 4px 20px rgba(0,0,0,0.06);
    transition: all 0.3s ease;
    border: 1px solid #F1F5F9;
    text-align: center;
    position: relative;
    overflow: hidden;
}
.stat-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 12px 40px rgba(0,0,0,0.12);
}
.stat-card .stat-value {
    font-family: 'Poppins', sans-serif;
    font-size: 2.2rem;
    font-weight: 800;
    line-height: 1.2;
}
.stat-card .stat-label {
    font-size: 0.85rem;
    color: #64748B;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-top: 0.3rem;
}
.stat-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 4px;
}
.stat-blue::before { background: linear-gradient(90deg, #4F46E5, #818CF8); }
.stat-blue .stat-value { color: #4F46E5; }
.stat-green::before { background: linear-gradient(90deg, #10B981, #34D399); }
.stat-green .stat-value { color: #10B981; }
.stat-red::before { background: linear-gradient(90deg, #EF4444, #F87171); }
.stat-red .stat-value { color: #EF4444; }
.stat-orange::before { background: linear-gradient(90deg, #F59E0B, #FBBF24); }
.stat-orange .stat-value { color: #F59E0B; }
.stat-purple::before { background: linear-gradient(90deg, #7C3AED, #A78BFA); }
.stat-purple .stat-value { color: #7C3AED; }

/* ──── Score Circle ──── */
.score-circle {
    width: 160px;
    height: 160px;
    border-radius: 50%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    margin: 0 auto 1rem;
    font-family: 'Poppins', sans-serif;
    box-shadow: 0 8px 30px rgba(0,0,0,0.12);
}
.score-circle.pass {
    background: linear-gradient(135deg, #D1FAE5, #A7F3D0);
    border: 4px solid #10B981;
}
.score-circle.fail {
    background: linear-gradient(135deg, #FEE2E2, #FECACA);
    border: 4px solid #EF4444;
}
.score-circle.review {
    background: linear-gradient(135deg, #FEF3C7, #FDE68A);
    border: 4px solid #F59E0B;
}
.score-circle .score-value {
    font-size: 2.5rem;
    font-weight: 800;
    line-height: 1;
}
.score-circle .score-label {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
}

/* ──── Skill Tags ──── */
.skill-tag {
    display: inline-block;
    padding: 0.35rem 0.9rem;
    border-radius: 50px;
    font-size: 0.8rem;
    font-weight: 600;
    margin: 0.2rem;
    transition: transform 0.2s ease;
}
.skill-tag:hover { transform: scale(1.05); }
.skill-matched {
    background: #D1FAE5;
    color: #065F46;
    border: 1px solid #A7F3D0;
}
.skill-missing {
    background: #FEE2E2;
    color: #991B1B;
    border: 1px solid #FECACA;
}

/* ──── Banners ──── */
.result-banner {
    padding: 1.2rem 2rem;
    border-radius: 14px;
    font-size: 1.1rem;
    font-weight: 700;
    text-align: center;
    margin: 1rem 0;
    animation: fadeIn 0.5s ease;
}
.pass-banner {
    background: linear-gradient(135deg, #D1FAE5, #A7F3D0);
    color: #065F46;
    border: 2px solid #10B981;
}
.fail-banner {
    background: linear-gradient(135deg, #FEE2E2, #FECACA);
    color: #991B1B;
    border: 2px solid #EF4444;
}
.review-banner {
    background: linear-gradient(135deg, #FEF3C7, #FDE68A);
    color: #92400E;
    border: 2px solid #F59E0B;
}

/* ──── Section Card ──── */
.section-card {
    background: white;
    border-radius: 16px;
    padding: 2rem;
    box-shadow: 0 4px 20px rgba(0,0,0,0.05);
    border: 1px solid #F1F5F9;
    margin-bottom: 1.5rem;
}
.section-card h3 {
    font-family: 'Poppins', sans-serif;
    color: #1E293B;
    margin-bottom: 1rem;
}

/* ──── Question Card ──── */
.question-card {
    background: #FAFBFC;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    margin-bottom: 1rem;
    border-left: 4px solid #4F46E5;
}
.question-card .q-number {
    color: #4F46E5;
    font-weight: 700;
    font-size: 0.85rem;
}
.question-card .q-meta {
    color: #94A3B8;
    font-size: 0.75rem;
}

/* ──── Timeline ──── */
.timeline-item {
    border-left: 3px solid #E2E8F0;
    padding: 0.8rem 0 0.8rem 1.5rem;
    position: relative;
    margin-left: 0.5rem;
}
.timeline-item::before {
    content: '';
    width: 12px;
    height: 12px;
    border-radius: 50%;
    position: absolute;
    left: -7.5px;
    top: 1.2rem;
}
.timeline-sent::before { background: #10B981; }
.timeline-failed::before { background: #EF4444; }
.timeline-queued::before { background: #F59E0B; }

/* ──── Candidate Card ──── */
.candidate-card {
    background: white;
    border-radius: 14px;
    padding: 1.5rem;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
    border: 1px solid #F1F5F9;
    transition: all 0.3s ease;
    margin-bottom: 1rem;
}
.candidate-card:hover {
    box-shadow: 0 8px 30px rgba(0,0,0,0.1);
    border-color: #818CF8;
}
.status-badge {
    display: inline-block;
    padding: 0.25rem 0.8rem;
    border-radius: 50px;
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.badge-pass { background: #D1FAE5; color: #065F46; }
.badge-fail { background: #FEE2E2; color: #991B1B; }
.badge-review { background: #FEF3C7; color: #92400E; }
.badge-pending { background: #DBEAFE; color: #1E40AF; }
.badge-interview { background: #EDE9FE; color: #5B21B6; }

/* ──── Gradient Divider ──── */
.gradient-divider {
    height: 3px;
    background: linear-gradient(90deg, #4F46E5, #7C3AED, #EC4899, transparent);
    border: none;
    border-radius: 2px;
    margin: 2rem 0;
}

/* ──── Footer ──── */
.footer {
    text-align: center;
    padding: 2rem 0 1rem;
    margin-top: 3rem;
    border-top: 1px solid #E2E8F0;
    color: #94A3B8;
    font-size: 0.85rem;
}
.footer a { color: #4F46E5; text-decoration: none; font-weight: 600; }

/* ──── Streamlit Overrides ──── */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #4F46E5, #7C3AED) !important;
    color: white !important;
    border: none !important;
    border-radius: 12px !important;
    padding: 0.6rem 2rem !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 4px 15px rgba(79, 70, 229, 0.3) !important;
}
.stButton > button[kind="primary"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 25px rgba(79, 70, 229, 0.4) !important;
}
.stProgress > div > div > div {
    background: linear-gradient(90deg, #4F46E5, #7C3AED) !important;
    border-radius: 10px !important;
}
[data-testid="stExpander"] {
    border: 1px solid #E2E8F0 !important;
    border-radius: 12px !important;
    overflow: hidden;
}
div[data-testid="stMetric"] {
    background: white;
    border: 1px solid #F1F5F9;
    border-radius: 12px;
    padding: 1rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}

/* ──── Animations ──── */
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}
@keyframes pulse {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.05); }
}
.animate-in {
    animation: fadeIn 0.6s ease forwards;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# SESSION STATE INITIALISATION
# ─────────────────────────────────────────────
defaults = {
    "candidates": {},
    "pipeline_logs": [],
    "current_candidate_id": None,
    "current_stage": "CV Upload & ATS",
    "assessment_started": False,
    "assessment_answers": {},
    "assessment_submitted": False,
    "assessment_questions": [],
    "assessment_result": None,
    "assessment_start_time": None,
    "recruiter_name": "TalentEdge Recruitment Team",
    "recruiter_email": "recruit@talentedge.ai",
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender_email": "",
    "sender_password": "",
    "smtp_configured": False,
    "auto_email_enabled": True,
    "email_log": [],
    "assessment_tokens": {},
    "_arrived_via_link": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────
# ASSESSMENT LINK HANDLER
# ─────────────────────────────────────────────
_query_assess_token = st.query_params.get("assess", None)
if _query_assess_token and _query_assess_token in st.session_state.assessment_tokens:
    _linked_cid = st.session_state.assessment_tokens[_query_assess_token]
    if _linked_cid in st.session_state.candidates:
        st.session_state.current_candidate_id = _linked_cid
        st.session_state["_arrived_via_link"] = True

# ─────────────────────────────────────────────
# HELPER: RENDER FOOTER
# ─────────────────────────────────────────────
def render_footer():
    st.markdown("""
    <div class="footer">
        🚀 <strong>TalentEdge AI Recruitment Platform</strong> — Built for fair, explainable & compliant hiring<br>
        <span style="font-size:0.78rem;">Powered by AI Screening • Automated Emails • Smart Assessments • Interview Scheduling</span>
    </div>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# EMAIL FUNCTIONS
# ─────────────────────────────────────────────

def send_email(to_email, subject, body_text):
    """Send an email via SMTP. Returns (success: bool, message: str)."""
    if not st.session_state.smtp_configured:
        return False, "SMTP not configured. Email queued for manual review."
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = formataddr((st.session_state.recruiter_name, st.session_state.sender_email))
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body_text, "plain", "utf-8"))

        with smtplib.SMTP(st.session_state.smtp_server, st.session_state.smtp_port, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(st.session_state.sender_email, st.session_state.sender_password)
            server.sendmail(st.session_state.sender_email, to_email, msg.as_string())
        return True, "Email sent successfully."
    except smtplib.SMTPAuthenticationError:
        return False, "SMTP authentication failed. Check email/password or enable App Passwords."
    except smtplib.SMTPException as e:
        return False, f"SMTP error: {str(e)}"
    except Exception as e:
        return False, f"Email error: {str(e)}"


def log_email(to_email, subject, email_type, status, detail):
    """Log every email action."""
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "to": to_email,
        "subject": subject,
        "type": email_type,
        "status": status,
        "detail": detail,
    }
    st.session_state.email_log.append(entry)
    return entry


def send_and_log(to_email, subject, body, email_type):
    """Send an email and log the result. Returns (success, message, status)."""
    if st.session_state.auto_email_enabled and st.session_state.smtp_configured:
        ok, msg = send_email(to_email, subject, body)
        status = "SENT" if ok else "FAILED"
    else:
        ok = False
        msg = "Auto-email disabled or SMTP not configured. Email content generated for manual sending."
        status = "QUEUED"
    log_email(to_email, subject, email_type, status, msg)
    return ok, msg, status


def auto_pipeline_action(candidate_data, action_type):
    """
    Automate the full pipeline action after a decision.
    Returns a list of action summaries.
    """
    actions = []
    c_name = candidate_data["name"]
    c_email = candidate_data.get("email", "")
    role = candidate_data["role"]
    recruiter_name = st.session_state.recruiter_name
    recruiter_email = st.session_state.recruiter_email
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if action_type == "ats_fail":
        # 1. Send rejection to candidate
        subj = f"Update on Your Application for {role}"
        body = generate_rejection_email(c_name, role, "ATS", recruiter_name)
        if c_email:
            ok, msg, status = send_and_log(c_email, subj, body, "ATS Rejection → Candidate")
            actions.append({"action": "Rejection email to candidate", "to": c_email, "status": status, "detail": msg})
            candidate_data["emails_sent"].append({"type": "ATS Rejection", "content": body, "timestamp": now_str, "send_status": status})
        # 2. Notify recruiter
        r_subj = f"[ATS FAIL] Candidate Rejected: {c_name} — {role}"
        r_body = f"Candidate: {c_name}\nEmail: {c_email}\nRole: {role}\nATS Score: {candidate_data['ats_result']['ats_score']}\nDecision: FAIL\nReason: {candidate_data['ats_result']['reasoning_summary']}\n\nRejection email has been sent to the candidate."
        if recruiter_email:
            ok2, msg2, status2 = send_and_log(recruiter_email, r_subj, r_body, "ATS Rejection → Recruiter Notification")
            actions.append({"action": "Recruiter notification (ATS FAIL)", "to": recruiter_email, "status": status2, "detail": msg2})

    elif action_type == "ats_pass":
        # 1. Send assessment invitation to candidate
        deadline = (datetime.now() + timedelta(days=2)).strftime("%B %d, %Y at 11:59 PM UTC")
        subj = f"Next Step: Assessment for {role}"
        body = generate_assessment_email(c_name, role, deadline, recruiter_name, candidate_id=candidate_data.get("id", ""))
        if c_email:
            ok, msg, status = send_and_log(c_email, subj, body, "Assessment Invitation → Candidate")
            actions.append({"action": "Assessment invitation to candidate", "to": c_email, "status": status, "detail": msg})
            candidate_data["emails_sent"].append({"type": "Assessment Invitation", "content": body, "timestamp": now_str, "send_status": status})
        # 2. Notify recruiter
        r_subj = f"[ATS PASS] New Candidate Shortlisted: {c_name} — {role}"
        r_body = f"Candidate: {c_name}\nEmail: {c_email}\nRole: {role}\nATS Score: {candidate_data['ats_result']['ats_score']}\nDecision: PASS\n\nAssessment invitation has been sent to the candidate.\nDeadline: {deadline}"
        if recruiter_email:
            ok2, msg2, status2 = send_and_log(recruiter_email, r_subj, r_body, "ATS Pass → Recruiter Notification")
            actions.append({"action": "Recruiter notification (ATS PASS)", "to": recruiter_email, "status": status2, "detail": msg2})

    elif action_type == "assessment_fail":
        subj = f"Update on Your Application for {role}"
        body = generate_rejection_email(c_name, role, "Assessment", recruiter_name)
        if c_email:
            ok, msg, status = send_and_log(c_email, subj, body, "Assessment Rejection → Candidate")
            actions.append({"action": "Rejection email to candidate", "to": c_email, "status": status, "detail": msg})
            candidate_data["emails_sent"].append({"type": "Assessment Rejection", "content": body, "timestamp": now_str, "send_status": status})
        assess = candidate_data.get("assessment_result", {})
        r_subj = f"[ASSESSMENT FAIL] Candidate Rejected: {c_name} — {role}"
        r_body = f"Candidate: {c_name}\nEmail: {c_email}\nRole: {role}\nAssessment Score: {assess.get('score_percent', 0)}%\nDecision: FAIL\n\nRejection email has been sent to the candidate."
        if recruiter_email:
            ok2, msg2, status2 = send_and_log(recruiter_email, r_subj, r_body, "Assessment Rejection → Recruiter Notification")
            actions.append({"action": "Recruiter notification (Assessment FAIL)", "to": recruiter_email, "status": status2, "detail": msg2})

    elif action_type == "assessment_pass":
        availability = get_panel_availability(role)
        slots = availability["slots"]
        subj = f"Interview Scheduling for {role}"
        body = generate_interview_email(c_name, role, slots, recruiter_name)
        if c_email:
            ok, msg, status = send_and_log(c_email, subj, body, "Interview Invitation → Candidate")
            actions.append({"action": "Interview invitation to candidate", "to": c_email, "status": status, "detail": msg})
            candidate_data["emails_sent"].append({"type": "Interview Invitation", "content": body, "timestamp": now_str, "send_status": status})
        candidate_data["interview_scheduled"] = True
        candidate_data["interview_slots"] = slots
        candidate_data["interview_panel"] = availability["panel"]
        assess = candidate_data.get("assessment_result", {})
        r_subj = f"[INTERVIEW READY] Candidate Cleared: {c_name} — {role}"
        panel_names = ", ".join([p["name"] for p in availability["panel"]])
        slot_summary = "\n".join([f"  - {s['date']} at {s['time']}" for s in slots[:6]])
        r_body = f"Candidate: {c_name}\nEmail: {c_email}\nRole: {role}\nATS Score: {candidate_data['ats_result']['ats_score']}\nAssessment Score: {assess.get('score_percent', 0)}%\n\nInterview invitation has been sent.\n\nPanel: {panel_names}\nAvailable Slots:\n{slot_summary}"
        if recruiter_email:
            ok2, msg2, status2 = send_and_log(recruiter_email, r_subj, r_body, "Interview Ready → Recruiter Notification")
            actions.append({"action": "Recruiter notification (Interview Ready)", "to": recruiter_email, "status": status2, "detail": msg2})

    return actions


# ─────────────────────────────────────────────
# JOB DESCRIPTION TEMPLATES
# ─────────────────────────────────────────────
JD_TEMPLATES = {
    "Data Engineer": """
Role: Data Engineer
Experience Required: 3-6 years

Responsibilities:
- Design, build, and maintain scalable data pipelines using ETL/ELT frameworks.
- Develop and optimize SQL queries and stored procedures for data transformation.
- Work with Apache Spark, PySpark, and Databricks for large-scale data processing.
- Design and maintain data warehouse schemas (star/snowflake) in cloud environments.
- Orchestrate workflows using Apache Airflow or similar tools.
- Implement data quality frameworks, monitoring, and governance best practices.
- Collaborate with analytics and ML teams to deliver clean, reliable datasets.
- Manage data on cloud platforms (AWS S3, Azure Data Lake, GCP BigQuery).

Required Skills:
- Python, SQL, Spark, PySpark, Databricks
- ETL/ELT design and implementation
- Data warehousing (Snowflake, Redshift, BigQuery)
- Apache Airflow, dbt
- Cloud platforms: AWS / Azure / GCP
- Data modeling (star schema, snowflake schema, data vault)
- Batch and streaming data processing (Kafka, Kinesis)
- Performance optimization and query tuning
- Data governance and cataloging (e.g., Apache Atlas, Collibra)
- CI/CD for data pipelines, version control (Git)

Preferred Certifications:
- Databricks Certified Data Engineer
- AWS Certified Data Analytics
- Google Professional Data Engineer
- Azure Data Engineer Associate

Education:
- Bachelor's or Master's in Computer Science, Data Science, Information Systems, or related field.
""",
    "Software Engineer": """
Role: Software Engineer
Experience Required: 2-5 years

Responsibilities:
- Design, develop, test, and maintain scalable software applications.
- Write clean, efficient, and well-documented code.
- Participate in code reviews and contribute to engineering best practices.
- Build and consume RESTful APIs and microservices.
- Work with relational and NoSQL databases.
- Deploy applications using CI/CD pipelines and container orchestration.
- Collaborate with product, design, and QA teams.

Required Skills:
- Python, Java, or JavaScript/TypeScript
- REST APIs, GraphQL
- Microservices architecture
- SQL, PostgreSQL, MongoDB
- Docker, Kubernetes
- CI/CD (Jenkins, GitHub Actions)
- Unit testing, TDD
- Git, Agile/Scrum
- Cloud platforms: AWS / Azure / GCP
- System design fundamentals

Preferred Certifications:
- AWS Certified Developer
- Azure Developer Associate
- Certified Kubernetes Application Developer (CKAD)

Education:
- Bachelor's or Master's in Computer Science, Software Engineering, or related field.
""",
    "Data Analyst": """
Role: Data Analyst
Experience Required: 1-4 years

Responsibilities:
- Analyze large datasets to identify trends, patterns, and insights.
- Create dashboards and reports using BI tools.
- Write complex SQL queries for data extraction and analysis.
- Collaborate with business stakeholders to define KPIs and metrics.
- Clean and validate data for accuracy and integrity.
- Present findings through data storytelling.

Required Skills:
- SQL, Excel (advanced)
- Python or R for data analysis
- Tableau, Power BI, Looker
- Statistical analysis and hypothesis testing
- Data cleaning and wrangling (Pandas, NumPy)
- Data visualization best practices
- Basic understanding of ETL processes
- Communication and presentation skills
- Git, Jupyter Notebooks

Preferred Certifications:
- Google Data Analytics Certificate
- Microsoft Certified: Data Analyst Associate
- Tableau Desktop Specialist

Education:
- Bachelor's in Statistics, Mathematics, Data Science, Economics, or related field.
""",
    "DevOps Engineer": """
Role: DevOps Engineer
Experience Required: 3-6 years

Responsibilities:
- Design and implement CI/CD pipelines for automated build, test, and deployment.
- Manage cloud infrastructure using Infrastructure as Code (Terraform, CloudFormation).
- Monitor system performance and ensure high availability.
- Containerize applications using Docker and orchestrate with Kubernetes.
- Implement security best practices across the pipeline.
- Manage configuration with Ansible, Chef, or Puppet.
- Troubleshoot production incidents and conduct root cause analysis.

Required Skills:
- Linux, Bash scripting, Python
- Docker, Kubernetes, Helm
- Terraform, CloudFormation, Ansible
- CI/CD: Jenkins, GitLab CI, GitHub Actions
- AWS / Azure / GCP cloud services
- Monitoring: Prometheus, Grafana, ELK stack, Datadog
- Networking basics (DNS, TCP/IP, load balancing)
- Security: IAM, secrets management, vulnerability scanning
- Git, GitOps practices
- Incident management and SRE principles

Preferred Certifications:
- AWS Certified DevOps Engineer
- Certified Kubernetes Administrator (CKA)
- HashiCorp Certified: Terraform Associate
- Azure DevOps Engineer Expert

Education:
- Bachelor's in Computer Science, Information Technology, or related field.
""",
}

# ─────────────────────────────────────────────
# QUESTION BANKS
# ─────────────────────────────────────────────
QUESTION_BANKS = {
"Data Engineer": [
  {"q":"What does ETL stand for?","options":["Extract, Transform, Load","Execute, Transfer, Log","Extract, Transfer, Load","Execute, Transform, Load"],"answer":0,"topic":"ETL","difficulty":"easy"},
  {"q":"Which SQL clause is used to filter groups of rows?","options":["WHERE","HAVING","GROUP BY","ORDER BY"],"answer":1,"topic":"SQL","difficulty":"easy"},
  {"q":"In a star schema, fact tables are connected to:","options":["Other fact tables","Dimension tables","Staging tables","Log tables"],"answer":1,"topic":"Data Modeling","difficulty":"easy"},
  {"q":"Which Apache Spark component is used for structured data processing?","options":["Spark Streaming","MLlib","Spark SQL","GraphX"],"answer":2,"topic":"Spark","difficulty":"easy"},
  {"q":"What is the primary purpose of Apache Airflow?","options":["Data storage","Workflow orchestration","Real-time streaming","Machine learning"],"answer":1,"topic":"Orchestration","difficulty":"easy"},
  {"q":"Which Python library is most commonly used for data manipulation?","options":["NumPy","Matplotlib","Pandas","Scikit-learn"],"answer":2,"topic":"Python","difficulty":"easy"},
  {"q":"In data warehousing, what is a slowly changing dimension (SCD)?","options":["A dimension that never changes","A dimension that tracks changes over time","A dimension used for real-time data","A temporary staging dimension"],"answer":1,"topic":"Data Warehousing","difficulty":"medium"},
  {"q":"What is the difference between batch and stream processing?","options":["Batch is real-time; stream is periodic","Batch processes data in chunks; stream processes data continuously","They are the same","Batch is faster than streaming"],"answer":1,"topic":"Batch vs Streaming","difficulty":"easy"},
  {"q":"Which of the following is a columnar storage format?","options":["CSV","JSON","Parquet","XML"],"answer":2,"topic":"Data Warehousing","difficulty":"easy"},
  {"q":"What does the ACID property Isolation guarantee?","options":["Data is saved permanently","Transactions don't interfere with each other","All operations succeed or none do","Data remains valid"],"answer":1,"topic":"SQL","difficulty":"medium"},
  {"q":"In Spark, what is a DataFrame?","options":["A distributed collection of key-value pairs","A distributed collection of data organized into named columns","A Python dictionary","A type of RDD with no schema"],"answer":1,"topic":"Spark","difficulty":"easy"},
  {"q":"Which partitioning strategy splits data by date?","options":["Hash partitioning","Range partitioning","Round-robin partitioning","Random partitioning"],"answer":1,"topic":"Performance Optimization","difficulty":"medium"},
  {"q":"What is the purpose of a data catalog?","options":["Store raw data","Provide metadata management and data discovery","Run ETL jobs","Monitor dashboards"],"answer":1,"topic":"Governance","difficulty":"easy"},
  {"q":"Which AWS service is a serverless data warehouse?","options":["RDS","DynamoDB","Redshift Serverless","S3"],"answer":2,"topic":"Cloud","difficulty":"medium"},
  {"q":"What is schema-on-read?","options":["Schema is enforced when data is written","Schema is applied when data is read","Schema is never used","Schema is stored in a separate database"],"answer":1,"topic":"Data Modeling","difficulty":"medium"},
  {"q":"In Kafka, what is a topic?","options":["A consumer group","A category to which records are published","A type of broker","A serialization format"],"answer":1,"topic":"Batch vs Streaming","difficulty":"easy"},
  {"q":"What transformation does a window function perform in SQL?","options":["Filters rows before aggregation","Performs calculations across a set of rows related to the current row","Joins two tables","Creates a new table"],"answer":1,"topic":"SQL","difficulty":"medium"},
  {"q":"Which tool is commonly used for data transformation in the modern data stack?","options":["Hadoop MapReduce","dbt (data build tool)","Apache Pig","Sqoop"],"answer":1,"topic":"ETL","difficulty":"medium"},
  {"q":"What is data lineage?","options":["The speed of data transfer","The tracking of data origin and transformations","The size of a dataset","A data encryption method"],"answer":1,"topic":"Governance","difficulty":"easy"},
  {"q":"In Databricks, what is a Delta table?","options":["A temporary view","An ACID-compliant table format built on Parquet","A CSV file","A streaming-only table"],"answer":1,"topic":"Databricks","difficulty":"medium"},
  {"q":"Which join returns all rows from both tables, matching where possible?","options":["INNER JOIN","LEFT JOIN","FULL OUTER JOIN","CROSS JOIN"],"answer":2,"topic":"SQL","difficulty":"easy"},
  {"q":"What is the purpose of an idempotent pipeline?","options":["It runs only once","Re-running it produces the same result without side effects","It processes data faster","It requires no input"],"answer":1,"topic":"ETL","difficulty":"medium"},
  {"q":"Which Spark action triggers computation on an RDD?","options":["map()","filter()","collect()","flatMap()"],"answer":2,"topic":"Spark","difficulty":"medium"},
  {"q":"What is the CAP theorem?","options":["A data modeling technique","A theorem about consistency, availability, and partition tolerance","A caching strategy","A compression algorithm"],"answer":1,"topic":"Data Warehousing","difficulty":"medium"},
  {"q":"In Python, which library is used for connecting to databases using an ORM?","options":["requests","sqlalchemy","flask","beautifulsoup"],"answer":1,"topic":"Python","difficulty":"easy"},
  {"q":"What is a materialized view?","options":["A virtual table that runs a query each time","A stored result set of a query","A temporary table","An index on a table"],"answer":1,"topic":"SQL","difficulty":"medium"},
  {"q":"Which Azure service is used for big data analytics?","options":["Azure Blob Storage","Azure Synapse Analytics","Azure Functions","Azure DevOps"],"answer":1,"topic":"Cloud","difficulty":"medium"},
  {"q":"What is data skew in distributed processing?","options":["Uniform data distribution","Uneven distribution of data across partitions","A type of data corruption","A sorting algorithm"],"answer":1,"topic":"Performance Optimization","difficulty":"medium"},
  {"q":"What is the role of a schema registry in streaming?","options":["Store data permanently","Manage and enforce schemas for messages","Route messages to topics","Monitor consumer lag"],"answer":1,"topic":"Batch vs Streaming","difficulty":"medium"},
  {"q":"Which orchestration pattern uses a DAG?","options":["Linear pipeline","Directed Acyclic Graph workflow","Circular workflow","Ad-hoc scheduling"],"answer":1,"topic":"Orchestration","difficulty":"easy"},
  {"q":"What is change data capture (CDC)?","options":["Capturing all data at once","Identifying and capturing changes made to data","A backup strategy","A data encryption method"],"answer":1,"topic":"ETL","difficulty":"medium"},
  {"q":"In Spark, wide transformations require:","options":["No shuffling","Data shuffling across partitions","Only local computation","Schema validation"],"answer":1,"topic":"Spark","difficulty":"hard"},
  {"q":"What is a data vault modeling approach?","options":["A replacement for all data models","A methodology using hubs, links, and satellites","A type of star schema","A NoSQL design pattern"],"answer":1,"topic":"Data Modeling","difficulty":"hard"},
  {"q":"Which Python decorator is used for caching function results?","options":["@staticmethod","@lru_cache","@property","@classmethod"],"answer":1,"topic":"Python","difficulty":"medium"},
  {"q":"What is the purpose of data partitioning in a data lake?","options":["Encrypt data","Improve query performance by reducing data scanned","Compress files","Create backups"],"answer":1,"topic":"Performance Optimization","difficulty":"medium"},
],
"Software Engineer": [
  {"q":"What is the time complexity of binary search?","options":["O(n)","O(log n)","O(n log n)","O(1)"],"answer":1,"topic":"Algorithms","difficulty":"easy"},
  {"q":"Which HTTP method is idempotent?","options":["POST","PATCH","PUT","None of the above"],"answer":2,"topic":"REST APIs","difficulty":"easy"},
  {"q":"What is the SOLID principle S for?","options":["Single Responsibility","Separation of Concerns","Singleton Pattern","Secure coding"],"answer":0,"topic":"Design Principles","difficulty":"easy"},
  {"q":"In a microservices architecture, what is an API Gateway?","options":["A database","A single entry point for API calls","A testing tool","A deployment server"],"answer":1,"topic":"Microservices","difficulty":"easy"},
  {"q":"Which data structure uses FIFO?","options":["Stack","Queue","Tree","Graph"],"answer":1,"topic":"Data Structures","difficulty":"easy"},
  {"q":"What does Docker containerization provide?","options":["Hardware virtualization","OS-level isolation for applications","Compiler optimization","Database management"],"answer":1,"topic":"Docker","difficulty":"easy"},
  {"q":"What is the purpose of a load balancer?","options":["Store data","Distribute traffic across servers","Compile code","Manage databases"],"answer":1,"topic":"System Design","difficulty":"easy"},
  {"q":"Which testing level verifies individual components?","options":["Integration testing","Unit testing","System testing","Acceptance testing"],"answer":1,"topic":"Testing","difficulty":"easy"},
  {"q":"What is a deadlock?","options":["A fast execution path","Two or more processes waiting for each other indefinitely","A type of exception","A memory leak"],"answer":1,"topic":"Concurrency","difficulty":"medium"},
  {"q":"In Git, what does rebase do?","options":["Deletes a branch","Re-applies commits on top of another base","Merges two repos","Creates a tag"],"answer":1,"topic":"Git","difficulty":"medium"},
  {"q":"What is the CAP theorem relevant to?","options":["UI design","Distributed systems","Compiler design","Sorting algorithms"],"answer":1,"topic":"System Design","difficulty":"medium"},
  {"q":"Which design pattern ensures a class has only one instance?","options":["Factory","Observer","Singleton","Strategy"],"answer":2,"topic":"Design Patterns","difficulty":"easy"},
  {"q":"What is the purpose of an ORM?","options":["Optimize rendering","Map objects to database tables","Manage operating systems","Route network packets"],"answer":1,"topic":"Databases","difficulty":"easy"},
  {"q":"In REST, what status code indicates Created?","options":["200","201","204","301"],"answer":1,"topic":"REST APIs","difficulty":"easy"},
  {"q":"What is CI/CD?","options":["Code Inspection/Code Deployment","Continuous Integration/Continuous Delivery","Central Index/Central Database","Compiled Instructions/Compiled Data"],"answer":1,"topic":"DevOps","difficulty":"easy"},
  {"q":"Which Kubernetes object manages stateless applications?","options":["StatefulSet","Deployment","DaemonSet","Job"],"answer":1,"topic":"Kubernetes","difficulty":"medium"},
  {"q":"What is a race condition?","options":["A performance benchmark","When output depends on uncontrolled timing of events","A networking protocol","A type of sort"],"answer":1,"topic":"Concurrency","difficulty":"medium"},
  {"q":"SQL uses fixed schemas; NoSQL is:","options":["Also fixed schema","Schema-flexible","Schema-less only","Identical to SQL"],"answer":1,"topic":"Databases","difficulty":"easy"},
  {"q":"What does DRY stand for in software engineering?","options":["Don't Repeat Yourself","Data Replication Yield","Dynamic Resource Yielding","Deploy Run Yell"],"answer":0,"topic":"Design Principles","difficulty":"easy"},
  {"q":"Which protocol does GraphQL use?","options":["FTP","HTTP","SMTP","SSH"],"answer":1,"topic":"REST APIs","difficulty":"easy"},
  {"q":"What is a hash table average lookup time?","options":["O(n)","O(log n)","O(1)","O(n^2)"],"answer":2,"topic":"Data Structures","difficulty":"easy"},
  {"q":"What is blue-green deployment?","options":["A testing strategy","Running two identical production environments for zero-downtime releases","A color-coding convention","A branching strategy"],"answer":1,"topic":"DevOps","difficulty":"medium"},
  {"q":"What is dependency injection?","options":["Injecting bugs into code","Providing dependencies to a class from outside","A type of SQL injection","A network protocol"],"answer":1,"topic":"Design Patterns","difficulty":"medium"},
  {"q":"What is the purpose of an index in a database?","options":["Store backup data","Speed up data retrieval","Encrypt data","Compress tables"],"answer":1,"topic":"Databases","difficulty":"easy"},
  {"q":"In Agile, what is a sprint retrospective?","options":["A planning meeting","A meeting to reflect on what went well and what to improve","A demo to stakeholders","A daily standup"],"answer":1,"topic":"Agile","difficulty":"easy"},
  {"q":"What is WebSocket used for?","options":["Static file serving","Full-duplex real-time communication","Email transfer","Database queries"],"answer":1,"topic":"Networking","difficulty":"medium"},
  {"q":"Which caching strategy writes data to cache and DB simultaneously?","options":["Cache-aside","Write-through","Write-back","Read-through"],"answer":1,"topic":"System Design","difficulty":"medium"},
  {"q":"What is a JWT token used for?","options":["Data storage","Stateless authentication","File compression","Code compilation"],"answer":1,"topic":"Security","difficulty":"easy"},
  {"q":"What is eventual consistency?","options":["Immediate consistency everywhere","System will become consistent given enough time","No consistency","Partial consistency"],"answer":1,"topic":"System Design","difficulty":"medium"},
  {"q":"What is test-driven development (TDD)?","options":["Testing after deployment","Writing tests before writing code","Manual testing only","No testing required"],"answer":1,"topic":"Testing","difficulty":"easy"},
  {"q":"What is the Observer design pattern?","options":["One object watches another for state changes","A singleton variant","A sorting pattern","A database pattern"],"answer":0,"topic":"Design Patterns","difficulty":"medium"},
  {"q":"What is a reverse proxy?","options":["A proxy that blocks traffic","A server that forwards requests to backend servers","A VPN","A firewall"],"answer":1,"topic":"Networking","difficulty":"medium"},
  {"q":"What is the purpose of Docker Compose?","options":["Build Docker images","Define and run multi-container applications","Monitor containers","Deploy to Kubernetes"],"answer":1,"topic":"Docker","difficulty":"medium"},
  {"q":"What is memoization?","options":["A type of memory leak","Caching results of expensive function calls","A debugging technique","A logging strategy"],"answer":1,"topic":"Algorithms","difficulty":"medium"},
  {"q":"What is the purpose of a message queue?","options":["Direct synchronous communication","Asynchronous decoupled communication between services","Database replication","File storage"],"answer":1,"topic":"System Design","difficulty":"medium"},
],
"Data Analyst": [
  {"q":"What does the SQL GROUP BY clause do?","options":["Sorts results","Groups rows sharing a property for aggregation","Filters rows","Joins tables"],"answer":1,"topic":"SQL","difficulty":"easy"},
  {"q":"Which chart is best for showing proportions of a whole?","options":["Line chart","Pie chart","Scatter plot","Histogram"],"answer":1,"topic":"Visualization","difficulty":"easy"},
  {"q":"In Excel, which function finds a lookup value in a table?","options":["SUM","VLOOKUP","COUNT","IF"],"answer":1,"topic":"Excel","difficulty":"easy"},
  {"q":"What is a p-value in statistics?","options":["Probability of results at least as extreme assuming null hypothesis is true","The mean of the dataset","A correlation coefficient","The standard deviation"],"answer":0,"topic":"Statistics","difficulty":"medium"},
  {"q":"Which Python library is used for data visualization?","options":["Pandas","Matplotlib","SQLAlchemy","Flask"],"answer":1,"topic":"Python","difficulty":"easy"},
  {"q":"What is a KPI?","options":["Key Performance Indicator","Key Python Interface","Kernel Processing Index","Knowledge Pattern Identifier"],"answer":0,"topic":"Business","difficulty":"easy"},
  {"q":"What does a LEFT JOIN return?","options":["Only matching rows","All rows from left table and matching from right","All rows from right table","Cartesian product"],"answer":1,"topic":"SQL","difficulty":"easy"},
  {"q":"What is the difference between mean and median?","options":["They are the same","Mean is the average; median is the middle value","Mean is the mode; median is the range","Median is the average; mean is the middle value"],"answer":1,"topic":"Statistics","difficulty":"easy"},
  {"q":"In Tableau, what is a calculated field?","options":["A pre-built metric","A custom field created using formulas","An imported CSV column","A filter"],"answer":1,"topic":"BI Tools","difficulty":"easy"},
  {"q":"What is data normalization?","options":["Deleting duplicates","Scaling data to a standard range","Backing up data","Encrypting data"],"answer":1,"topic":"Data Cleaning","difficulty":"easy"},
  {"q":"Which SQL function counts non-NULL values?","options":["SUM()","COUNT()","AVG()","MAX()"],"answer":1,"topic":"SQL","difficulty":"easy"},
  {"q":"What is a correlation coefficient?","options":["A measure of data size","A measure of linear relationship between two variables","A sorting metric","A data type"],"answer":1,"topic":"Statistics","difficulty":"medium"},
  {"q":"What is a pivot table used for?","options":["Data encryption","Summarizing and reorganizing data","Writing macros","Creating charts only"],"answer":1,"topic":"Excel","difficulty":"easy"},
  {"q":"In Power BI, what is DAX?","options":["Data Analysis Expressions","Database Access XML","Dynamic Application Extension","Data Archive eXport"],"answer":0,"topic":"BI Tools","difficulty":"medium"},
  {"q":"What is the purpose of data profiling?","options":["Visualize data","Examine data for quality, structure, and content","Delete data","Encrypt data"],"answer":1,"topic":"Data Cleaning","difficulty":"easy"},
  {"q":"What is an outlier?","options":["A common data point","A data point significantly different from others","A missing value","A duplicate row"],"answer":1,"topic":"Statistics","difficulty":"easy"},
  {"q":"Which Pandas function reads a CSV file?","options":["pd.open_csv()","pd.read_csv()","pd.load_csv()","pd.import_csv()"],"answer":1,"topic":"Python","difficulty":"easy"},
  {"q":"What is A/B testing?","options":["A debugging method","Comparing two versions to see which performs better","A data storage format","A visualization type"],"answer":1,"topic":"Statistics","difficulty":"medium"},
  {"q":"What does ETL stand for?","options":["Extract, Transform, Load","Edit, Transfer, Log","Encode, Translate, Link","Export, Test, Load"],"answer":0,"topic":"ETL","difficulty":"easy"},
  {"q":"In SQL, what is a subquery?","options":["A backup query","A query nested inside another query","A delete operation","A schema definition"],"answer":1,"topic":"SQL","difficulty":"medium"},
  {"q":"What is a box plot used to display?","options":["Trends over time","Distribution through quartiles and outliers","Proportions","Correlations"],"answer":1,"topic":"Visualization","difficulty":"easy"},
  {"q":"What is the purpose of the DISTINCT keyword in SQL?","options":["Sort results","Remove duplicate rows from results","Count rows","Group data"],"answer":1,"topic":"SQL","difficulty":"easy"},
  {"q":"What is regression analysis?","options":["A classification method","Modeling the relationship between dependent and independent variables","A clustering technique","A data cleaning method"],"answer":1,"topic":"Statistics","difficulty":"medium"},
  {"q":"Which chart type best shows trends over time?","options":["Pie chart","Bar chart","Line chart","Treemap"],"answer":2,"topic":"Visualization","difficulty":"easy"},
  {"q":"What is data wrangling?","options":["Data deletion","Cleaning and transforming raw data into a usable format","Data encryption","Data visualization"],"answer":1,"topic":"Data Cleaning","difficulty":"easy"},
  {"q":"What is the mode in a dataset?","options":["The average","The middle value","The most frequent value","The range"],"answer":2,"topic":"Statistics","difficulty":"easy"},
  {"q":"In SQL, what does COALESCE do?","options":["Joins tables","Returns the first non-NULL value from a list","Sorts data","Deletes NULL values"],"answer":1,"topic":"SQL","difficulty":"medium"},
  {"q":"What is a funnel chart used for?","options":["Showing geographic data","Displaying stages in a process and drop-offs","Comparing categories","Showing distributions"],"answer":1,"topic":"Visualization","difficulty":"easy"},
  {"q":"What is the Central Limit Theorem?","options":["Sample means approximate normal distribution as sample size grows","All data is normally distributed","Variance equals zero for large samples","Mean equals median always"],"answer":0,"topic":"Statistics","difficulty":"hard"},
  {"q":"What does the Pandas .groupby() method do?","options":["Sorts data","Groups data for aggregation","Merges dataframes","Drops duplicates"],"answer":1,"topic":"Python","difficulty":"easy"},
  {"q":"What is cohort analysis?","options":["Analyzing all users together","Grouping users by shared characteristics over time","A machine learning technique","A database design method"],"answer":1,"topic":"Business","difficulty":"medium"},
  {"q":"What is a heat map?","options":["A geographic map","A visualization using color intensity to represent values","A type of filter","A data cleaning tool"],"answer":1,"topic":"Visualization","difficulty":"easy"},
  {"q":"What is the difference between COUNT(*) and COUNT(column)?","options":["They are the same","COUNT(*) counts all rows; COUNT(column) counts non-NULL values","COUNT(*) is slower","COUNT(column) counts all rows"],"answer":1,"topic":"SQL","difficulty":"medium"},
  {"q":"What is the purpose of INDEX-MATCH in Excel?","options":["Creating charts","Flexible lookup alternative to VLOOKUP","Data validation","Macro recording"],"answer":1,"topic":"Excel","difficulty":"medium"},
  {"q":"What is standard deviation?","options":["The average value","A measure of data spread around the mean","The maximum value","The data range"],"answer":1,"topic":"Statistics","difficulty":"easy"},
],
"DevOps Engineer": [
  {"q":"What is Infrastructure as Code (IaC)?","options":["Writing code in infrastructure","Managing infrastructure through machine-readable definition files","A programming language","A type of database"],"answer":1,"topic":"IaC","difficulty":"easy"},
  {"q":"Which tool is used for container orchestration?","options":["Docker","Kubernetes","Jenkins","Terraform"],"answer":1,"topic":"Kubernetes","difficulty":"easy"},
  {"q":"What does CI in CI/CD stand for?","options":["Code Integration","Continuous Integration","Central Infrastructure","Container Isolation"],"answer":1,"topic":"CI/CD","difficulty":"easy"},
  {"q":"What is a Dockerfile?","options":["A log file","A script with instructions to build a Docker image","A configuration for Kubernetes","A monitoring dashboard"],"answer":1,"topic":"Docker","difficulty":"easy"},
  {"q":"What is Terraform used for?","options":["Application monitoring","Infrastructure provisioning and management","Code testing","Container runtime"],"answer":1,"topic":"IaC","difficulty":"easy"},
  {"q":"In Kubernetes, what is a Pod?","options":["A network policy","The smallest deployable unit containing one or more containers","A storage volume","A node"],"answer":1,"topic":"Kubernetes","difficulty":"easy"},
  {"q":"What is a reverse proxy?","options":["A client-side proxy","A server that forwards requests to backend servers on behalf of clients","A VPN","A firewall rule"],"answer":1,"topic":"Networking","difficulty":"easy"},
  {"q":"What does Prometheus monitor?","options":["Code quality","System and application metrics","Container images","Infrastructure cost"],"answer":1,"topic":"Monitoring","difficulty":"easy"},
  {"q":"What is a Helm chart?","options":["A monitoring dashboard","A package of Kubernetes resources","A Docker image","A CI/CD pipeline"],"answer":1,"topic":"Kubernetes","difficulty":"medium"},
  {"q":"What is the purpose of a health check endpoint?","options":["Test API performance","Verify that a service is running and healthy","Monitor user activity","Backup data"],"answer":1,"topic":"Monitoring","difficulty":"easy"},
  {"q":"What is GitOps?","options":["Using Git for code storage only","Using Git as the single source of truth for infrastructure and deployments","A testing framework","A database versioning tool"],"answer":1,"topic":"CI/CD","difficulty":"medium"},
  {"q":"Which tool is used for secrets management?","options":["GitHub","HashiCorp Vault","Docker Hub","Grafana"],"answer":1,"topic":"Security","difficulty":"medium"},
  {"q":"What is a rolling deployment?","options":["Deploying all at once","Gradually replacing instances of the old version with the new","Reverting to a previous version","Testing in staging only"],"answer":1,"topic":"CI/CD","difficulty":"medium"},
  {"q":"What is the ELK stack?","options":["Elasticsearch, Logstash, Kibana","Envoy, Linux, Kubernetes","Elastic, Lambda, Kafka","Endpoint, Load, Key"],"answer":0,"topic":"Monitoring","difficulty":"easy"},
  {"q":"In Linux, what does chmod 755 mean?","options":["Delete all files","Owner: rwx, Group: r-x, Others: r-x","Read-only for everyone","Full access for everyone"],"answer":1,"topic":"Linux","difficulty":"medium"},
  {"q":"What is a canary deployment?","options":["Deploying to all users","Releasing to a small subset of users before full rollout","A rollback strategy","A testing environment"],"answer":1,"topic":"CI/CD","difficulty":"medium"},
  {"q":"What is the purpose of an ingress controller in Kubernetes?","options":["Manage storage","Manage external access to services in a cluster","Monitor pods","Scale deployments"],"answer":1,"topic":"Kubernetes","difficulty":"medium"},
  {"q":"What is Ansible used for?","options":["Container orchestration","Configuration management and automation","Code compilation","Database management"],"answer":1,"topic":"IaC","difficulty":"easy"},
  {"q":"What is a service mesh?","options":["A network of services with built-in observability, security, and traffic management","A type of VPN","A DNS service","A load balancer"],"answer":0,"topic":"Networking","difficulty":"hard"},
  {"q":"What is the difference between Docker volumes and bind mounts?","options":["They are the same","Volumes are managed by Docker; bind mounts map to host paths directly","Volumes are temporary; bind mounts are persistent","Bind mounts are faster"],"answer":1,"topic":"Docker","difficulty":"medium"},
  {"q":"What is the purpose of a config map in Kubernetes?","options":["Store secrets","Store non-confidential configuration data as key-value pairs","Monitor pods","Manage deployments"],"answer":1,"topic":"Kubernetes","difficulty":"medium"},
  {"q":"What is SRE (Site Reliability Engineering)?","options":["A programming language","Applying software engineering to operations problems","A monitoring tool","A deployment strategy"],"answer":1,"topic":"SRE","difficulty":"easy"},
  {"q":"What is the purpose of a load balancer?","options":["Store sessions","Distribute incoming traffic across multiple servers","Encrypt data","Compile code"],"answer":1,"topic":"Networking","difficulty":"easy"},
  {"q":"What is immutable infrastructure?","options":["Infrastructure that changes frequently","Infrastructure that is never modified after deployment; replaced instead","Temporary infrastructure","Infrastructure without monitoring"],"answer":1,"topic":"IaC","difficulty":"medium"},
  {"q":"What is the purpose of Grafana?","options":["Code review","Visualization and dashboarding for metrics","Container orchestration","CI/CD pipelines"],"answer":1,"topic":"Monitoring","difficulty":"easy"},
  {"q":"What is a multi-stage Docker build?","options":["Running multiple containers","Using multiple FROM statements to reduce image size","Deploying to multiple environments","Building on multiple OS"],"answer":1,"topic":"Docker","difficulty":"medium"},
  {"q":"What is the blue-green deployment strategy?","options":["Using two identical environments and switching traffic between them","Deploying to one server at a time","A testing strategy","A branching model"],"answer":0,"topic":"CI/CD","difficulty":"medium"},
  {"q":"What is the purpose of a liveness probe in Kubernetes?","options":["Check if a pod is ready for traffic","Check if a container is still running","Monitor CPU usage","Scale pods"],"answer":1,"topic":"Kubernetes","difficulty":"medium"},
  {"q":"What does shift left mean in DevOps?","options":["Move deployment earlier","Integrate testing and security earlier in the development lifecycle","Shift servers to the left region","Reduce team size"],"answer":1,"topic":"CI/CD","difficulty":"easy"},
  {"q":"What is the purpose of a NAT gateway?","options":["Route traffic between containers","Allow private subnet resources to access the internet","Store DNS records","Monitor network traffic"],"answer":1,"topic":"Networking","difficulty":"medium"},
  {"q":"What is the principle of least privilege?","options":["Give everyone admin access","Grant only minimum permissions needed to perform a task","Disable all access by default","Use only one user account"],"answer":1,"topic":"Security","difficulty":"easy"},
  {"q":"What is a DaemonSet in Kubernetes?","options":["A deployment with replicas","Ensures a copy of a pod runs on all (or some) nodes","A service type","A config object"],"answer":1,"topic":"Kubernetes","difficulty":"medium"},
  {"q":"What is the purpose of Terraform state?","options":["Store application logs","Track the current state of managed infrastructure","Configure CI/CD","Monitor performance"],"answer":1,"topic":"IaC","difficulty":"medium"},
  {"q":"What is a container registry?","options":["A runtime environment","A repository for storing and distributing container images","A monitoring tool","A CI/CD pipeline"],"answer":1,"topic":"Docker","difficulty":"easy"},
  {"q":"What is chaos engineering?","options":["Breaking things randomly","Deliberately introducing failures to test system resilience","A debugging technique","A deployment strategy"],"answer":1,"topic":"SRE","difficulty":"medium"},
],
}


# ─────────────────────────────────────────────
# SKILLS DICTIONARY
# ─────────────────────────────────────────────
SKILLS_DICTIONARY = {
    "Programming": ["python","java","javascript","typescript","scala","r","go","rust","c++",
                     "c#","ruby","kotlin","php","swift","perl","bash","shell","powershell"],
    "Databases": ["sql","mysql","postgresql","postgres","mongodb","cassandra","redis",
                  "dynamodb","oracle","snowflake","redshift","bigquery","hive","hbase",
                  "cockroachdb","couchbase","neo4j","elasticsearch"],
    "Cloud": ["aws","azure","gcp","google cloud","s3","ec2","lambda","iam","cloudformation",
              "cloud","sagemaker","emr","glue","athena","kinesis","azure data factory",
              "azure synapse","azure data lake","cloud storage","cloud functions"],
    "Big Data": ["spark","pyspark","hadoop","mapreduce","kafka","flink","hive","presto",
                 "trino","databricks","delta lake","delta","iceberg","lakehouse"],
    "ETL & Orchestration": ["etl","elt","airflow","dbt","nifi","talend","informatica",
                            "mwaa","dagster","prefect","luigi","cron","orchestration",
                            "data pipeline","pipeline","data integration"],
    "DevOps": ["docker","kubernetes","k8s","terraform","ansible","jenkins","github actions",
               "gitlab ci","helm","prometheus","grafana","datadog","elk","logstash",
               "kibana","argocd","flux","istio","nginx"],
    "Data Concepts": ["data modeling","data warehouse","data warehousing","data lake",
                      "data pipeline","data governance","data quality","data catalog",
                      "medallion","star schema","snowflake schema","data vault","scd",
                      "slowly changing dimension","data lineage","metadata","schema on read",
                      "schema on write","olap","oltp","dimensional modeling","normalization"],
    "BI & Visualization": ["tableau","power bi","powerbi","looker","matplotlib","seaborn",
                           "plotly","d3","superset","qlik","sisense","metabase"],
    "Machine Learning": ["machine learning","deep learning","tensorflow","pytorch",
                         "scikit-learn","sklearn","nlp","computer vision","mlops",
                         "neural network","random forest","xgboost","regression",
                         "classification","clustering"],
    "Software Engineering": ["git","agile","scrum","rest api","restful","graphql",
                             "microservices","ci/cd","cicd","tdd","unit testing",
                             "integration testing","design patterns","solid","oop",
                             "functional programming","websocket","jwt","oauth"],
    "Certifications": ["databricks certified","aws certified","google professional",
                       "azure certified","ckad","cka","terraform associate",
                       "certified data engineer","certified developer",
                       "certified solutions architect","pmp","csm","togaf"],
}

# ─────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────

def add_log(candidate_id, stage, decision, score, reason, next_action, owner="AI_AGENT"):
    entry = {
        "candidate_id": candidate_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stage": stage, "decision": decision, "score": score,
        "reason": reason, "next_action": next_action, "owner": owner,
    }
    st.session_state.pipeline_logs.append(entry)
    return entry


def parse_cv_text(uploaded_file):
    if uploaded_file is None:
        return ""
    file_name = uploaded_file.name.lower()
    try:
        if file_name.endswith(".pdf"):
            try:
                import PyPDF2
                reader = PyPDF2.PdfReader(uploaded_file)
                text = ""
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                return text.strip()
            except ImportError:
                return uploaded_file.read().decode("utf-8", errors="ignore")
        elif file_name.endswith(".txt"):
            return uploaded_file.read().decode("utf-8", errors="ignore")
        elif file_name.endswith(".docx"):
            try:
                import docx
                doc = docx.Document(BytesIO(uploaded_file.read()))
                text = "\n".join([para.text for para in doc.paragraphs])
                return text.strip()
            except ImportError:
                return uploaded_file.read().decode("utf-8", errors="ignore")
        else:
            return uploaded_file.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return f"ERROR_PARSING: {str(e)}"


def extract_skills_from_text(text):
    text_lower = text.lower()
    found_skills = {}
    for category, skills in SKILLS_DICTIONARY.items():
        matched = []
        for skill in skills:
            if len(skill) <= 3:
                pattern = r'\b' + re.escape(skill) + r'\b'
                if re.search(pattern, text_lower):
                    matched.append(skill)
            else:
                if skill in text_lower:
                    matched.append(skill)
        if matched:
            found_skills[category] = list(set(matched))
    return found_skills


def extract_experience_years(text):
    patterns = [
        r'(\d+)\+?\s*(?:years?|yrs?)\s*(?:of)?\s*(?:experience|exp)',
        r'(?:experience|exp)\s*(?:of)?\s*(\d+)\+?\s*(?:years?|yrs?)',
        r'(\d+)\+?\s*(?:years?|yrs?)\s*(?:in|of|working)',
        r'(?:over|more than|approximately|approx|about)\s*(\d+)\s*(?:years?|yrs?)',
    ]
    years_found = []
    text_lower = text.lower()
    for pattern in patterns:
        matches = re.findall(pattern, text_lower)
        for m in matches:
            try:
                y = int(m)
                if 0 < y < 50:
                    years_found.append(y)
            except ValueError:
                pass
    return max(years_found) if years_found else 0


def extract_education(text):
    text_lower = text.lower()
    education_keywords = [
        "bachelor", "master", "phd", "doctorate", "b.tech", "m.tech",
        "b.sc", "m.sc", "bsc", "msc", "b.e.", "m.e.", "mba",
        "computer science", "data science", "information technology",
        "information systems", "software engineering", "statistics",
        "mathematics", "electrical engineering", "electronics",
        "engineering", "university", "college", "degree"
    ]
    return [kw for kw in education_keywords if kw in text_lower]


def calculate_ats_score(cv_text, jd_text, role):
    if not cv_text or "ERROR_PARSING" in cv_text:
        return {
            "ats_score": 0, "decision": "FAIL",
            "reasoning_summary": "CV could not be parsed.",
            "matched_skills": [], "missing_skills": [],
            "experience_match": "Unable to determine",
            "strengths": [], "gaps": ["CV parsing failed"],
            "requires_human_review": True,
            "score_breakdown": {"skill_score":0,"experience_score":0,"education_score":0,"certification_score":0,"tool_platform_score":0},
        }
    cv_skills = extract_skills_from_text(cv_text)
    jd_skills = extract_skills_from_text(jd_text)
    cv_exp = extract_experience_years(cv_text)
    jd_exp = extract_experience_years(jd_text)
    cv_edu = extract_education(cv_text)
    jd_edu = extract_education(jd_text)
    cv_set = set()
    for s in cv_skills.values():
        cv_set.update(s)
    jd_set = set()
    for s in jd_skills.values():
        jd_set.update(s)
    if jd_set:
        matched = cv_set & jd_set
        missing = jd_set - cv_set
        skill_pct = len(matched) / len(jd_set)
    else:
        matched = cv_set
        missing = set()
        skill_pct = 0.5
    skill_score = min(skill_pct * 100, 100) * 0.40
    if jd_exp > 0:
        if cv_exp >= jd_exp:
            exp_score = 100 * 0.20
            exp_match = f"CV: {cv_exp} yrs >= JD: {jd_exp} yrs"
        elif cv_exp >= jd_exp * 0.7:
            exp_score = 75 * 0.20
            exp_match = f"CV: {cv_exp} yrs (slightly below JD: {jd_exp} yrs)"
        else:
            exp_score = max(30, (cv_exp / jd_exp) * 100) * 0.20
            exp_match = f"CV: {cv_exp} yrs < JD: {jd_exp} yrs"
    else:
        exp_score = 60 * 0.20
        exp_match = f"CV: {cv_exp} yrs (JD requirement not clearly specified)"
    if jd_edu:
        edu_pct = len(set(cv_edu) & set(jd_edu)) / len(set(jd_edu))
    else:
        edu_pct = 0.6
    edu_score = min(edu_pct * 100, 100) * 0.15
    cv_certs = cv_skills.get("Certifications", [])
    jd_certs = jd_skills.get("Certifications", [])
    if jd_certs:
        cert_pct = len(set(cv_certs) & set(jd_certs)) / len(set(jd_certs))
    else:
        cert_pct = 0.5 if cv_certs else 0.3
    cert_score = min(cert_pct * 100, 100) * 0.10
    tool_cats = ["Cloud", "Big Data", "DevOps", "BI & Visualization"]
    t_match = t_total = 0
    for cat in tool_cats:
        jt = set(jd_skills.get(cat, []))
        ct = set(cv_skills.get(cat, []))
        t_total += len(jt)
        t_match += len(ct & jt)
    tool_pct = (t_match / t_total) if t_total > 0 else 0.5
    tool_score = min(tool_pct * 100, 100) * 0.15
    total = round(skill_score + exp_score + edu_score + cert_score + tool_score, 1)
    total = min(total, 100)
    strengths = []
    gaps = []
    if jd_set and skill_pct > 0.7:
        strengths.append(f"Strong skill match ({len(matched)}/{len(jd_set)} skills)")
    elif jd_set:
        gaps.append(f"Skill gap: missing {len(missing)} of {len(jd_set)} required skills")
    if cv_exp >= jd_exp and jd_exp > 0:
        strengths.append(f"Meets experience requirement ({cv_exp} yrs)")
    elif jd_exp > 0:
        gaps.append(f"Experience below requirement ({cv_exp} vs {jd_exp} yrs)")
    if edu_pct > 0.5:
        strengths.append("Education aligns with role requirements")
    if cv_certs:
        strengths.append(f"Has relevant certifications: {', '.join(cv_certs)}")
    elif jd_certs:
        gaps.append("No matching certifications found")
    decision = "PASS" if total > 85 else "FAIL"
    requires_review = 75 <= total <= 85
    reasoning = (
        f"ATS Score: {total}/100. "
        f"Skill match: {len(matched)}/{len(jd_set)} required skills found. "
        f"Experience: {exp_match}. "
        f"{'Human review recommended due to borderline score.' if requires_review else ''}"
    )
    return {
        "ats_score": total, "decision": decision,
        "reasoning_summary": reasoning.strip(),
        "matched_skills": sorted(list(matched)),
        "missing_skills": sorted(list(missing)),
        "experience_match": exp_match,
        "strengths": strengths, "gaps": gaps,
        "requires_human_review": requires_review,
        "score_breakdown": {
            "skill_score": round(skill_score, 1),
            "experience_score": round(exp_score, 1),
            "education_score": round(edu_score, 1),
            "certification_score": round(cert_score, 1),
            "tool_platform_score": round(tool_score, 1),
        },
    }


def get_assessment_questions(role, num_questions=30):
    role_key = None
    for key in QUESTION_BANKS:
        if key.lower() in role.lower() or role.lower() in key.lower():
            role_key = key
            break
    if role_key is None:
        role_key = "Software Engineer"
    bank = QUESTION_BANKS[role_key][:]
    random.shuffle(bank)
    return bank[:num_questions]


def score_assessment(questions, answers):
    if not questions or not answers:
        return {"score_percent": 0, "correct": 0, "total": 0, "strength_areas": [], "weak_areas": [], "topic_breakdown": {}}
    correct = 0
    topic_scores = {}
    for i, q in enumerate(questions):
        topic = q.get("topic", "General")
        if topic not in topic_scores:
            topic_scores[topic] = {"correct": 0, "total": 0}
        topic_scores[topic]["total"] += 1
        user_answer = answers.get(str(i), None)
        if user_answer is not None and int(user_answer) == q["answer"]:
            correct += 1
            topic_scores[topic]["correct"] += 1
    total = len(questions)
    score_percent = round((correct / total) * 100, 1) if total > 0 else 0
    strength_areas = []
    weak_areas = []
    for topic, data in topic_scores.items():
        pct = (data["correct"] / data["total"]) * 100 if data["total"] > 0 else 0
        if pct >= 75:
            strength_areas.append(f"{topic} ({data['correct']}/{data['total']})")
        elif pct < 50:
            weak_areas.append(f"{topic} ({data['correct']}/{data['total']})")
    return {"score_percent": score_percent, "correct": correct, "total": total,
            "strength_areas": strength_areas, "weak_areas": weak_areas, "topic_breakdown": topic_scores}


def get_panel_availability(role):
    panels = {
        "Data Engineer": [{"name": "Priya Sharma", "title": "Senior Data Engineer"}, {"name": "James Chen", "title": "Data Engineering Manager"}],
        "Software Engineer": [{"name": "Alex Rivera", "title": "Staff Software Engineer"}, {"name": "Sarah Kim", "title": "Engineering Manager"}],
        "Data Analyst": [{"name": "Michael Brown", "title": "Lead Data Analyst"}, {"name": "Emily Zhang", "title": "Analytics Manager"}],
        "DevOps Engineer": [{"name": "Raj Patel", "title": "Senior DevOps Engineer"}, {"name": "Lisa Johnson", "title": "Platform Engineering Lead"}],
    }
    role_key = None
    for key in panels:
        if key.lower() in role.lower() or role.lower() in key.lower():
            role_key = key
            break
    if role_key is None:
        role_key = "Software Engineer"
    panel = panels[role_key]
    today = datetime.now()
    slots = []
    slot_times = ["09:00 AM", "10:30 AM", "11:30 AM", "01:00 PM", "02:30 PM", "03:30 PM", "04:00 PM"]
    for day_offset in range(1, 4):
        day = today + timedelta(days=day_offset)
        day_str = day.strftime("%A, %B %d, %Y")
        available = random.sample(slot_times, k=random.randint(2, 4))
        available.sort()
        for slot_time in available:
            slots.append({"date": day_str, "time": slot_time, "duration": "45 minutes",
                          "mode": "Video Call (Microsoft Teams)", "panel": [p["name"] for p in panel], "timezone": "UTC"})
    return {"panel": panel, "slots": slots}


def generate_rejection_email(candidate_name, role, stage, recruiter_name):
    if stage == "ATS":
        return f"""Subject: Update on Your Application for {role}

Dear {candidate_name},

Thank you for your interest in the {role} position and for taking the time to apply.

After reviewing your profile, we will not be moving forward with your application for this role at this stage.

We appreciate your interest in our opportunity and encourage you to apply again for future roles that match your experience.

Wishing you all the best in your job search.

Best regards,
{recruiter_name}"""
    else:
        return f"""Subject: Update on Your Application for {role}

Dear {candidate_name},

Thank you for completing the assessment for the {role} role.

After careful evaluation, we will not be moving forward with your application to the next stage.

We appreciate the time and effort you invested in the process and wish you success in your future opportunities.

Best regards,
{recruiter_name}"""


def generate_assessment_email(candidate_name, role, deadline, recruiter_name, candidate_id=None):
    # Generate a unique token and map it to the candidate
    token = hashlib.md5(f"{candidate_name}_{candidate_id}_{datetime.now().isoformat()}".encode()).hexdigest()[:16]
    if candidate_id:
        st.session_state.assessment_tokens[token] = candidate_id
    # Link points to the running Streamlit app
    link = f"http://localhost:8501/?assess={token}"
    return f"""Subject: Next Step: Assessment for {role}

Dear {candidate_name},

Thank you for your application for the {role} role.

We are pleased to invite you to complete the next stage of the selection process: an online assessment.

Assessment Details:
- Number of questions: 30
- Duration: 20 minutes
- Link: {link}
- Deadline: {deadline}

Important Instructions:
- Complete the assessment in one sitting.
- Ensure a stable internet connection.
- The assessment runs in full-screen mode.
- Do not switch tabs or windows during the test.
- Copy-paste and tab-switching will be monitored.
- Any suspicious activity will be flagged for review.

Note: This link connects to the assessment portal. If the link does not open, please contact the recruitment team.

If you face any technical difficulties, please reply to this email.

Best regards,
{recruiter_name}"""


def generate_interview_email(candidate_name, role, slots, recruiter_name):
    link = f"https://schedule.talentedge.ai/{hashlib.md5(candidate_name.encode()).hexdigest()[:12]}"
    slot_lines = ""
    for i, slot in enumerate(slots[:6], 1):
        slot_lines += f"  - Slot {i}: {slot['date']} at {slot['time']} ({slot['duration']}, {slot['timezone']})\n"
    return f"""Subject: Interview Scheduling for {role}

Dear {candidate_name},

Congratulations! You have successfully cleared the assessment stage for the {role} position.

We would like to invite you to schedule your interview. Please choose one of the available slots:

{slot_lines}
Interview Details:
- Mode: Video Call (Microsoft Teams)
- Duration: 45 minutes
- Scheduling Link: {link}

If none of these slots work for you, please reply to this email and our team will assist you.

Best regards,
{recruiter_name}"""



# ═════════════════════════════════════════════
# STYLED SIDEBAR
# ═════════════════════════════════════════════
st.sidebar.markdown("""
<div style="text-align:center; padding: 1rem 0;">
    <span style="font-size:2.5rem;">🚀</span><br>
    <span style="font-family:'Poppins',sans-serif; font-size:1.3rem; font-weight:800; color:#F1F5F9 !important;">TalentEdge AI</span><br>
    <span style="font-size:0.8rem; color:#94A3B8 !important;">Recruitment Platform</span>
</div>
""", unsafe_allow_html=True)
st.sidebar.markdown("---")

_default_page_idx = 0
if st.session_state.get("_arrived_via_link"):
    _default_page_idx = 1

page = st.sidebar.radio(
    "Navigation",
    ["📄 CV Upload & ATS", "📝 Assessment", "📊 Results & Interview",
     "📋 Pipeline Logs", "📧 Email Log", "👤 Candidate Dashboard"],
    index=_default_page_idx,
)

st.sidebar.markdown("---")
st.sidebar.markdown("### 📧 Email Automation")
st.session_state.auto_email_enabled = st.sidebar.checkbox(
    "Enable Auto Email Sending", value=st.session_state.auto_email_enabled,
    help="When enabled, emails are sent automatically at each pipeline stage."
)

with st.sidebar.expander("⚙️ SMTP Configuration"):
    st.session_state.smtp_server = st.text_input("SMTP Server", value=st.session_state.smtp_server, key="sb_smtp_server")
    st.session_state.smtp_port = st.number_input("SMTP Port", value=st.session_state.smtp_port, min_value=1, max_value=65535, key="sb_smtp_port")
    st.session_state.sender_email = st.text_input("Sender Email", value=st.session_state.sender_email, key="sb_sender_email")
    st.session_state.sender_password = st.text_input("Sender Password (App Password)", value=st.session_state.sender_password, type="password", key="sb_sender_pwd")
    if st.session_state.sender_email and st.session_state.sender_password:
        st.session_state.smtp_configured = True
    else:
        st.session_state.smtp_configured = False
    if st.button("🔌 Test SMTP Connection"):
        if not st.session_state.smtp_configured:
            st.error("Please fill in sender email and password first.")
        else:
            try:
                with smtplib.SMTP(st.session_state.smtp_server, st.session_state.smtp_port, timeout=10) as server:
                    server.ehlo(); server.starttls(); server.ehlo()
                    server.login(st.session_state.sender_email, st.session_state.sender_password)
                st.success("✅ SMTP connection successful!")
            except Exception as e:
                st.error(f"❌ Connection failed: {str(e)}")
    st.info("**Gmail:** Use App Password • **Outlook:** smtp-mail.outlook.com:587")

if st.session_state.smtp_configured and st.session_state.auto_email_enabled:
    st.sidebar.success("🟢 Auto-email: ACTIVE")
elif st.session_state.auto_email_enabled:
    st.sidebar.warning("🟡 SMTP not configured")
else:
    st.sidebar.info("⚪ Auto-email: OFF")

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ Recruiter Settings")
st.session_state.recruiter_name = st.sidebar.text_input("Team Name", value=st.session_state.recruiter_name)
st.session_state.recruiter_email = st.sidebar.text_input("Recruiter Email", value=st.session_state.recruiter_email)

if st.session_state.current_candidate_id and st.session_state.current_candidate_id in st.session_state.candidates:
    cand_sb = st.session_state.candidates[st.session_state.current_candidate_id]
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 👤 Active Candidate")
    st.sidebar.markdown(f"**{cand_sb.get('name','N/A')}**")
    st.sidebar.markdown(f"*{cand_sb.get('role','N/A')}*")
    status_sb = cand_sb.get("status", "Pending")
    st.sidebar.markdown(f"Status: **{status_sb}**")

st.sidebar.markdown("---")
if st.sidebar.button("🗑️ Reset All Data"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


def show_automation_results(actions):
    if not actions:
        return
    st.markdown("### ⚡ Automation Actions")
    for act in actions:
        icon = "✅" if act["status"] == "SENT" else ("🟡" if act["status"] == "QUEUED" else "❌")
        st.markdown(f"{icon} **{act['action']}** → `{act['to']}` — **{act['status']}**")
        if act["status"] != "SENT":
            st.caption(f"   {act['detail']}")


# ═════════════════════════════════════════════
# PAGE 1: CV UPLOAD & ATS ANALYSIS
# ═════════════════════════════════════════════
if page == "📄 CV Upload & ATS":
    st.markdown("""
    <div class="hero-banner animate-in">
        <h1>📄 CV Upload & ATS Screening</h1>
        <p>Upload a candidate's CV, analyze it against the job description, and let AI handle the rest — emails, scoring & decisions.</p>
    </div>
    """, unsafe_allow_html=True)

    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.markdown('<div class="section-card"><h3>👤 Candidate Information</h3>', unsafe_allow_html=True)
        c_id = st.text_input("Candidate ID", value=f"CAND-{datetime.now().strftime('%Y%m%d%H%M%S')}")
        c_name = st.text_input("Candidate Name", placeholder="e.g., John Doe")
        c_email = st.text_input("Candidate Email", placeholder="e.g., john@email.com")
        role_options = list(JD_TEMPLATES.keys()) + ["Custom Role"]
        role_applied = st.selectbox("Role Applied For", role_options)
        if role_applied == "Custom Role":
            role_applied = st.text_input("Enter Custom Role Title")
        st.markdown("#### 📎 Upload CV")
        uploaded_cv = st.file_uploader("Upload CV (PDF, TXT, DOCX)", type=["pdf", "txt", "docx"])
        cv_text_manual = st.text_area("Or paste CV text here", height=150)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_right:
        st.markdown('<div class="section-card"><h3>📋 Job Description</h3>', unsafe_allow_html=True)
        if role_applied in JD_TEMPLATES:
            jd_text = st.text_area("Job Description", value=JD_TEMPLATES[role_applied], height=400)
        else:
            jd_text = st.text_area("Enter Job Description", height=400)
        with st.expander("ℹ️ Scoring Methodology"):
            st.markdown("""
| Component | Weight |
|---|---|
| Skill Match | 40% |
| Experience | 20% |
| Education | 15% |
| Certifications | 10% |
| Tools / Platforms | 15% |

**Pass: > 85%** · Borderline (75–85%) = human review
""")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)

    if st.button("🔍 Analyze CV & Generate ATS Score", type="primary", use_container_width=True):
        if not c_name:
            st.error("❌ Please enter the candidate's name.")
        elif not c_email:
            st.error("❌ Please enter the candidate's email.")
        elif not jd_text.strip():
            st.error("❌ Please provide a job description.")
        else:
            cv_text = ""
            if uploaded_cv:
                with st.spinner("Parsing CV..."): cv_text = parse_cv_text(uploaded_cv)
            if not cv_text and cv_text_manual.strip():
                cv_text = cv_text_manual.strip()
            if not cv_text:
                st.error("❌ No CV content found.")
            else:
                with st.spinner("🔄 Analyzing CV against JD..."):
                    result = calculate_ats_score(cv_text, jd_text, role_applied)
                candidate_data = {
                    "id": c_id, "name": c_name, "email": c_email, "role": role_applied,
                    "cv_text": cv_text[:500] + "..." if len(cv_text) > 500 else cv_text,
                    "ats_result": result,
                    "status": "Passed ATS" if result["decision"] == "PASS" else ("Manual Review" if result["requires_human_review"] else "Failed ATS"),
                    "assessment_result": None, "interview_scheduled": False, "emails_sent": [],
                    "interview_slots": [], "interview_panel": [],
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                st.session_state.candidates[c_id] = candidate_data
                st.session_state.current_candidate_id = c_id

                # Score Circle
                score = result["ats_score"]
                dec = result["decision"]
                circ_class = "pass" if dec == "PASS" else ("review" if result["requires_human_review"] else "fail")
                circ_color = "#065F46" if dec == "PASS" else ("#92400E" if result["requires_human_review"] else "#991B1B")
                st.markdown(f"""
                <div style="text-align:center; margin:2rem 0;">
                    <div class="score-circle {circ_class}" style="margin:0 auto;">
                        <div class="score-value" style="color:{circ_color}">{score}</div>
                        <div class="score-label" style="color:{circ_color}">ATS Score</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Result Banner
                if dec == "PASS":
                    st.markdown(f'<div class="result-banner pass-banner">🎉 {c_name} PASSED — Score: {score}% — Moving to Assessment</div>', unsafe_allow_html=True)
                elif result["requires_human_review"]:
                    st.markdown(f'<div class="result-banner review-banner">⚠️ {c_name} scored {score}% — Borderline — Flagged for Human Review</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="result-banner fail-banner">❌ {c_name} did NOT pass — Score: {score}%</div>', unsafe_allow_html=True)

                # Score Breakdown Cards
                breakdown = result.get("score_breakdown", {})
                labels = {"skill_score": ("Skill Match", 40, "stat-blue"), "experience_score": ("Experience", 20, "stat-green"),
                          "education_score": ("Education", 15, "stat-purple"), "certification_score": ("Certifications", 10, "stat-orange"),
                          "tool_platform_score": ("Tools & Platforms", 15, "stat-red")}
                cols = st.columns(5)
                for idx, (comp, val) in enumerate(breakdown.items()):
                    lbl, mx, cls = labels.get(comp, (comp, 20, "stat-blue"))
                    with cols[idx]:
                        st.markdown(f"""
                        <div class="stat-card {cls}">
                            <div class="stat-value">{val}</div>
                            <div class="stat-label">{lbl} (/{mx})</div>
                        </div>""", unsafe_allow_html=True)

                # Matched / Missing Skills
                sk1, sk2 = st.columns(2)
                with sk1:
                    st.markdown("#### ✅ Matched Skills")
                    if result["matched_skills"]:
                        tags = " ".join([f'<span class="skill-tag skill-matched">{s}</span>' for s in result["matched_skills"]])
                        st.markdown(tags, unsafe_allow_html=True)
                    else:
                        st.info("No matched skills found.")
                with sk2:
                    st.markdown("#### ❌ Missing Skills")
                    if result["missing_skills"]:
                        tags = " ".join([f'<span class="skill-tag skill-missing">{s}</span>' for s in result["missing_skills"]])
                        st.markdown(tags, unsafe_allow_html=True)
                    else:
                        st.success("No gaps identified!")

                # Strengths / Gaps
                sg1, sg2 = st.columns(2)
                with sg1:
                    if result.get("strengths"):
                        st.markdown('<div class="section-card" style="border-left:4px solid #10B981;"><h3>💪 Strengths</h3>', unsafe_allow_html=True)
                        for s in result["strengths"]: st.markdown(f"- {s}")
                        st.markdown('</div>', unsafe_allow_html=True)
                with sg2:
                    if result.get("gaps"):
                        st.markdown('<div class="section-card" style="border-left:4px solid #EF4444;"><h3>⚠️ Gaps</h3>', unsafe_allow_html=True)
                        for g in result["gaps"]: st.markdown(f"- {g}")
                        st.markdown('</div>', unsafe_allow_html=True)

                st.markdown(f"**📅 Experience:** {result.get('experience_match', 'N/A')}")

                with st.expander("🔧 Full ATS JSON"):
                    st.json({"candidate_id": c_id, "ats_score": result["ats_score"], "decision": result["decision"],
                             "reasoning_summary": result["reasoning_summary"], "matched_skills": result["matched_skills"],
                             "missing_skills": result["missing_skills"], "experience_match": result["experience_match"],
                             "requires_human_review": result["requires_human_review"]})

                # Auto pipeline actions
                st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)
                if dec == "PASS":
                    add_log(c_id, "ATS_SCREENING", "PASS", result["ats_score"], result["reasoning_summary"], "Send Assessment (Auto)")
                    with st.spinner("⚡ Sending assessment invitation..."):
                        actions = auto_pipeline_action(candidate_data, "ats_pass")
                    candidate_data["status"] = "Assessment Sent"
                    st.session_state.candidates[c_id] = candidate_data
                    show_automation_results(actions)
                    for em in candidate_data.get("emails_sent", []):
                        with st.expander(f"📧 {em['type']} — {em.get('send_status','N/A')}"):
                            st.code(em["content"], language="text")
                    st.info("👉 Navigate to **📝 Assessment** page to proceed.")
                elif result["requires_human_review"]:
                    add_log(c_id, "ATS_SCREENING", "REVIEW", result["ats_score"], "Borderline score", "Escalate to Recruiter")
                else:
                    add_log(c_id, "ATS_SCREENING", "FAIL", result["ats_score"], result["reasoning_summary"], "Send Rejection (Auto)")
                    with st.spinner("⚡ Sending rejection email..."):
                        actions = auto_pipeline_action(candidate_data, "ats_fail")
                    st.session_state.candidates[c_id] = candidate_data
                    show_automation_results(actions)
                    for em in candidate_data.get("emails_sent", []):
                        with st.expander(f"📧 {em['type']} — {em.get('send_status','N/A')}"):
                            st.code(em["content"], language="text")

    render_footer()


# ═════════════════════════════════════════════
# PAGE 2: ASSESSMENT
# ═════════════════════════════════════════════
elif page == "📝 Assessment":
    st.markdown("""
    <div class="hero-banner animate-in">
        <h1>📝 Role-Specific Assessment</h1>
        <p>30 curated questions • 20-minute timer • Anti-cheating monitored • Auto-scored & auto-emailed</p>
    </div>
    """, unsafe_allow_html=True)

    if st.session_state.get("_arrived_via_link"):
        st.success("✅ **Welcome!** You arrived via your assessment invitation link.")
        st.session_state["_arrived_via_link"] = False
        st.query_params.clear()

    cid = st.session_state.current_candidate_id
    if not cid or cid not in st.session_state.candidates:
        st.warning("⚠️ No active candidate. Complete ATS screening first on **📄 CV Upload & ATS**.")
    else:
        cand = st.session_state.candidates[cid]
        status = cand.get("status", "")
        if status in ["Failed ATS"]:
            st.error("❌ This candidate did not pass ATS.")
        elif status in ["Passed Assessment", "Failed Assessment", "Interview Scheduled"]:
            st.info(f"ℹ️ Assessment completed. Status: **{status}**. Check **📊 Results & Interview**.")
        else:
            st.markdown(f"""
            <div class="section-card">
                <strong>Candidate:</strong> {cand['name']} &nbsp;|&nbsp;
                <strong>Role:</strong> {cand['role']} &nbsp;|&nbsp;
                <strong>ATS Score:</strong> {cand['ats_result']['ats_score']}%
            </div>
            """, unsafe_allow_html=True)

            with st.expander("📋 Instructions & Anti-Cheating Notice", expanded=not st.session_state.assessment_started):
                st.markdown("""
**Assessment Details:** 30 MCQs • 20 minutes • Pass: > 90%

**⚠️ Anti-Cheating Policy:**
- Complete in **one sitting** • **Full-screen mode**
- **No tab switching** • Copy-paste monitored
- Suspicious activity will be flagged
""")

            if not st.session_state.assessment_started:
                if st.button("🚀 Start Assessment", type="primary", use_container_width=True):
                    questions = get_assessment_questions(cand["role"], 30)
                    st.session_state.assessment_questions = questions
                    st.session_state.assessment_started = True
                    st.session_state.assessment_answers = {}
                    st.session_state.assessment_submitted = False
                    st.session_state.assessment_start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    add_log(cid, "ASSESSMENT_STARTED", "IN_PROGRESS", "N/A", "Candidate started assessment", "Awaiting submission")
                    st.rerun()
            else:
                questions = st.session_state.get("assessment_questions", [])
                if not questions:
                    st.error("Error loading questions.")
                elif not st.session_state.assessment_submitted:
                    start_time = st.session_state.get("assessment_start_time", "")
                    st.info(f"⏱️ **Started:** {start_time} | **Duration:** 20 min | **Questions:** {len(questions)}")
                    st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)

                    for i, q in enumerate(questions):
                        st.markdown(f"""<div class="question-card">
                            <span class="q-number">Q{i+1}</span> <span class="q-meta">({q.get('topic','')}, {q.get('difficulty','')})</span><br>
                            <strong>{q['q']}</strong>
                        </div>""", unsafe_allow_html=True)
                        key = f"assess_q_{i}"
                        answer = st.radio(f"Answer Q{i+1}:", options=q["options"], key=key, index=None, label_visibility="collapsed")
                        if answer is not None:
                            st.session_state.assessment_answers[str(i)] = q["options"].index(answer)

                    answered = len(st.session_state.assessment_answers)
                    st.markdown(f"**Answered:** {answered} / {len(questions)}")
                    st.progress(answered / len(questions))

                    if st.button("✅ Submit Assessment", type="primary", use_container_width=True):
                        if answered < len(questions):
                            st.warning(f"⚠️ {answered}/{len(questions)} answered. Unanswered = incorrect.")
                        st.session_state.assessment_submitted = True
                        result = score_assessment(questions, st.session_state.assessment_answers)
                        st.session_state.assessment_result = result
                        decision = "PASS" if result["score_percent"] > 90 else "FAIL"
                        result["decision"] = decision
                        cand["assessment_result"] = result
                        cand["status"] = "Passed Assessment" if decision == "PASS" else "Failed Assessment"
                        add_log(cid, "ASSESSMENT", decision, result["score_percent"],
                                f"Score: {result['correct']}/{result['total']} ({result['score_percent']}%)",
                                "Move to Interview (Auto)" if decision == "PASS" else "Send Rejection (Auto)")
                        if decision == "PASS":
                            actions = auto_pipeline_action(cand, "assessment_pass")
                            cand["status"] = "Interview Scheduled"
                        else:
                            actions = auto_pipeline_action(cand, "assessment_fail")
                        cand["auto_actions_assessment"] = actions
                        st.session_state.candidates[cid] = cand
                        st.rerun()
                else:
                    result = st.session_state.get("assessment_result", cand.get("assessment_result", {}))
                    decision = result.get("decision", "FAIL")
                    score_pct = result.get("score_percent", 0)

                    circ_class = "pass" if decision == "PASS" else "fail"
                    circ_color = "#065F46" if decision == "PASS" else "#991B1B"
                    st.markdown(f"""
                    <div style="text-align:center; margin:2rem 0;">
                        <div class="score-circle {circ_class}" style="margin:0 auto;">
                            <div class="score-value" style="color:{circ_color}">{score_pct}%</div>
                            <div class="score-label" style="color:{circ_color}">{"PASSED" if decision == "PASS" else "FAILED"}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    if decision == "PASS":
                        st.markdown(f'<div class="result-banner pass-banner">🎉 Assessment PASSED — {result.get("correct",0)}/{result.get("total",0)} correct</div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="result-banner fail-banner">❌ Assessment FAILED — {result.get("correct",0)}/{result.get("total",0)} correct</div>', unsafe_allow_html=True)

                    with st.expander("📈 Topic Breakdown", expanded=True):
                        for topic, data in result.get("topic_breakdown", {}).items():
                            pct = (data["correct"]/data["total"]*100) if data["total"] > 0 else 0
                            st.markdown(f"**{topic}**: {data['correct']}/{data['total']} ({pct:.0f}%)")
                            st.progress(min(pct/100, 1.0))

                    s1, s2 = st.columns(2)
                    with s1:
                        st.markdown("#### 💪 Strong Areas")
                        for s in result.get("strength_areas", []): st.markdown(f"- ✅ {s}")
                    with s2:
                        st.markdown("#### ⚠️ Weak Areas")
                        for w in result.get("weak_areas", []): st.markdown(f"- ❌ {w}")

                    auto_acts = cand.get("auto_actions_assessment", [])
                    if auto_acts:
                        st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)
                        show_automation_results(auto_acts)
                    for em in cand.get("emails_sent", []):
                        with st.expander(f"📧 {em['type']} — {em.get('send_status','N/A')}"):
                            st.code(em["content"], language="text")
                    st.info("👉 Navigate to **📊 Results & Interview** for full details.")

    render_footer()


# ═════════════════════════════════════════════
# PAGE 3: RESULTS & INTERVIEW
# ═════════════════════════════════════════════
elif page == "📊 Results & Interview":
    st.markdown("""
    <div class="hero-banner animate-in">
        <h1>📊 Results & Interview Scheduling</h1>
        <p>Comprehensive results overview with automated interview scheduling</p>
    </div>
    """, unsafe_allow_html=True)

    cid = st.session_state.current_candidate_id
    if not cid or cid not in st.session_state.candidates:
        st.warning("⚠️ No active candidate.")
    else:
        cand = st.session_state.candidates[cid]
        st.markdown(f"""
        <div class="section-card">
            <strong>{cand['name']}</strong> &nbsp;|&nbsp; {cand['role']} &nbsp;|&nbsp;
            <span class="status-badge {'badge-pass' if 'Pass' in cand.get('status','') or 'Interview' in cand.get('status','') else ('badge-fail' if 'Fail' in cand.get('status','') else 'badge-pending')}">{cand.get('status','Pending')}</span>
        </div>
        """, unsafe_allow_html=True)

        with st.expander("📄 ATS Summary"):
            ats = cand.get("ats_result", {})
            if ats:
                st.metric("ATS Score", f"{ats.get('ats_score', 0)}/100", delta=ats.get("decision","N/A"))
                st.markdown(f"**Reasoning:** {ats.get('reasoning_summary','N/A')}")

        assessment = cand.get("assessment_result")
        if assessment:
            with st.expander("📝 Assessment Summary", expanded=True):
                a1, a2, a3 = st.columns(3)
                with a1: st.metric("Score", f"{assessment.get('score_percent', 0)}%")
                with a2: st.metric("Result", assessment.get("decision","N/A"))
                with a3: st.metric("Correct", f"{assessment.get('correct',0)}/{assessment.get('total',0)}")

            if assessment.get("decision") == "PASS":
                st.success("🎉 Candidate cleared the assessment! Interview scheduled.")
                st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)
                st.markdown("## 🗓️ Interview Scheduling")
                panel = cand.get("interview_panel", [])
                slots = cand.get("interview_slots", [])
                if not panel or not slots:
                    availability = get_panel_availability(cand["role"])
                    panel = availability["panel"]; slots = availability["slots"]
                st.markdown("### 👥 Interview Panel")
                for p in panel: st.markdown(f"- **{p['name']}** — {p['title']}")
                st.markdown("### 📅 Available Slots")
                if slots:
                    slot_df = pd.DataFrame(slots)
                    slot_df["panel"] = slot_df["panel"].apply(lambda x: ", ".join(x) if isinstance(x, list) else x)
                    st.dataframe(slot_df, use_container_width=True, hide_index=True)
                if cand.get("interview_scheduled"):
                    st.success("✅ Interview invitation sent automatically.")
            elif assessment.get("decision") == "FAIL":
                st.error(f"❌ Scored {assessment.get('score_percent', 0)}% (threshold: >90%).")
        else:
            st.info("ℹ️ Assessment not yet completed.")

        emails = cand.get("emails_sent", [])
        if emails:
            st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)
            st.markdown("### 📬 All Emails")
            for em in emails:
                icon = "✅" if em.get("send_status") == "SENT" else ("🟡" if em.get("send_status") == "QUEUED" else "❌")
                with st.expander(f"{icon} {em['type']} — {em['timestamp']}"):
                    st.code(em["content"], language="text")

        auto_acts = cand.get("auto_actions_assessment", [])
        if auto_acts:
            show_automation_results(auto_acts)

    render_footer()


# ═════════════════════════════════════════════
# PAGE 4: PIPELINE LOGS
# ═════════════════════════════════════════════
elif page == "📋 Pipeline Logs":
    st.markdown("""
    <div class="hero-banner animate-in">
        <h1>📋 Pipeline Decision Logs</h1>
        <p>Full audit trail of all screening decisions with timestamps and reasoning</p>
    </div>
    """, unsafe_allow_html=True)

    logs = st.session_state.pipeline_logs
    if not logs:
        st.info("No pipeline logs yet. Process a candidate to generate logs.")
    else:
        all_cids = list(set(l["candidate_id"] for l in logs))
        filter_cid = st.selectbox("Filter by Candidate ID", ["All"] + all_cids)
        filtered = logs if filter_cid == "All" else [l for l in logs if l["candidate_id"] == filter_cid]

        df = pd.DataFrame(filtered)
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.markdown("### 📈 Stage Timeline")
        for log in filtered:
            icon = {"PASS": "🟢", "FAIL": "🔴", "REVIEW": "🟠", "IN_PROGRESS": "🔵"}.get(log["decision"], "⚪")
            st.markdown(f"{icon} **[{log['timestamp']}]** `{log['stage']}` — **{log['decision']}** (Score: {log['score']}) → {log['next_action']}")

        st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)
        json_str = json.dumps(filtered, indent=2)
        st.download_button("📥 Download Logs as JSON", data=json_str,
                           file_name=f"pipeline_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", mime="application/json")

    render_footer()


# ═════════════════════════════════════════════
# PAGE 5: EMAIL LOG
# ═════════════════════════════════════════════
elif page == "📧 Email Log":
    st.markdown("""
    <div class="hero-banner animate-in">
        <h1>📧 Email Automation Log</h1>
        <p>Track all automated emails — sent, failed, or queued across the pipeline</p>
    </div>
    """, unsafe_allow_html=True)

    email_log = st.session_state.email_log
    if not email_log:
        st.info("No emails processed yet.")
    else:
        total = len(email_log)
        sent = sum(1 for e in email_log if e["status"] == "SENT")
        failed = sum(1 for e in email_log if e["status"] == "FAILED")
        queued = sum(1 for e in email_log if e["status"] == "QUEUED")

        c1, c2, c3, c4 = st.columns(4)
        with c1: st.markdown(f'<div class="stat-card stat-blue"><div class="stat-value">{total}</div><div class="stat-label">Total Emails</div></div>', unsafe_allow_html=True)
        with c2: st.markdown(f'<div class="stat-card stat-green"><div class="stat-value">{sent}</div><div class="stat-label">Sent</div></div>', unsafe_allow_html=True)
        with c3: st.markdown(f'<div class="stat-card stat-red"><div class="stat-value">{failed}</div><div class="stat-label">Failed</div></div>', unsafe_allow_html=True)
        with c4: st.markdown(f'<div class="stat-card stat-orange"><div class="stat-value">{queued}</div><div class="stat-label">Queued</div></div>', unsafe_allow_html=True)

        st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)

        status_filter = st.selectbox("Filter by Status", ["All", "SENT", "FAILED", "QUEUED"])
        filtered_emails = email_log if status_filter == "All" else [e for e in email_log if e["status"] == status_filter]

        if filtered_emails:
            # Timeline view
            for em in filtered_emails:
                tl_class = {"SENT": "timeline-sent", "FAILED": "timeline-failed", "QUEUED": "timeline-queued"}.get(em["status"], "")
                st.markdown(f"""<div class="timeline-item {tl_class}">
                    <strong>{em['type']}</strong> → {em['to']}<br>
                    <small>{em['timestamp']} — <strong>{em['status']}</strong></small>
                </div>""", unsafe_allow_html=True)

            st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)
            df = pd.DataFrame(filtered_emails)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info(f"No emails with status '{status_filter}'.")

        json_str = json.dumps(email_log, indent=2)
        st.download_button("📥 Download Email Log", data=json_str,
                           file_name=f"email_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", mime="application/json")

    render_footer()


# ═════════════════════════════════════════════
# PAGE 6: CANDIDATE DASHBOARD
# ═════════════════════════════════════════════
elif page == "👤 Candidate Dashboard":
    st.markdown("""
    <div class="hero-banner animate-in">
        <h1>👤 Candidate Dashboard</h1>
        <p>Overview of all candidates processed through the recruitment pipeline</p>
    </div>
    """, unsafe_allow_html=True)

    candidates = st.session_state.candidates
    if not candidates:
        st.info("No candidates processed yet. Upload a CV on **📄 CV Upload & ATS** to get started.")
    else:
        total = len(candidates)
        passed_ats = sum(1 for c in candidates.values() if c.get("ats_result", {}).get("decision") == "PASS")
        passed_assess = sum(1 for c in candidates.values() if c.get("assessment_result") and c["assessment_result"].get("decision") == "PASS")
        interviews = sum(1 for c in candidates.values() if c.get("interview_scheduled"))

        c1, c2, c3, c4 = st.columns(4)
        with c1: st.markdown(f'<div class="stat-card stat-blue"><div class="stat-value">{total}</div><div class="stat-label">Total Candidates</div></div>', unsafe_allow_html=True)
        with c2: st.markdown(f'<div class="stat-card stat-green"><div class="stat-value">{passed_ats}</div><div class="stat-label">Passed ATS</div></div>', unsafe_allow_html=True)
        with c3: st.markdown(f'<div class="stat-card stat-purple"><div class="stat-value">{passed_assess}</div><div class="stat-label">Passed Assessment</div></div>', unsafe_allow_html=True)
        with c4: st.markdown(f'<div class="stat-card stat-orange"><div class="stat-value">{interviews}</div><div class="stat-label">Interviews</div></div>', unsafe_allow_html=True)

        st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)

        for cid_key, cand_val in candidates.items():
            status = cand_val.get("status", "Unknown")
            badge_cls = "badge-pass" if "Pass" in status or "Interview" in status else ("badge-fail" if "Fail" in status else ("badge-review" if "Review" in status else "badge-pending"))
            ats_r = cand_val.get("ats_result", {})
            assess_r = cand_val.get("assessment_result") or {}

            with st.expander(f"**{cand_val['name']}** — {cand_val['role']} — {status}"):
                st.markdown(f"""
                <div class="candidate-card">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
                        <strong style="font-size:1.1rem;">{cand_val['name']}</strong>
                        <span class="status-badge {badge_cls}">{status}</span>
                    </div>
                    <div style="color:#64748B; font-size:0.85rem;">
                        ID: {cid_key} &nbsp;|&nbsp; Email: {cand_val.get('email','N/A')} &nbsp;|&nbsp; Created: {cand_val.get('created_at','N/A')}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                i1, i2, i3 = st.columns(3)
                with i1:
                    st.markdown(f"**ATS Score:** {ats_r.get('ats_score', 'N/A')}")
                    st.markdown(f"**ATS Decision:** {ats_r.get('decision', 'N/A')}")
                with i2:
                    st.markdown(f"**Assessment Score:** {assess_r.get('score_percent', 'N/A')}")
                    st.markdown(f"**Assessment Decision:** {assess_r.get('decision', 'N/A')}")
                with i3:
                    st.markdown(f"**Interview:** {'✅ Scheduled' if cand_val.get('interview_scheduled') else '—'}")
                    st.markdown(f"**Emails Sent:** {len(cand_val.get('emails_sent', []))}")

                if st.button(f"🔄 Load {cand_val['name']}", key=f"load_{cid_key}"):
                    st.session_state.current_candidate_id = cid_key
                    st.success(f"Loaded {cand_val['name']} as active candidate.")
                    st.rerun()

    render_footer()
