import streamlit as st
import json
import re
import random
import hashlib
import secrets
import string
import smtplib
import pandas as pd
import db_manager as db
import time
import base64
# from anti_cheat import render_anti_cheat
from datetime import datetime, timedelta
from collections import Counter
from io import BytesIO

import sqlite3

# ─────────────────────────────────────────────
# AUTH DATABASE (SQLite)
# ─────────────────────────────────────────────
AUTH_DB = "recruitment_users.db"

def init_auth_db():
    conn = sqlite3.connect(AUTH_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            company_name TEXT NOT NULL,
            phone_number TEXT,
            password_hash TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            role TEXT DEFAULT 'recruiter',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS assessment_credentials (
            token TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            candidate_id TEXT NOT NULL,
            candidate_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS candidate_assessments (
            candidate_id TEXT PRIMARY KEY,
            candidate_name TEXT NOT NULL,
            candidate_email TEXT,
            role TEXT,
            ats_score REAL,
            ats_decision TEXT,
            assessment_data TEXT,
            status TEXT DEFAULT 'Assessment Sent',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # ═══ END ═══
    conn.commit()
    conn.close()


def _hash_pw(password, salt=None):
    import secrets as _sec
    if salt is None:
        salt = _sec.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return hashed, salt

def db_create_user(full_name, email, company_name, phone, password):
    conn = sqlite3.connect(AUTH_DB)
    try:
        hashed, salt = _hash_pw(password)
        conn.execute(
            "INSERT INTO users (full_name, email, company_name, phone_number, password_hash, password_salt) VALUES (?,?,?,?,?,?)",
            (full_name, email.lower().strip(), company_name, phone, hashed, salt)
        )
        conn.commit()
        return True, "Account created successfully!"
    except sqlite3.IntegrityError:
        return False, "An account with this email already exists."
    except Exception as e:
        return False, f"Error: {str(e)}"
    finally:
        conn.close()

def db_verify_login(email, password):
    conn = sqlite3.connect(AUTH_DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM users WHERE email = ? AND is_active = 1", (email.lower().strip(),)).fetchone()
    conn.close()
    if not row:
        return False, "Invalid email or password."
    hashed, _ = _hash_pw(password, row["password_salt"])
    if hashed != row["password_hash"]:
        return False, "Invalid email or password."
    return True, {
        "id": row["id"], "username": row["email"], "name": row["full_name"],
        "email": row["email"], "company": row["company_name"], "role": row["role"],
    }

def db_get_user_count():
    conn = sqlite3.connect(AUTH_DB)
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    return count

def db_save_candidate_for_assessment(candidate_id, cand_data):
    """Save candidate info to SQLite so candidate's session can access it."""
    conn = sqlite3.connect(AUTH_DB)
    conn.execute(
        "INSERT OR REPLACE INTO candidate_assessments (candidate_id, candidate_name, candidate_email, role, ats_score, ats_decision, status) VALUES (?,?,?,?,?,?,?)",
        (candidate_id, cand_data.get("name",""), cand_data.get("email",""),
         cand_data.get("role",""), cand_data.get("ats_result",{}).get("ats_score",0),
         cand_data.get("ats_result",{}).get("decision",""), cand_data.get("status",""))
    )
    conn.commit()
    conn.close()


def db_get_candidate_assessment(candidate_id):
    """Get candidate info from SQLite."""
    conn = sqlite3.connect(AUTH_DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM candidate_assessments WHERE candidate_id = ?", (candidate_id,)).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def db_save_assessment_result(candidate_id, result_json, status):
    """Save assessment result to SQLite."""
    conn = sqlite3.connect(AUTH_DB)
    conn.execute(
        "UPDATE candidate_assessments SET assessment_data = ?, status = ? WHERE candidate_id = ?",
        (result_json, status, candidate_id)
    )
    conn.commit()
    conn.close()    

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="TalentEdge AI Recruitment Platform",
    page_icon="\U0001f680",
    layout="wide",
    initial_sidebar_state="expanded",
)

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
    "assessment_credentials": {},
    "_assess_token": None,
    "_candidate_authenticated": False,
    "_candidate_cid": None,
    "_candidate_mode": False,
    # Authentication
    "authenticated": False,
    "current_user": None,
    "users_db": {},  # Using SQLite database
    # Theme
    "theme": "dark",
    "show_landing": True,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

init_auth_db()
db.init()
db.sync_candidates_to_session(st.session_state)


# ═══ TEMPORARY DEBUG — remove after testing ═══
import db_manager as _dbg
_test = _dbg.get_all_candidates()
for _tid, _tc in _test.items():
    _ar = _tc.get("assessment_result")
    print(f"[DEBUG] Candidate {_tid}: status={_tc.get('status')}, has_assessment={_ar is not None}, type={type(_ar)}")
# ═══ END DEBUG ═══


# Load persisted SMTP settings
if not st.session_state.sender_email:
    st.session_state.sender_email = db.get_setting("smtp_email", "")
    st.session_state.sender_password = db.get_setting("smtp_password", "")
    st.session_state.smtp_server = db.get_setting("smtp_server", "smtp.gmail.com")
    st.session_state.smtp_port = int(db.get_setting("smtp_port", "587"))
    if st.session_state.sender_email and st.session_state.sender_password:
        st.session_state.smtp_configured = True


# ─────────────────────────────────────────────
# DYNAMIC CSS THEME (Dark / Light)
# ─────────────────────────────────────────────
def get_theme_css():
    theme = st.session_state.get("theme", "dark")
    if theme == "dark":
        return """
        :root {
            --bg-primary: #0F172A; --bg-secondary: #1E293B; --bg-tertiary: #334155;
            --text-primary: #F1F5F9; --text-secondary: #CBD5E1; --text-muted: #94A3B8;
            --card-bg: #1E293B; --card-border: #334155; --card-shadow: rgba(0,0,0,0.3);
            --card-hover-shadow: rgba(0,0,0,0.5);
            --sidebar-bg-start: #0F172A; --sidebar-bg-end: #020617;
            --sidebar-text: #CBD5E1; --sidebar-heading: #F1F5F9; --sidebar-hr: #334155;
            --input-bg: #334155; --input-border: #475569; --input-text: #F1F5F9;
            --expander-bg: #1E293B; --expander-border: #334155;
            --table-header: #334155; --table-row-alt: #1E293B;
            --primary: #6366F1; --primary-light: #818CF8; --primary-dark: #4F46E5;
            --success: #10B981; --danger: #EF4444; --warning: #F59E0B; --info: #3B82F6;
            --hero-start: #4F46E5; --hero-mid: #7C3AED; --hero-end: #EC4899;
        }
        .main .block-container { background-color: #0F172A; }
        .stApp { background-color: #0F172A; }
        """
    else:
        return """
        :root {
            --bg-primary: #FFFFFF; --bg-secondary: #F8FAFC; --bg-tertiary: #F1F5F9;
            --text-primary: #1E293B; --text-secondary: #64748B; --text-muted: #94A3B8;
            --card-bg: #FFFFFF; --card-border: #E2E8F0; --card-shadow: rgba(0,0,0,0.06);
            --card-hover-shadow: rgba(0,0,0,0.12);
            --sidebar-bg-start: #1E293B; --sidebar-bg-end: #0F172A;
            --sidebar-text: #CBD5E1; --sidebar-heading: #F1F5F9; --sidebar-hr: #334155;
            --input-bg: #FFFFFF; --input-border: #E2E8F0; --input-text: #1E293B;
            --expander-bg: #FFFFFF; --expander-border: #E2E8F0;
            --table-header: #F1F5F9; --table-row-alt: #F8FAFC;
            --primary: #4F46E5; --primary-light: #818CF8; --primary-dark: #3730A3;
            --success: #10B981; --danger: #EF4444; --warning: #F59E0B; --info: #3B82F6;
            --hero-start: #4F46E5; --hero-mid: #7C3AED; --hero-end: #EC4899;
        }
        .main .block-container { background-color: #FFFFFF; }
        .stApp { background-color: #F8FAFC; }
        """

STATIC_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Poppins:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
.main .block-container { padding-top: 1rem; padding-bottom: 4rem; max-width: 1200px; }

/* ── Sidebar ── */
[data-testid="stSidebar"] { background: linear-gradient(180deg, var(--sidebar-bg-start), var(--sidebar-bg-end)) !important; }
[data-testid="stSidebar"] * { color: var(--sidebar-text) !important; }
[data-testid="stSidebar"] .stMarkdown h1, [data-testid="stSidebar"] .stMarkdown h2, [data-testid="stSidebar"] .stMarkdown h3 { color: var(--sidebar-heading) !important; }
[data-testid="stSidebar"] hr { border-color: var(--sidebar-hr) !important; }
[data-testid="stSidebar"] .stButton > button { border-radius: 10px !important; font-weight: 600 !important; }
[data-testid="stSidebar"] input, [data-testid="stSidebar"] textarea, [data-testid="stSidebar"] select { color: #F1F5F9 !important; background-color: #334155 !important; border: 1px solid #475569 !important; border-radius: 8px !important; }
[data-testid="stSidebar"] .stNumberInput input { color: #F1F5F9 !important; background-color: #334155 !important; }

/* ── Hero Banner ── */
.hero-banner {
    background: linear-gradient(135deg, var(--hero-start) 0%, var(--hero-mid) 50%, var(--hero-end) 100%);
    color: white; padding: 2.5rem 3rem; border-radius: 20px; margin-bottom: 2rem;
    box-shadow: 0 20px 60px rgba(79,70,229,0.3); position: relative; overflow: hidden;
}
.hero-banner::before { content:''; position:absolute; top:-50%; right:-20%; width:400px; height:400px; border-radius:50%; background:rgba(255,255,255,0.08); }
.hero-banner::after { content:''; position:absolute; bottom:-30%; left:-10%; width:300px; height:300px; border-radius:50%; background:rgba(255,255,255,0.05); }
.hero-banner h1 { font-family:'Poppins',sans-serif; font-size:2.2rem; font-weight:800; margin-bottom:0.5rem; position:relative; z-index:1; }
.hero-banner p { font-size:1.1rem; opacity:0.9; margin:0; position:relative; z-index:1; }

/* ── Stat Cards ── */
.stat-card {
    background: var(--card-bg); border-radius:16px; padding:1.5rem;
    box-shadow: 0 4px 20px var(--card-shadow); transition: all 0.3s ease;
    border: 1px solid var(--card-border); text-align:center; position:relative; overflow:hidden;
}
.stat-card:hover { transform:translateY(-4px); box-shadow:0 12px 40px var(--card-hover-shadow); }
.stat-card .stat-value { font-family:'Poppins',sans-serif; font-size:2.2rem; font-weight:800; line-height:1.2; }
.stat-card .stat-label { font-size:0.85rem; color:var(--text-muted); font-weight:500; text-transform:uppercase; letter-spacing:0.05em; margin-top:0.3rem; }
.stat-card::before { content:''; position:absolute; top:0; left:0; right:0; height:4px; }
.stat-blue::before { background: linear-gradient(90deg, #4F46E5, #818CF8); } .stat-blue .stat-value { color: #6366F1; }
.stat-green::before { background: linear-gradient(90deg, #10B981, #34D399); } .stat-green .stat-value { color: #10B981; }
.stat-red::before { background: linear-gradient(90deg, #EF4444, #F87171); } .stat-red .stat-value { color: #EF4444; }
.stat-orange::before { background: linear-gradient(90deg, #F59E0B, #FBBF24); } .stat-orange .stat-value { color: #F59E0B; }
.stat-purple::before { background: linear-gradient(90deg, #7C3AED, #A78BFA); } .stat-purple .stat-value { color: #7C3AED; }

/* ── Score Circle ── */
.score-circle { width:160px; height:160px; border-radius:50%; display:flex; flex-direction:column; align-items:center; justify-content:center; margin:0 auto 1rem; font-family:'Poppins',sans-serif; box-shadow:0 8px 30px rgba(0,0,0,0.12); }
.score-circle.pass { background:linear-gradient(135deg,#D1FAE5,#A7F3D0); border:4px solid #10B981; }
.score-circle.fail { background:linear-gradient(135deg,#FEE2E2,#FECACA); border:4px solid #EF4444; }
.score-circle.review { background:linear-gradient(135deg,#FEF3C7,#FDE68A); border:4px solid #F59E0B; }
.score-circle .score-value { font-size:2.5rem; font-weight:800; line-height:1; }
.score-circle .score-label { font-size:0.75rem; font-weight:600; text-transform:uppercase; letter-spacing:0.1em; }

/* ── Skill Tags ── */
.skill-tag { display:inline-block; padding:0.35rem 0.9rem; border-radius:50px; font-size:0.8rem; font-weight:600; margin:0.2rem; transition:transform 0.2s ease; }
.skill-tag:hover { transform:scale(1.05); }
.skill-matched { background:#D1FAE5; color:#065F46; border:1px solid #A7F3D0; }
.skill-missing { background:#FEE2E2; color:#991B1B; border:1px solid #FECACA; }

/* ── Banners ── */
.result-banner { padding:1.2rem 2rem; border-radius:14px; font-size:1.1rem; font-weight:700; text-align:center; margin:1rem 0; animation:fadeIn 0.5s ease; }
.pass-banner { background:linear-gradient(135deg,#D1FAE5,#A7F3D0); color:#065F46; border:2px solid #10B981; }
.fail-banner { background:linear-gradient(135deg,#FEE2E2,#FECACA); color:#991B1B; border:2px solid #EF4444; }
.review-banner { background:linear-gradient(135deg,#FEF3C7,#FDE68A); color:#92400E; border:2px solid #F59E0B; }

/* ── Section Card ── */
.section-card { background:var(--card-bg); border-radius:16px; padding:2rem; box-shadow:0 4px 20px var(--card-shadow); border:1px solid var(--card-border); margin-bottom:1.5rem; }
.section-card h3 { font-family:'Poppins',sans-serif; color:var(--text-primary); margin-bottom:1rem; }

/* ── Question Card ── */
.question-card { background:var(--bg-secondary); border:1px solid var(--card-border); border-radius:12px; padding:1.2rem 1.5rem; margin-bottom:1rem; border-left:4px solid var(--primary); }
.question-card .q-number { color:var(--primary); font-weight:700; font-size:0.85rem; }
.question-card .q-meta { color:var(--text-muted); font-size:0.75rem; }

/* ── Timeline ── */
.timeline-item { border-left:3px solid var(--card-border); padding:0.8rem 0 0.8rem 1.5rem; position:relative; margin-left:0.5rem; }
.timeline-item::before { content:''; width:12px; height:12px; border-radius:50%; position:absolute; left:-7.5px; top:1.2rem; }
.timeline-sent::before { background:#10B981; } .timeline-failed::before { background:#EF4444; } .timeline-queued::before { background:#F59E0B; }
.timeline-item strong { color: var(--text-primary); }
.timeline-item small { color: var(--text-secondary); }

/* ── Candidate Card ── */
.candidate-card { background:var(--card-bg); border-radius:14px; padding:1.5rem; box-shadow:0 2px 12px var(--card-shadow); border:1px solid var(--card-border); transition:all 0.3s ease; margin-bottom:1rem; }
.candidate-card:hover { box-shadow:0 8px 30px var(--card-hover-shadow); border-color:#818CF8; }

/* ── Status Badges ── */
.status-badge { display:inline-block; padding:0.25rem 0.8rem; border-radius:50px; font-size:0.75rem; font-weight:700; text-transform:uppercase; letter-spacing:0.05em; }
.badge-pass { background:#D1FAE5; color:#065F46; } .badge-fail { background:#FEE2E2; color:#991B1B; }
.badge-review { background:#FEF3C7; color:#92400E; } .badge-pending { background:#DBEAFE; color:#1E40AF; }
.badge-interview { background:#EDE9FE; color:#5B21B6; }

/* ── Gradient Divider ── */
.gradient-divider { height:3px; background:linear-gradient(90deg, var(--primary), #7C3AED, #EC4899, transparent); border:none; border-radius:2px; margin:2rem 0; }

/* ── Footer ── */
.footer { text-align:center; padding:2rem 0 1rem; margin-top:3rem; border-top:1px solid var(--card-border); color:var(--text-muted); font-size:0.85rem; }
.footer a { color:var(--primary); text-decoration:none; font-weight:600; }

/* ── LANDING PAGE ── */
.landing-hero {
    background: linear-gradient(135deg, #0F172A 0%, #1E1B4B 30%, #312E81 60%, #4F46E5 100%);
    color:white; padding:5rem 3rem 4rem; border-radius:24px; margin-bottom:3rem; text-align:center;
    position:relative; overflow:hidden;
}
.landing-hero::before { content:''; position:absolute; top:-100px; right:-100px; width:500px; height:500px; border-radius:50%; background:radial-gradient(circle, rgba(99,102,241,0.3), transparent); }
.landing-hero::after { content:''; position:absolute; bottom:-150px; left:-100px; width:600px; height:600px; border-radius:50%; background:radial-gradient(circle, rgba(124,58,237,0.2), transparent); }
.landing-hero h1 { font-family:'Poppins',sans-serif; font-size:3.5rem; font-weight:800; margin-bottom:1rem; position:relative; z-index:1;
    background: linear-gradient(135deg, #FFFFFF 0%, #C7D2FE 50%, #A78BFA 100%); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; }
.landing-hero p { font-size:1.25rem; opacity:0.85; max-width:700px; margin:0 auto 2rem; position:relative; z-index:1; }

.cta-button {
    display:inline-block; padding:0.9rem 2.5rem; border-radius:14px; font-weight:700; font-size:1.05rem;
    text-decoration:none; transition:all 0.3s ease; cursor:pointer; border:none; margin:0.5rem;
}
.cta-primary { background:linear-gradient(135deg, #6366F1, #8B5CF6); color:white; box-shadow:0 8px 30px rgba(99,102,241,0.4); }
.cta-primary:hover { transform:translateY(-3px); box-shadow:0 12px 40px rgba(99,102,241,0.5); }
.cta-secondary { background:rgba(255,255,255,0.1); color:white; border:2px solid rgba(255,255,255,0.3); backdrop-filter:blur(10px); }
.cta-secondary:hover { background:rgba(255,255,255,0.2); }

.feature-card {
    background:var(--card-bg); border-radius:16px; padding:2rem; text-align:center;
    box-shadow:0 4px 20px var(--card-shadow); border:1px solid var(--card-border);
    transition:all 0.3s ease; height:100%;
}
.feature-card:hover { transform:translateY(-6px); box-shadow:0 16px 50px var(--card-hover-shadow); border-color:var(--primary-light); }
.feature-card .feature-icon { font-size:2.5rem; margin-bottom:1rem; display:block;
    width:70px; height:70px; line-height:70px; border-radius:16px; margin:0 auto 1rem;
    background:linear-gradient(135deg, rgba(99,102,241,0.1), rgba(139,92,246,0.1)); }
.feature-card h4 { font-family:'Poppins',sans-serif; color:var(--text-primary); font-weight:700; margin-bottom:0.5rem; }
.feature-card p { color:var(--text-secondary); font-size:0.9rem; line-height:1.6; }

.step-card {
    text-align:center; padding:1.5rem; position:relative;
}
.step-card .step-number {
    width:60px; height:60px; border-radius:50%; line-height:60px; font-size:1.5rem; font-weight:800;
    margin:0 auto 1rem; color:white; font-family:'Poppins',sans-serif;
}
.step-card h5 { font-family:'Poppins',sans-serif; color:var(--text-primary); font-weight:700; margin-bottom:0.3rem; }
.step-card p { color:var(--text-secondary); font-size:0.85rem; }

.pricing-card {
    background:var(--card-bg); border-radius:20px; padding:2.5rem 2rem; text-align:center;
    box-shadow:0 4px 20px var(--card-shadow); border:2px solid var(--card-border);
    transition:all 0.3s ease; position:relative;
}
.pricing-card:hover { transform:translateY(-6px); box-shadow:0 20px 60px var(--card-hover-shadow); }
.pricing-card.recommended { border-color:var(--primary); box-shadow:0 8px 40px rgba(99,102,241,0.2); }
.pricing-card.recommended::before { content:'MOST POPULAR'; position:absolute; top:-12px; left:50%; transform:translateX(-50%);
    background:linear-gradient(135deg, #6366F1, #8B5CF6); color:white; padding:0.3rem 1.2rem; border-radius:50px;
    font-size:0.7rem; font-weight:700; letter-spacing:0.1em; }
.pricing-card .price { font-family:'Poppins',sans-serif; font-size:3rem; font-weight:800; color:var(--primary); }
.pricing-card .price-period { font-size:0.9rem; color:var(--text-muted); }
.pricing-card h3 { font-family:'Poppins',sans-serif; color:var(--text-primary); margin-bottom:0.5rem; }
.pricing-card ul { list-style:none; padding:0; margin:1.5rem 0; text-align:left; }
.pricing-card ul li { padding:0.5rem 0; color:var(--text-secondary); font-size:0.9rem; border-bottom:1px solid var(--card-border); }
.pricing-card ul li::before { content:'\2713'; color:var(--success); font-weight:700; margin-right:0.5rem; }

.testimonial-card {
    background:var(--card-bg); border-radius:16px; padding:2rem; box-shadow:0 4px 20px var(--card-shadow);
    border:1px solid var(--card-border); position:relative;
}
.testimonial-card .quote { font-size:1rem; font-style:italic; color:var(--text-secondary); line-height:1.7; margin-bottom:1.5rem; }
.testimonial-card .author { font-weight:700; color:var(--text-primary); } .testimonial-card .role { color:var(--text-muted); font-size:0.85rem; }
.testimonial-card::before { content:'\201C'; font-size:4rem; color:var(--primary-light); position:absolute; top:10px; left:20px; opacity:0.3; font-family:serif; }

.login-container {
    max-width:450px; margin:3rem auto; background:var(--card-bg); border-radius:24px; padding:3rem;
    box-shadow:0 20px 60px var(--card-shadow); border:1px solid var(--card-border);
}
.login-container h2 { font-family:'Poppins',sans-serif; text-align:center; color:var(--text-primary); margin-bottom:0.5rem; }
.login-container p { text-align:center; color:var(--text-muted); margin-bottom:2rem; }

.theme-toggle { display:inline-flex; align-items:center; gap:0.5rem; cursor:pointer; padding:0.4rem 1rem;
    border-radius:50px; font-size:0.85rem; font-weight:600; transition:all 0.3s ease; }

.analytics-chart-card { background:var(--card-bg); border-radius:16px; padding:1.5rem; box-shadow:0 4px 20px var(--card-shadow);
    border:1px solid var(--card-border); margin-bottom:1.5rem; }
.analytics-chart-card h4 { font-family:'Poppins',sans-serif; color:var(--text-primary); margin-bottom:1rem; }

.trust-section { text-align:center; padding:2rem 0; color:var(--text-muted); }
.trust-section .trust-label { font-size:0.85rem; font-weight:600; text-transform:uppercase; letter-spacing:0.1em; margin-bottom:1rem; }

/* ── Streamlit Overrides ── */
.stButton > button[kind="primary"] {
    background:linear-gradient(135deg, var(--primary), #7C3AED) !important; color:white !important;
    border:none !important; border-radius:12px !important; padding:0.6rem 2rem !important;
    font-weight:700 !important; font-size:1rem !important; transition:all 0.3s ease !important;
    box-shadow:0 4px 15px rgba(79,70,229,0.3) !important;
}
.stButton > button[kind="primary"]:hover { transform:translateY(-2px) !important; box-shadow:0 8px 25px rgba(79,70,229,0.4) !important; }
.stProgress > div > div > div { background:linear-gradient(90deg, var(--primary), #7C3AED) !important; border-radius:10px !important; }
[data-testid="stExpander"] { border:1px solid var(--card-border) !important; border-radius:12px !important; overflow:hidden; }

/* ── Animations ── */
@keyframes fadeIn { from { opacity:0; transform:translateY(10px); } to { opacity:1; transform:translateY(0); } }
@keyframes pulse { 0%,100% { transform:scale(1); } 50% { transform:scale(1.05); } }
@keyframes gradientShift { 0% { background-position:0% 50%; } 50% { background-position:100% 50%; } 100% { background-position:0% 50%; } }
.animate-in { animation: fadeIn 0.6s ease forwards; }
"""

def inject_css():
    """Inject the combined theme + static CSS."""
    theme_css = get_theme_css()
    st.markdown(f"<style>{theme_css}\n{STATIC_CSS}</style>", unsafe_allow_html=True)

inject_css()

# ─────────────────────────────────────────────
# ASSESSMENT LINK HANDLER
# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
# ASSESSMENT LINK HANDLER
# ─────────────────────────────────────────────
_query_assess_token = st.query_params.get("assess", None)
if _query_assess_token:
    # Don't auto-authenticate — show candidate login instead
    if not st.session_state.get("_candidate_authenticated"):
        st.session_state["_assess_token"] = _query_assess_token
        st.session_state.show_landing = False

    # If candidate already authenticated via their credentials, proceed
    if st.session_state.get("_candidate_authenticated"):
        _linked_cid = st.session_state.get("_candidate_cid")
        if _linked_cid and _linked_cid in st.session_state.candidates:
            st.session_state.current_candidate_id = _linked_cid
            st.session_state["_arrived_via_link"] = True
            st.session_state.authenticated = True
            st.session_state.show_landing = False

# ─────────────────────────────────────────────
# HELPER: FOOTER
# ─────────────────────────────────────────────
def render_footer():
    st.markdown("""
    <div class="footer">
        \U0001f680 <strong>TalentEdge AI Recruitment Platform</strong> — Built for fair, explainable & compliant hiring<br>
        <span style="font-size:0.78rem;">Powered by AI Screening \u2022 Automated Emails \u2022 Smart Assessments \u2022 Interview Scheduling</span><br>
        <span style="font-size:0.75rem; margin-top:0.5rem; display:block;">\u00a9 2025 TalentEdge AI. All rights reserved.</span>
    </div>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# AUTHENTICATION SYSTEM
# ─────────────────────────────────────────────
def render_login_page():
    st.markdown("""
    <div style="text-align:center; margin: 2rem 0 1rem;">
        <span style="font-size:3.5rem;">\U0001f680</span>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("""
        <div class="login-container">
            <h2>\U0001f512 Welcome Back</h2>
            <p>Sign in to access the recruitment platform</p>
        </div>
        """, unsafe_allow_html=True)

        login_tab, signup_tab = st.tabs(["\U0001f511 Login", "\U0001f4DD Sign Up"])

        with login_tab:
            login_email = st.text_input("Email", placeholder="you@company.com", key="login_email")
            login_pass = st.text_input("Password", type="password", placeholder="Enter your password", key="login_pass")

            if st.button("\U0001f680 Sign In", type="primary", use_container_width=True, key="login_btn"):
                if login_email and login_pass:
                    ok, result = db_verify_login(login_email, login_pass)
                    if ok:
                        st.session_state.authenticated = True
                        st.session_state.current_user = result
                        st.session_state.show_landing = False
                        st.success(f"\u2705 Welcome, {result['name']}!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"\u274c {result}")
                else:
                    st.warning("Please enter both email and password.")

            user_count = db_get_user_count()
            if user_count == 0:
                st.info("\U0001f449 No accounts yet. Create your first account in the **Sign Up** tab.")

        with signup_tab:
            su_name = st.text_input("Full Name *", placeholder="e.g., John Doe", key="su_name")
            su_email = st.text_input("Email Address *", placeholder="you@company.com", key="su_email")
            su_company = st.text_input("Company / Firm Name *", placeholder="Acme Recruiting Inc.", key="su_company")
            su_phone = st.text_input("Phone (optional)", placeholder="+91 98765 43210", key="su_phone")
            su_pass = st.text_input("Password *", type="password", placeholder="Min 8 chars", key="su_pass")
            su_pass2 = st.text_input("Confirm Password *", type="password", placeholder="Re-enter password", key="su_pass2")

            if su_pass:
                import re as _re
                score = sum([
                    len(su_pass) >= 8,
                    bool(_re.search(r"[A-Z]", su_pass)),
                    bool(_re.search(r"[a-z]", su_pass)),
                    bool(_re.search(r"\d", su_pass)),
                    bool(_re.search(r"[!@#$%^&*(),.?\":{}|<>]", su_pass)),
                ])
                colors = {0: 0.1, 1: 0.2, 2: 0.33, 3: 0.66, 4: 0.85, 5: 1.0}
                labels = {0: "Very Weak", 1: "Weak", 2: "Weak", 3: "Medium", 4: "Strong", 5: "Very Strong"}
                st.progress(colors.get(score, 0.1))
                st.caption(f"Password strength: **{labels.get(score, 'Weak')}**")

            if st.button("\U0001f4DD Create Account", type="primary", use_container_width=True, key="signup_btn"):
                errors = []
                if not su_name or not su_name.strip(): errors.append("Full name is required.")
                if not su_email or "@" not in su_email: errors.append("Valid email is required.")
                if not su_company or not su_company.strip(): errors.append("Company name is required.")
                if not su_pass or len(su_pass) < 8: errors.append("Password must be at least 8 characters.")
                elif su_pass != su_pass2: errors.append("Passwords do not match.")
                if errors:
                    for e in errors:
                        st.error(e)
                else:
                    ok, msg = db_create_user(su_name.strip(), su_email.strip(), su_company.strip(), su_phone.strip() if su_phone else "", su_pass)
                    if ok:
                        st.success(f"\u2705 {msg} You can now sign in.")
                        st.balloons()
                    else:
                        st.error(f"\u274c {msg}")

    render_footer()


# ─────────────────────────────────────────────
# LANDING PAGE
# ─────────────────────────────────────────────
def render_landing_page():
    """Render a stunning marketing landing page."""

    # Hero Section
    st.markdown("""
    <div class="landing-hero animate-in">
        <div style="position:relative; z-index:1;">
            <div style="font-size:0.85rem; font-weight:700; letter-spacing:0.15em; text-transform:uppercase;
                 color:#A5B4FC; margin-bottom:1rem;">AI-POWERED RECRUITMENT AUTOMATION</div>
            <h1>AI Recruitment<br>Screening Agent</h1>
            <p>Automate candidate screening, assessments, and communications with our intelligent
            recruitment agent. Save time, reduce bias, and hire the best talent faster.</p>
            <div style="margin-top:1.5rem;">
                <span style="color:#A7F3D0; font-size:0.85rem; margin-right:2rem;">\u2705 No Credit Card Required</span>
                <span style="color:#A7F3D0; font-size:0.85rem; margin-right:2rem;">\u2705 Secure & Compliant</span>
                <span style="color:#A7F3D0; font-size:0.85rem;">\u2705 Start in 60 Seconds</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # CTA Buttons
    c1, c2, c3 = st.columns([1.5, 1, 1.5])
    with c2:
        if st.button("\U0001f680 Get Started Free", type="primary", use_container_width=True, key="cta_start"):
            st.session_state.show_landing = False
            st.rerun()

    # Trust Section
    st.markdown("""
    <div class="trust-section">
        <div class="trust-label">Trusted by recruitment teams worldwide</div>
        <div style="display:flex; justify-content:center; gap:3rem; flex-wrap:wrap; opacity:0.5; font-size:1.5rem; font-weight:800; color:var(--text-muted);">
            <span>Deloitte.</span><span>Infosys</span><span>accenture</span><span>TCS</span><span>wipro</span><span>Cognizant</span>
        </div>
        <div style="margin-top:1rem; color:var(--warning); font-weight:700;">\u2B50\u2B50\u2B50\u2B50\u2B50 4.9/5 from 500+ users</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)

    # Features Section
    st.markdown('<h2 style="text-align:center; font-family:Poppins,sans-serif; color:var(--text-primary); margin-bottom:2rem;">\u2728 Powerful Features</h2>', unsafe_allow_html=True)

    features = [
        ("\U0001f4e4", "Smart CV Screening", "AI-powered parsing and ranking of resumes against job descriptions with detailed skill matching."),
        ("\U0001f4cb", "Automated Assessments", "Send, track & evaluate role-specific candidate assessments with anti-cheating monitoring."),
        ("\U0001f4e7", "Auto Email Workflows", "Automated emails for invites, results, rejections & interview scheduling via SMTP."),
        ("\U0001f527", "Pipeline Management", "Visualize and manage your hiring pipeline with full audit trail and decision logs."),
        ("\U0001f4ca", "Analytics & Insights", "Data-driven insights with interactive charts to improve hiring decisions."),
        ("\U0001f512", "Secure & Compliant", "Enterprise-grade security with hashed passwords, RBAC, and transparent AI decisions."),
    ]
    cols = st.columns(3)
    for i, (icon, title, desc) in enumerate(features):
        with cols[i % 3]:
            st.markdown(f"""
            <div class="feature-card">
                <span class="feature-icon">{icon}</span>
                <h4>{title}</h4>
                <p>{desc}</p>
            </div><br>
            """, unsafe_allow_html=True)

    st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)

    # How It Works
    st.markdown('<h2 style="text-align:center; font-family:Poppins,sans-serif; color:var(--text-primary); margin-bottom:0.5rem;">How It Works</h2>', unsafe_allow_html=True)
    st.markdown('<p style="text-align:center; color:var(--text-muted); margin-bottom:2rem;">A simple, automated recruitment workflow</p>', unsafe_allow_html=True)

    steps = [
        ("#6366F1", "1", "Upload CV", "Candidates upload their CV through the portal"),
        ("#8B5CF6", "2", "AI Screening", "AI parses and ranks candidates based on your JD"),
        ("#A78BFA", "3", "Send Assessment", "Top candidates receive an assessment invite"),
        ("#C084FC", "4", "Evaluate", "AI evaluates responses and scores candidates"),
        ("#E879F9", "5", "Shortlist", "Best candidates move to the next stage"),
        ("#F472B6", "6", "Hire & Onboard", "Hire the best talent with confidence"),
    ]
    cols = st.columns(6)
    for i, (color, num, title, desc) in enumerate(steps):
        with cols[i]:
            st.markdown(f"""
            <div class="step-card">
                <div class="step-number" style="background:{color};">{num}</div>
                <h5>{title}</h5>
                <p>{desc}</p>
            </div>
            """, unsafe_allow_html=True)

    st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)

    # Pricing
    st.markdown('<h2 style="text-align:center; font-family:Poppins,sans-serif; color:var(--text-primary); margin-bottom:2rem;">\U0001f4b0 Simple Pricing</h2>', unsafe_allow_html=True)

    p1, p2, p3 = st.columns(3)
    with p1:
        st.markdown("""
        <div class="pricing-card">
            <h3>Free</h3>
            <div class="price">$0</div><div class="price-period">forever</div>
            <ul><li>5 candidates/month</li><li>Basic ATS screening</li><li>Email templates</li><li>Pipeline logs</li><li>Community support</li></ul>
        </div>""", unsafe_allow_html=True)
    with p2:
        st.markdown("""
        <div class="pricing-card recommended">
            <h3>Pro</h3>
            <div class="price">$49</div><div class="price-period">/month</div>
            <ul><li>Unlimited candidates</li><li>Advanced ATS + Assessments</li><li>Auto email workflows</li><li>Analytics dashboard</li><li>Interview scheduling</li><li>Priority support</li></ul>
        </div>""", unsafe_allow_html=True)
    with p3:
        st.markdown("""
        <div class="pricing-card">
            <h3>Enterprise</h3>
            <div class="price">Custom</div><div class="price-period">contact us</div>
            <ul><li>Everything in Pro</li><li>SSO & SAML</li><li>Custom integrations</li><li>Dedicated account manager</li><li>SLA guarantee</li><li>On-premise option</li></ul>
        </div>""", unsafe_allow_html=True)

    st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)

    # Testimonials
    st.markdown('<h2 style="text-align:center; font-family:Poppins,sans-serif; color:var(--text-primary); margin-bottom:2rem;">\U0001f4ac What Our Users Say</h2>', unsafe_allow_html=True)

    t1, t2, t3 = st.columns(3)
    testimonials = [
        ("We reduced our screening time by 80%%. The AI scoring is incredibly accurate and fair.", "Priya Sharma", "Head of Talent, TechCorp"),
        ("The automated email workflows saved us countless hours. Candidates love the seamless experience.", "James Chen", "HR Director, DataFlow Inc"),
        ("Finally a recruitment tool that is transparent and explainable. The audit logs are a game changer.", "Sarah Kim", "VP People, StartupXYZ"),
    ]
    for col, (quote, author, role) in zip([t1, t2, t3], testimonials):
        with col:
            st.markdown(f"""
            <div class="testimonial-card">
                <div class="quote">{quote}</div>
                <div class="author">{author}</div>
                <div class="role">{role}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Final CTA
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        if st.button("\U0001f680 Start Hiring Smarter Today", type="primary", use_container_width=True, key="cta_bottom"):
            st.session_state.show_landing = False
            st.rerun()

    render_footer()

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
    db.save_email_log(entry) 
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
            
        try:
            db_save_candidate_for_assessment(candidate_data.get("id",""), candidate_data)
        except Exception:
            pass


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


def generate_strong_password(length=12):
    """Generate a strong random password."""
    chars = string.ascii_letters + string.digits + "!@#$%"
    password = [
        random.choice(string.ascii_uppercase),
        random.choice(string.ascii_lowercase),
        random.choice(string.digits),
        random.choice("!@#$%"),
    ]
    password += [random.choice(chars) for _ in range(length - 4)]
    random.shuffle(password)
    return "".join(password)


def add_log(candidate_id, stage, decision, score, reason, next_action, owner="AI_AGENT"):
    entry = {
        "candidate_id": candidate_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stage": stage, "decision": decision, "score": score,
        "reason": reason, "next_action": next_action, "owner": owner,
    }
    st.session_state.pipeline_logs.append(entry)
    db.save_log(entry)
    return entry


def parse_cv_text(uploaded_file):
    """Extract text from uploaded CV. Uses pdfplumber for PDFs."""
    if uploaded_file is None:
        return ""
    try:
        file_name = uploaded_file.name.lower()
        uploaded_file.seek(0)
        raw = uploaded_file.read()
        uploaded_file.seek(0)
        if not raw:
            return ""
        if file_name.endswith(".pdf"):
            try:
                import pdfplumber
                with pdfplumber.open(BytesIO(raw)) as pdf:
                    parts = [p.extract_text() for p in pdf.pages if p.extract_text()]
                if parts:
                    return "\n".join(parts).strip()
            except Exception:
                pass
            try:
                import PyPDF2
                reader = PyPDF2.PdfReader(BytesIO(raw))
                text = ""
                for page in reader.pages:
                    pt = page.extract_text()
                    if pt:
                        text += pt + "\n"
                if text.strip():
                    return text.strip()
            except Exception:
                pass
            return ""
        elif file_name.endswith(".docx"):
            try:
                import docx
                doc = docx.Document(BytesIO(raw))
                text = "\n".join([p.text for p in doc.paragraphs])
                if text.strip():
                    return text.strip()
            except Exception:
                pass
            try:
                import zipfile
                with zipfile.ZipFile(BytesIO(raw)) as zf:
                    if "word/document.xml" in zf.namelist():
                        xd = zf.read("word/document.xml").decode("utf-8", errors="ignore")
                        ct = re.sub(r"<[^>]+>", " ", xd)
                        ct = re.sub(r'\s+', ' ', ct).strip()
                        if len(ct) > 20:
                            return ct
            except Exception:
                pass
            return ""
        elif file_name.endswith(".txt"):
            return raw.decode("utf-8", errors="ignore").strip()
        else:
            return raw.decode("utf-8", errors="ignore").strip()
    except Exception as e:
        return f"ERROR_PARSING: {str(e)}"



def extract_candidate_email(text):
    """Extract personal email with domain validation."""
    if not text:
        return ""
    pat = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,4}'
    emails = re.findall(pat, text)
    skip = ["noreply","info@","support@","hr@","admin@","contact@","sales@","hello@","team@","careers@","jobs@"]
    ok_tlds = {"com","org","net","edu","io","in","co","uk","us","ca","au","de","fr","ai","dev","tech","me","info","biz"}
    for e in emails:
        el = e.lower()
        if any(el.startswith(s) for s in skip):
            continue
        parts = el.split("@")
        if len(parts) != 2 or len(parts[0]) < 2:
            continue
        dp = parts[1].split(".")
        if len(dp) < 2 or dp[-1] not in ok_tlds:
            continue
        if len(dp[-2]) < 2 or not re.match(r'^[a-z0-9-]+$', dp[-2]):
            continue
        return e
    return ""


def extract_candidate_name(text):
    """Extract candidate name from CV text. Handles PDF quirks."""
    if not text:
        return ""
    tl = [l.strip() for l in text.splitlines() if l.strip()]
    for line in tl[:20]:
        m = re.match(r'(?:full\s*name|name|candidate\s*name)\s*[:\;-]\s*(.+)', line, re.IGNORECASE)
        if m:
            nm = m.group(1).strip().strip('.,;:')
            if 2 <= len(nm.split()) <= 5 and not re.search(r'\d', nm):
                return nm
    skip = [
        r'https?://|www\.',
        r'\d{5,}',
        r'(?i)\b(?:resume|curriculum|vitae|cv|portfolio|objective|summary|profile|experience)\b',
        r'(?i)\b(?:address|street|city|state|country|pin|zip)\b',
        r'(?i)\b(?:phone|tel|mobile|cell|fax)\b',
        r'(?i)\b(?:linkedin|github|twitter|facebook)\b',
        r'(?i)^page\s*\d',
        r'[|/\\]',
    ]
    for line in tl[:15]:
        skip_this = False
        for p in skip:
            if re.search(p, line):
                skip_this = True
                break
        if skip_this:
            continue
        test_line = line
        if '@' in line:
            test_line = re.sub(r'\S+@\S+', '', line).strip()
            test_line = re.sub(r'(?i)\b(?:email|e-mail)\s*[:\;-]?\s*', '', test_line).strip()
        if len(test_line) > 45 or len(test_line) < 3:
            continue
        test_line = re.sub(r'\s+', ' ', test_line).strip()
        words = test_line.split()
        if 2 <= len(words) <= 4:
            if all(w[0].isupper() for w in words if w):
                if all(re.match(r"^[A-Za-z'.\-]+$", w) for w in words):
                    return test_line
    return ""


def auto_detect_cv_info(uploaded_file):
    """Parse CV and auto-detect name + email."""
    if uploaded_file is None:
        return {"cv_text": "", "name": "", "email": "", "file_name": ""}
    file_name = uploaded_file.name
    uploaded_file.seek(0)
    cv_text = parse_cv_text(uploaded_file)
    uploaded_file.seek(0)
    name = extract_candidate_name(cv_text) if cv_text else ""
    email = extract_candidate_email(cv_text) if cv_text else ""
    return {"cv_text": cv_text, "name": name, "email": email, "file_name": file_name}


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
    app_host = st.context.headers.get("Host", "localhost:8501")
    protocol = "https" if "streamlit.app" in app_host else "http"
    link = f"{protocol}://{app_host}/?assess={token}"

    # Generate strong credentials for the candidate
    assess_username = candidate_name.lower().replace(" ", ".") + f".{random.randint(100,999)}"
    assess_password = generate_strong_password()

    # Store credentials in session state if candidate_id is available
    if candidate_id and candidate_id in st.session_state.candidates:
        st.session_state.candidates[candidate_id]["assessment_credentials"] = {
            "username": assess_username,
            "password": assess_password,
        }
    # Also register the username in the users_db so the candidate can log in
    if assess_username not in st.session_state.users_db:
        st.session_state.users_db[assess_username] = {
            "password_hash": hashlib.sha256(assess_password.encode()).hexdigest(),
            "name": candidate_name,
            "role": "candidate",
        }

    # ═══ ADD THIS BLOCK RIGHT HERE ═══
    # if "assessment_credentials" not in st.session_state:
    #     st.session_state["assessment_credentials"] = {}
    # st.session_state["assessment_credentials"][token] = {
    #     "username": assess_username,
    #     "password": assess_password,
    #     "candidate_id": candidate_id,
    #     "candidate_name": candidate_name,
    # }
    # Store credentials in SQLite (persists across all sessions)
    try:
        conn = sqlite3.connect(AUTH_DB)
        conn.execute(
            "INSERT OR REPLACE INTO assessment_credentials (token, username, password, candidate_id, candidate_name) VALUES (?,?,?,?,?)",
            (token, assess_username, assess_password, candidate_id, candidate_name)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB] Error storing assessment credentials: {e}")
    # ═══ END OF NEW BLOCK ═══

    return f"""Subject: Next Step: Assessment for {role}

Dear {candidate_name},

Thank you for your application for the {role} role.

We are pleased to invite you to complete the next stage of the selection process: an online assessment.

Assessment Details:
- Number of questions: 30
- Duration: 20 minutes
- Link: {link}
- Deadline: {deadline}

Your Login Credentials:
━━━━━━━━━━━━━━━━━━━━━━━━━━━
  👤 Username : {assess_username}
  🔑 Password : {assess_password}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

Important Instructions:
- Complete the assessment in one sitting.
- Ensure a stable internet connection.
- The assessment runs in full-screen mode.
- Do not switch tabs or windows during the test.
- Copy-paste and tab-switching will be monitored.
- Any suspicious activity will be flagged for review.
- Do NOT share your credentials with anyone.

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
# ANALYTICS PAGE
# ═════════════════════════════════════════════
def render_analytics_page():
    """Render comprehensive analytics dashboard with Plotly charts."""
    st.markdown("""
    <div class="hero-banner animate-in">
        <h1>\U0001f4ca Analytics & Insights</h1>
        <p>Data-driven recruitment analytics — track performance, identify patterns, and optimize your hiring pipeline</p>
    </div>
    """, unsafe_allow_html=True)

    candidates = st.session_state.candidates
    theme = st.session_state.get("theme", "dark")
    plot_template = "plotly_dark" if theme == "dark" else "plotly_white"
    plot_bg = "rgba(0,0,0,0)" if theme == "dark" else "rgba(0,0,0,0)"
    paper_bg = "#1E293B" if theme == "dark" else "#FFFFFF"
    text_color = "#F1F5F9" if theme == "dark" else "#1E293B"
    grid_color = "#334155" if theme == "dark" else "#E2E8F0"

    if not PLOTLY_AVAILABLE:
        st.warning("⚠️ Install Plotly for interactive charts: `pip install plotly`")
        render_footer()
        return

    if not candidates:
        st.info("No candidates yet. Process some candidates to see analytics.")
        render_footer()
        return

    # Collect data
    all_ats_scores = [c["ats_result"]["ats_score"] for c in candidates.values() if c.get("ats_result")]
    all_roles = [c["role"] for c in candidates.values()]
    passed_ats = sum(1 for c in candidates.values() if (c.get("ats_result") or {}).get("decision") == "PASS")
    total = len(candidates)
    pass_rate = round((passed_ats / total) * 100, 1) if total > 0 else 0
    avg_ats = round(sum(all_ats_scores) / len(all_ats_scores), 1) if all_ats_scores else 0
    assess_scores = [c["assessment_result"]["score_percent"] for c in candidates.values() if c.get("assessment_result")]
    avg_assess = round(sum(assess_scores) / len(assess_scores), 1) if assess_scores else 0
    interviews = sum(1 for c in candidates.values() if c.get("interview_scheduled"))

    # KPI Cards
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="stat-card stat-blue"><div class="stat-value">{total}</div><div class="stat-label">Total Candidates</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="stat-card stat-purple"><div class="stat-value">{avg_ats}</div><div class="stat-label">Avg ATS Score</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="stat-card stat-green"><div class="stat-value">{pass_rate}%</div><div class="stat-label">ATS Pass Rate</div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="stat-card stat-orange"><div class="stat-value">{avg_assess}</div><div class="stat-label">Avg Assessment</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)

    # Row 1: ATS Distribution + Pipeline Funnel
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="analytics-chart-card"><h4>\U0001f4ca ATS Score Distribution</h4>', unsafe_allow_html=True)
        if all_ats_scores:
            colors = ["#10B981" if s > 85 else ("#F59E0B" if s >= 75 else "#EF4444") for s in all_ats_scores]
            fig = go.Figure(go.Bar(x=list(range(1, len(all_ats_scores)+1)), y=all_ats_scores,
                                   marker_color=colors, text=[f"{s}%" for s in all_ats_scores], textposition="outside"))
            fig.add_hline(y=85, line_dash="dash", line_color="#10B981", annotation_text="Pass: 85%")
            fig.add_hline(y=75, line_dash="dash", line_color="#F59E0B", annotation_text="Review: 75%")
            fig.update_layout(template=plot_template, paper_bgcolor=paper_bg, plot_bgcolor=plot_bg,
                              font_color=text_color, height=350, margin=dict(l=40,r=20,t=30,b=40),
                              xaxis_title="Candidate #", yaxis_title="ATS Score",
                              yaxis=dict(gridcolor=grid_color), xaxis=dict(gridcolor=grid_color))
            st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="analytics-chart-card"><h4>\U0001f3af Pipeline Funnel</h4>', unsafe_allow_html=True)
        assess_sent = sum(1 for c in candidates.values() if c and c.get("status") in ["Assessment Sent", "Passed Assessment", "Failed Assessment", "Interview Scheduled"])
        passed_assess = sum(1 for c in candidates.values() if c and (c.get("assessment_result") or {}).get("decision") == "PASS")
        funnel_data = {"Stage": ["Applied", "Passed ATS", "Assessment", "Passed Assessment", "Interview"],
                       "Count": [total, passed_ats, assess_sent, passed_assess, interviews]}
        fig = go.Figure(go.Funnel(y=funnel_data["Stage"], x=funnel_data["Count"],
                                   marker=dict(color=["#6366F1", "#8B5CF6", "#A78BFA", "#C084FC", "#E879F9"]),
                                   textinfo="value+percent initial"))
        fig.update_layout(template=plot_template, paper_bgcolor=paper_bg, font_color=text_color,
                          height=350, margin=dict(l=20,r=20,t=30,b=20))
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # Row 2: Skills Gap + Role Distribution
    col3, col4 = st.columns(2)

    with col3:
        st.markdown('<div class="analytics-chart-card"><h4>\U0001f50d Top Missing Skills</h4>', unsafe_allow_html=True)
        all_missing = []
        for c in candidates.values():
            all_missing.extend((c.get("ats_result") or {}).get("missing_skills", []))
        if all_missing:
            skill_counts = Counter(all_missing).most_common(12)
            skills, counts = zip(*skill_counts)
            fig = go.Figure(go.Bar(y=list(skills), x=list(counts), orientation="h",
                                   marker_color="#EF4444", text=list(counts), textposition="outside"))
            fig.update_layout(template=plot_template, paper_bgcolor=paper_bg, plot_bgcolor=plot_bg,
                              font_color=text_color, height=400, margin=dict(l=120,r=40,t=20,b=40),
                              xaxis_title="Frequency", yaxis=dict(autorange="reversed", gridcolor=grid_color),
                              xaxis=dict(gridcolor=grid_color))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No skills gap data yet.")
        st.markdown('</div>', unsafe_allow_html=True)

    with col4:
        st.markdown('<div class="analytics-chart-card"><h4>\U0001f465 Candidates by Role</h4>', unsafe_allow_html=True)
        if all_roles:
            role_counts = Counter(all_roles)
            fig = go.Figure(go.Pie(labels=list(role_counts.keys()), values=list(role_counts.values()),
                                    hole=0.5, marker=dict(colors=["#6366F1","#8B5CF6","#EC4899","#F59E0B","#10B981"])))
            fig.update_layout(template=plot_template, paper_bgcolor=paper_bg, font_color=text_color,
                              height=400, margin=dict(l=20,r=20,t=20,b=20))
            st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # Row 3: Score Radar + Email Stats
    col5, col6 = st.columns(2)

    with col5:
        st.markdown('<div class="analytics-chart-card"><h4>\U0001f578\ufe0f ATS Score Breakdown (Average)</h4>', unsafe_allow_html=True)
        components = {"Skill": [], "Experience": [], "Education": [], "Certification": [], "Tools": []}
        for c in candidates.values():
            bd = (c.get("ats_result") or {}).get("score_breakdown", {})
            if bd:
                components["Skill"].append(bd.get("skill_score", 0))
                components["Experience"].append(bd.get("experience_score", 0))
                components["Education"].append(bd.get("education_score", 0))
                components["Certification"].append(bd.get("certification_score", 0))
                components["Tools"].append(bd.get("tool_platform_score", 0))
        if any(components.values()):
            avgs = [round(sum(v)/len(v), 1) if v else 0 for v in components.values()]
            maxes = [40, 20, 15, 10, 15]
            pcts = [round((a/m)*100, 1) if m > 0 else 0 for a, m in zip(avgs, maxes)]
            fig = go.Figure(go.Scatterpolar(
                r=pcts + [pcts[0]], theta=list(components.keys()) + [list(components.keys())[0]],
                fill="toself", fillcolor="rgba(99,102,241,0.2)", line_color="#6366F1"
            ))
            fig.update_layout(template=plot_template, paper_bgcolor=paper_bg, font_color=text_color,
                              height=380, margin=dict(l=60,r=60,t=40,b=40),
                              polar=dict(bgcolor=plot_bg, radialaxis=dict(visible=True, range=[0,100], gridcolor=grid_color),
                                         angularaxis=dict(gridcolor=grid_color)))
            st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col6:
        st.markdown('<div class="analytics-chart-card"><h4>\U0001f4e7 Email Automation Stats</h4>', unsafe_allow_html=True)
        # email_log = st.session_state.email_log
        email_log = db.get_email_logs()  # Load from SQLite
        if email_log:
            sent = sum(1 for e in email_log if e["status"] == "SENT")
            failed = sum(1 for e in email_log if e["status"] == "FAILED")
            queued = sum(1 for e in email_log if e["status"] == "QUEUED")
            fig = go.Figure(go.Bar(x=["Sent", "Failed", "Queued"], y=[sent, failed, queued],
                                   marker_color=["#10B981", "#EF4444", "#F59E0B"],
                                   text=[sent, failed, queued], textposition="outside"))
            fig.update_layout(template=plot_template, paper_bgcolor=paper_bg, plot_bgcolor=plot_bg,
                              font_color=text_color, height=380, margin=dict(l=40,r=20,t=30,b=40),
                              yaxis_title="Count", yaxis=dict(gridcolor=grid_color), xaxis=dict(gridcolor=grid_color))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No email data yet.")
        st.markdown('</div>', unsafe_allow_html=True)

    render_footer()


# ═════════════════════════════════════════════
# HELPER: SHOW AUTOMATION RESULTS
# ═════════════════════════════════════════════
def show_automation_results(actions):
    if not actions:
        return
    st.markdown("### \u26a1 Automation Actions")
    for act in actions:
        icon = "\u2705" if act["status"] == "SENT" else ("\U0001f7e1" if act["status"] == "QUEUED" else "\u274c")
        st.markdown(f"{icon} **{act['action']}** \u2192 `{act['to']}` \u2014 **{act['status']}**")
        if act["status"] != "SENT":
            st.caption(f"   {act['detail']}")


# ═════════════════════════════════════════════
#  MAIN APP ROUTER
# ═════════════════════════════════════════════

# Gate 1: Landing page
# Gate 1: Landing page
if st.session_state.show_landing and not st.session_state.authenticated:
    render_landing_page()

# Gate 1.5: Candidate Assessment Login (when arriving via email link)
elif st.session_state.get("_assess_token") and not st.session_state.get("_candidate_authenticated") and not st.session_state.authenticated:
    _token = st.session_state["_assess_token"]
    # _creds = st.session_state.get("assessment_credentials", {}).get(_token)
    # Look up credentials from SQLite (shared across all sessions)
    _creds = None
    try:
        conn = sqlite3.connect(AUTH_DB)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM assessment_credentials WHERE token = ?", (_token,)).fetchone()
        conn.close()
        if row:
            _creds = {
                "username": row["username"],
                "password": row["password"],
                "candidate_id": row["candidate_id"],
                "candidate_name": row["candidate_name"],
            }
    except Exception:
        _creds = None


    st.markdown("""
    <div style="text-align:center; margin: 2rem 0;">
        <span style="font-size:3rem;">📝</span>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("## 📝 Candidate Assessment Login")
        st.markdown("Enter the credentials from your assessment invitation email.")

        c_user = st.text_input("Username", placeholder="Enter username from email", key="cand_login_user")
        c_pass = st.text_input("Password", type="password", placeholder="Enter password from email", key="cand_login_pass")

        # if st.button("🚀 Start Assessment", type="primary", use_container_width=True, key="cand_login_btn"):
        #     if _creds and c_user == _creds["username"] and c_pass == _creds["password"]:
        #         st.session_state["_candidate_authenticated"] = True
        #         st.session_state["_candidate_cid"] = _creds["candidate_id"]
        #         st.session_state.authenticated = True
        #         st.session_state.show_landing = False
        #         st.session_state["_arrived_via_link"] = True
        #         st.session_state.current_candidate_id = _creds["candidate_id"]


        if st.button("🚀 Start Assessment", type="primary", use_container_width=True, key="cand_login_btn"):
            if _creds and c_user == _creds["username"] and c_pass == _creds["password"]:
                st.session_state["_candidate_authenticated"] = True
                st.session_state["_candidate_cid"] = _creds["candidate_id"]
                st.session_state["_candidate_mode"] = True  # ← NEW: candidate-only mode
                st.session_state.authenticated = True
                st.session_state.show_landing = False
                st.session_state["_arrived_via_link"] = True
                st.session_state.current_candidate_id = _creds["candidate_id"]            
                st.success(f"✅ Welcome, {_creds['candidate_name']}! Loading your assessment...")
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Invalid credentials. Please check the username and password from your email.")

        st.markdown("---")
        st.caption("If you're having trouble, please contact the recruitment team.")


# Gate 2: Login
elif not st.session_state.authenticated:
    render_login_page()

# Gate 3: Authenticated - Full App
# else:

else:

    # ═══ CANDIDATE-ONLY ASSESSMENT MODE ═══
    if st.session_state.get("_candidate_mode"):
        # cid = st.session_state.get("_candidate_cid")
        # cand = st.session_state.candidates.get(cid, {}) if cid else {}

        # if not cand:
        #     st.error("❌ Assessment not found. Please contact the recruitment team.")
        #     st.stop()
        cid = st.session_state.get("_candidate_cid")
        cand = st.session_state.candidates.get(cid, {}) if cid else {}

        # If not in session_state, load from SQLite (cross-session support)
        if not cand and cid:
            db_cand = db_get_candidate_assessment(cid)
            if db_cand:
                cand = {
                    "id": cid,
                    "name": db_cand["candidate_name"],
                    "email": db_cand["candidate_email"],
                    "role": db_cand["role"],
                    "ats_result": {"ats_score": db_cand["ats_score"], "decision": db_cand["ats_decision"]},
                    "status": db_cand["status"],
                    "assessment_result": json.loads(db_cand["assessment_data"]) if db_cand["assessment_data"] else None,
                    "emails_sent": [],
                }
                st.session_state.candidates[cid] = cand

        if not cand:
            st.error("❌ Assessment not found. Please contact the recruitment team.")
            st.stop()

        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#4F46E5,#7C3AED); color:white; padding:1.5rem 2rem; border-radius:16px; margin-bottom:2rem;">
            <h2 style="margin:0; color:white;">📝 Assessment: {cand.get('role', 'Role')}</h2>
            <p style="margin:0.5rem 0 0; opacity:0.9;">Candidate: {cand.get('name', '')} | {len(st.session_state.get('assessment_questions', []) or ['?']*30)} Questions | {cand.get('assess_duration', 20)} Minutes</p>
        </div>
        """, unsafe_allow_html=True)

        # Check if already submitted
        if cand.get("assessment_result"):
            st.success("✅ You have submitted your assessment. Thank you!")
            st.info("You may close this page now. The recruitment team will contact you with next steps.")
            st.stop()

        # Assessment instructions
        if not st.session_state.assessment_started:
            st.markdown("""
            **Assessment Instructions:**
            - 30 multiple-choice questions
            - Duration: 20 minutes
            - Pass threshold: > 90%
            - Complete in one sitting
            - Do NOT switch tabs or windows

            By clicking Start, you agree to the assessment policies.
            """)
            if st.button("🚀 Start Assessment", type="primary", use_container_width=True, key="cand_start_assess"):
                # questions = get_assessment_questions(cand["role"], 30)
                
                custom_qs = db.get_custom_assessment(cid)
                if custom_qs and len(custom_qs) >= 5:
                    questions = custom_qs
                    random.shuffle(questions)
                    questions = questions[:30]
                else:
                    questions = get_assessment_questions(cand["role"], 30)
                st.session_state.assessment_questions = questions
                st.session_state.assessment_started = True
                st.session_state.assessment_answers = {}
                st.session_state.assessment_submitted = False
                st.session_state.assessment_start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.rerun()
            st.stop()

        # Show questions
        # questions = st.session_state.get("assessment_questions", [])

        # if not st.session_state.assessment_submitted:
        #     # ═══ ANTI-CHEAT: Timer ═══
        #     import math
        #     start_str = st.session_state.get("assessment_start_time", "")
        #     if start_str:
        #         start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
        #         elapsed = (datetime.now() - start_dt).total_seconds()
        #         remaining = max(0, 20 * 60 - elapsed)
        #         mins_left = int(remaining // 60)
        #         secs_left = int(remaining % 60)

        #         if remaining <= 0:
        #             # TIME UP — auto submit
        #             st.session_state.assessment_submitted = True
        #             result = score_assessment(questions, st.session_state.assessment_answers)
        #             decision = "PASS" if result["score_percent"] > 90 else "FAIL"
        #             result["decision"] = decision
        #             cand["assessment_result"] = result
        #             cand["status"] = "Passed Assessment" if decision == "PASS" else "Failed Assessment"
        #             st.session_state.candidates[cid] = cand
        #             db.save_candidate(cand)
        #             db.save_assessment_result(cid, result, cand["status"])
        #             add_log(cid, "ASSESSMENT", decision, result["score_percent"],
        #                 f"Auto-submitted (time expired). {result['correct']}/{result['total']}",
        #                 "Interview" if decision == "PASS" else "Rejection")
        #             if decision == "PASS":
        #                 auto_pipeline_action(cand, "assessment_pass")
        #                 cand["status"] = "Interview Scheduled"
        #             else:
        #                 auto_pipeline_action(cand, "assessment_fail")
        #             st.session_state.candidates[cid] = cand
        #             db.save_candidate(cand)
        #             st.warning("⏰ Time expired! Your assessment has been auto-submitted.")
        #             st.rerun()

        #         # Timer display
        #         if remaining > 300:
        #             st.info(f"⏱️ Time Remaining: **{mins_left:02d}:{secs_left:02d}** | Questions: {len(questions)}")
        #         elif remaining > 60:
        #             st.warning(f"⚠️ Hurry! Only **{mins_left:02d}:{secs_left:02d}** remaining!")
        #         else:
        #             st.error(f"🔴 LAST MINUTE! **{mins_left:02d}:{secs_left:02d}** — Submit NOW!")

        #         # Auto-refresh every 30 seconds to update timer
        #         import streamlit.components.v1 as components
        #         components.html(f"""<script>setTimeout(function(){{ 
        #             window.parent.document.querySelector('[data-testid="stApp"]').__streamlitWebsocket && 
        #             window.parent.location.reload(); 
        #         }}, 30000);</script>""", height=0)

        #     # ═══ ANTI-CHEAT: Tab switch detection + copy block ═══
        #     if "tab_violations" not in st.session_state:
        #         st.session_state["tab_violations"] = 0

        #     import streamlit.components.v1 as components
        #     components.html("""
        #     <script>
        #     // Block copy/paste/right-click
        #     parent.document.addEventListener('copy', e => e.preventDefault());
        #     parent.document.addEventListener('paste', e => e.preventDefault());
        #     parent.document.addEventListener('contextmenu', e => e.preventDefault());
        #     parent.document.addEventListener('keydown', function(e) {
        #         if (e.ctrlKey && ['c','v','a','u','s','p'].includes(e.key.toLowerCase())) e.preventDefault();
        #         if (e.key === 'F12') e.preventDefault();
        #         if (e.ctrlKey && e.shiftKey && ['i','j'].includes(e.key.toLowerCase())) e.preventDefault();
        #     });
        #     // Text selection disabled
        #     let s = parent.document.createElement('style');
        #     s.textContent = '.stRadio label, .stMarkdown { -webkit-user-select:none!important; user-select:none!important; }';
        #     parent.document.head.appendChild(s);

        #     // Tab switch detection
        #     document.addEventListener('visibilitychange', function() {
        #         if (document.hidden) {
        #             // Send violation to Streamlit via query param trick
        #             let url = new URL(parent.window.location);
        #             let v = parseInt(url.searchParams.get('tv') || '0') + 1;
        #             url.searchParams.set('tv', v);
        #             parent.window.history.replaceState({}, '', url);
        #             parent.window.location.reload();
        #         }
        #     });
        #     </script>
        #     """, height=0)

        #     # Check tab violation from URL param
        #     tv = st.query_params.get("tv", "0")
        #     try:
        #         tv_count = int(tv)
        #     except:
        #         tv_count = 0

        #     if tv_count > st.session_state.get("tab_violations", 0):
        #         st.session_state["tab_violations"] = tv_count

        #         if tv_count == 1:
        #             st.error("⚠️ **WARNING:** You switched tabs/windows! This has been recorded. **Next time your test will be auto-submitted.**")
        #             add_log(cid, "ANTI_CHEAT", "WARNING", tv_count, "Tab switch detected (1st warning)", "Final warning issued")

        #         elif tv_count >= 2:
        #             # FORCE SUBMIT
        #             st.session_state.assessment_submitted = True
        #             result = score_assessment(questions, st.session_state.assessment_answers)
        #             decision = "PASS" if result["score_percent"] > 90 else "FAIL"
        #             result["decision"] = decision
        #             cand["assessment_result"] = result
        #             cand["status"] = "Passed Assessment" if decision == "PASS" else "Failed Assessment"
        #             st.session_state.candidates[cid] = cand
        #             db.save_candidate(cand)
        #             db.save_assessment_result(cid, result, cand["status"])
        #             add_log(cid, "ANTI_CHEAT", "FORCE_SUBMIT", tv_count, f"Force-submitted after {tv_count} tab switches", "Flagged for review")
        #             if decision == "PASS":
        #                 auto_pipeline_action(cand, "assessment_pass")
        #                 cand["status"] = "Interview Scheduled"
        #             else:
        #                 auto_pipeline_action(cand, "assessment_fail")
        #             st.session_state.candidates[cid] = cand
        #             db.save_candidate(cand)
        #             st.error("🚫 Your test has been **force-submitted** due to multiple tab switches.")
        #             st.rerun()

        #     if st.session_state.get("tab_violations", 0) == 1:
        #         st.warning("⚠️ You have **1 tab-switch violation**. One more and your test will be auto-submitted.")

        #     # ═══ Show Questions ═══
        #     for i, q in enumerate(questions):
        #         st.markdown(f"**Q{i+1}.** ({q.get('topic','')}) {q['q']}")
        #         answer = st.radio(f"Answer Q{i+1}:", q["options"], key=f"cand_q_{i}", index=None, label_visibility="collapsed")
        #         if answer is not None:
        #             st.session_state.assessment_answers[str(i)] = q["options"].index(answer)
        #         st.markdown("---")

        #     answered = len(st.session_state.assessment_answers)
        #     st.progress(answered / len(questions))
        #     st.markdown(f"**Answered: {answered}/{len(questions)}**")

        #     if st.button("✅ Submit Assessment", type="primary", use_container_width=True, key="cand_submit_assess"):
               

        #     answered = len(st.session_state.assessment_answers)
        #     st.progress(answered / len(questions))
        #     st.markdown(f"**Answered: {answered}/{len(questions)}**")

        #     if st.button("✅ Submit Assessment", type="primary", use_container_width=True, key="cand_submit_assess"):
        #         st.session_state.assessment_submitted = True
        #         result = score_assessment(questions, st.session_state.assessment_answers)
        #         decision = "PASS" if result["score_percent"] > 90 else "FAIL"
        #         result["decision"] = decision

        #         # Store result in candidate record
        #         cand["assessment_result"] = result
        #         cand["status"] = "Passed Assessment" if decision == "PASS" else "Failed Assessment"
                
                
        #         st.session_state.candidates[cid] = cand
        #         db.save_candidate(cand)                                  # ← saves to db_manager's candidates table
        #         db.save_assessment_result(cid, result, cand["status"])   # ← updates assessment columns

                

        #         # Log it
        #         add_log(cid, "ASSESSMENT", decision, result["score_percent"],
        #             f"Score: {result['correct']}/{result['total']} ({result['score_percent']}%)",
        #             "Move to Interview" if decision == "PASS" else "Send Rejection")

        #         # Auto-trigger email pipeline
        #         if decision == "PASS":
        #             auto_pipeline_action(cand, "assessment_pass")
        #             cand["status"] = "Interview Scheduled"
        #         else:
        #             auto_pipeline_action(cand, "assessment_fail")
        #         st.session_state.candidates[cid] = cand
        #         st.rerun()
        

        # else:
        #     # Show results after submission
        #     result = cand.get("assessment_result", {})
        #     if isinstance(result, str):
        #         try:
        #             result = json.loads(result)
        #         except Exception:
        #             result = {}
        #     if not isinstance(result, dict):


        # Show questions
        questions = st.session_state.get("assessment_questions", [])

        if not st.session_state.assessment_submitted:
            # ═══ ANTI-CHEAT: Timer ═══
            import math
            # ═══ ANTI-CHEAT: Timer (visual JS countdown, no page reload) ═══
            start_str = st.session_state.get("assessment_start_time", "")
            if start_str:
                start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
                elapsed = (datetime.now() - start_dt).total_seconds()
                # remaining = max(0, 20 * 60 - elapsed)
                duration_mins = cand.get("assess_duration", 20)
                remaining = max(0, duration_mins * 60 - elapsed)

                if remaining <= 0:
                    # TIME UP — auto submit
                    st.session_state.assessment_submitted = True
                    result = score_assessment(questions, st.session_state.assessment_answers)
                    decision = "PASS" if result["score_percent"] > 90 else "FAIL"
                    result["decision"] = decision
                    cand["assessment_result"] = result
                    cand["status"] = "Passed Assessment" if decision == "PASS" else "Failed Assessment"
                    st.session_state.candidates[cid] = cand
                    db.save_candidate(cand)
                    db.save_assessment_result(cid, result, cand["status"])
                    add_log(cid, "ASSESSMENT", decision, result["score_percent"],
                        f"Auto-submitted (time expired). {result['correct']}/{result['total']}",
                        "Interview" if decision == "PASS" else "Rejection")
                    if decision == "PASS":
                        auto_pipeline_action(cand, "assessment_pass")
                        cand["status"] = "Interview Scheduled"
                    else:
                        auto_pipeline_action(cand, "assessment_fail")
                    st.session_state.candidates[cid] = cand
                    db.save_candidate(cand)
                    st.warning("⏰ Time expired! Your assessment has been auto-submitted.")
                    st.rerun()

                # Visual JS countdown timer (ticks every second, NO page reload)
                import streamlit.components.v1 as components
                components.html(f"""
                <div id="timer-box" style="
                    position:fixed; top:10px; right:10px; z-index:99999;
                    background:linear-gradient(135deg,#1E293B,#0F172A);
                    color:#F1F5F9; padding:12px 24px; border-radius:14px;
                    font-family:'Courier New',monospace; font-size:1.3rem; font-weight:800;
                    box-shadow:0 6px 25px rgba(0,0,0,0.4); border:2px solid #334155;
                    text-align:center; min-width:220px;">
                    ⏱️ <span id="mm">--</span>:<span id="ss">--</span>
                </div>
                <script>
                    let t = {int(remaining)};
                    const mm = document.getElementById('mm');
                    const ss = document.getElementById('ss');
                    const box = document.getElementById('timer-box');
                    function tick() {{
                        t--;
                        if (t < 0) t = 0;
                        let m = Math.floor(t/60), s = t%60;
                        mm.textContent = String(m).padStart(2,'0');
                        ss.textContent = String(s).padStart(2,'0');
                        if (t <= 60) {{
                            box.style.background = 'linear-gradient(135deg,#991B1B,#7F1D1D)';
                            box.style.borderColor = '#EF4444';
                        }} else if (t <= 300) {{
                            box.style.background = 'linear-gradient(135deg,#92400E,#78350F)';
                            box.style.borderColor = '#F59E0B';
                        }}
                        if (t <= 0) {{
                            box.innerHTML = '⏰ TIME UP — Submitting...';
                            // Click the Submit button automatically
                            try {{
                                let btns = parent.document.querySelectorAll('button');
                                for (let b of btns) {{
                                    if (b.textContent.includes('Submit Assessment')) {{
                                        b.click();
                                        break;
                                    }}
                                }}
                            }} catch(e) {{}}
                        }}
                    }}
                    tick();
                    setInterval(tick, 1000);
                </script>
                """, height=0)
            # start_str = st.session_state.get("assessment_start_time", "")
            # if start_str:
            #     start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
            #     elapsed = (datetime.now() - start_dt).total_seconds()
            #     remaining = max(0, 20 * 60 - elapsed)
            #     mins_left = int(remaining // 60)
            #     secs_left = int(remaining % 60)

            #     if remaining <= 0:
            #         # TIME UP — auto submit
            #         st.session_state.assessment_submitted = True
            #         result = score_assessment(questions, st.session_state.assessment_answers)
            #         decision = "PASS" if result["score_percent"] > 90 else "FAIL"
            #         result["decision"] = decision
            #         cand["assessment_result"] = result
            #         cand["status"] = "Passed Assessment" if decision == "PASS" else "Failed Assessment"
            #         st.session_state.candidates[cid] = cand
            #         db.save_candidate(cand)
            #         db.save_assessment_result(cid, result, cand["status"])
            #         add_log(cid, "ASSESSMENT", decision, result["score_percent"],
            #             f"Auto-submitted (time expired). {result['correct']}/{result['total']}",
            #             "Interview" if decision == "PASS" else "Rejection")
            #         if decision == "PASS":
            #             auto_pipeline_action(cand, "assessment_pass")
            #             cand["status"] = "Interview Scheduled"
            #         else:
            #             auto_pipeline_action(cand, "assessment_fail")
            #         st.session_state.candidates[cid] = cand
            #         db.save_candidate(cand)
            #         st.warning("⏰ Time expired! Your assessment has been auto-submitted.")
            #         st.rerun()

            #     # Timer display
            #     if remaining > 300:
            #         st.info(f"⏱️ Time Remaining: **{mins_left:02d}:{secs_left:02d}** | Questions: {len(questions)}")
            #     elif remaining > 60:
            #         st.warning(f"⚠️ Hurry! Only **{mins_left:02d}:{secs_left:02d}** remaining!")
            #     else:
            #         st.error(f"🔴 LAST MINUTE! **{mins_left:02d}:{secs_left:02d}** — Submit NOW!")

            #     # Auto-refresh every 30 seconds to update timer
            #     import streamlit.components.v1 as components
            #     components.html("""<script>setTimeout(function(){ window.parent.location.reload(); }, 30000);</script>""", height=0)

            # ═══ ANTI-CHEAT: Tab switch detection + copy block ═══
            if "tab_violations" not in st.session_state:
                st.session_state["tab_violations"] = 0

            import streamlit.components.v1 as components
            components.html("""
            <script>
            try {
                parent.document.addEventListener('copy', e => e.preventDefault());
                parent.document.addEventListener('paste', e => e.preventDefault());
                parent.document.addEventListener('contextmenu', e => e.preventDefault());
                parent.document.addEventListener('keydown', function(e) {
                    if (e.ctrlKey && ['c','v','a','u','s','p'].includes(e.key.toLowerCase())) e.preventDefault();
                    if (e.key === 'F12') e.preventDefault();
                    if (e.ctrlKey && e.shiftKey && ['i','j'].includes(e.key.toLowerCase())) e.preventDefault();
                });
                let s = parent.document.createElement('style');
                s.textContent = '.stRadio label, .stMarkdown { -webkit-user-select:none!important; user-select:none!important; }';
                parent.document.head.appendChild(s);
            } catch(err) {}
            document.addEventListener('visibilitychange', function() {
                if (document.hidden) {
                    let url = new URL(parent.window.location);
                    let v = parseInt(url.searchParams.get('tv') || '0') + 1;
                    url.searchParams.set('tv', v);
                    parent.window.history.replaceState({}, '', url);
                    parent.window.location.reload();
                }
            });
            </script>
            """, height=0)

            # Check tab violation from URL param
            tv = st.query_params.get("tv", "0")
            try:
                tv_count = int(tv)
            except:
                tv_count = 0

            if tv_count > st.session_state.get("tab_violations", 0):
                st.session_state["tab_violations"] = tv_count

                if tv_count == 1:
                    st.error("⚠️ **WARNING:** You switched tabs/windows! This has been recorded. **Next time your test will be auto-submitted.**")
                    add_log(cid, "ANTI_CHEAT", "WARNING", tv_count, "Tab switch detected (1st warning)", "Final warning issued")

                elif tv_count >= 2:
                    # FORCE SUBMIT
                    st.session_state.assessment_submitted = True
                    result = score_assessment(questions, st.session_state.assessment_answers)
                    decision = "PASS" if result["score_percent"] > 90 else "FAIL"
                    result["decision"] = decision
                    cand["assessment_result"] = result
                    cand["status"] = "Passed Assessment" if decision == "PASS" else "Failed Assessment"
                    st.session_state.candidates[cid] = cand
                    db.save_candidate(cand)
                    db.save_assessment_result(cid, result, cand["status"])
                    add_log(cid, "ANTI_CHEAT", "FORCE_SUBMIT", tv_count, f"Force-submitted after {tv_count} tab switches", "Flagged for review")
                    if decision == "PASS":
                        auto_pipeline_action(cand, "assessment_pass")
                        cand["status"] = "Interview Scheduled"
                    else:
                        auto_pipeline_action(cand, "assessment_fail")
                    st.session_state.candidates[cid] = cand
                    db.save_candidate(cand)
                    st.error("🚫 Your test has been **force-submitted** due to multiple tab switches.")
                    st.rerun()

            if st.session_state.get("tab_violations", 0) == 1:
                st.warning("⚠️ You have **1 tab-switch violation**. One more and your test will be auto-submitted.")

            # ═══ Show Questions ═══
            for i, q in enumerate(questions):
                st.markdown(f"**Q{i+1}.** ({q.get('topic','')}) {q['q']}")
                answer = st.radio(f"Answer Q{i+1}:", q["options"], key=f"cand_q_{i}", index=None, label_visibility="collapsed")
                if answer is not None:
                    st.session_state.assessment_answers[str(i)] = q["options"].index(answer)
                st.markdown("---")

            answered = len(st.session_state.assessment_answers)
            st.progress(answered / len(questions))
            st.markdown(f"**Answered: {answered}/{len(questions)}**")

            if st.button("✅ Submit Assessment", type="primary", use_container_width=True, key="cand_submit_assess"):
                st.session_state.assessment_submitted = True
                result = score_assessment(questions, st.session_state.assessment_answers)
                decision = "PASS" if result["score_percent"] > 90 else "FAIL"
                result["decision"] = decision
                cand["assessment_result"] = result
                cand["status"] = "Passed Assessment" if decision == "PASS" else "Failed Assessment"
                st.session_state.candidates[cid] = cand
                db.save_candidate(cand)
                db.save_assessment_result(cid, result, cand["status"])
                add_log(cid, "ASSESSMENT", decision, result["score_percent"],
                    f"Score: {result['correct']}/{result['total']} ({result['score_percent']}%)",
                    "Move to Interview" if decision == "PASS" else "Send Rejection")
                if decision == "PASS":
                    auto_pipeline_action(cand, "assessment_pass")
                    cand["status"] = "Interview Scheduled"
                else:
                    auto_pipeline_action(cand, "assessment_fail")
                st.session_state.candidates[cid] = cand
                db.save_candidate(cand)
                st.rerun()

        else:
            # Show results after submission
            result = cand.get("assessment_result", {})
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except Exception:
                    result = {}
            if not isinstance(result, dict):
                result = {}
            decision = result.get("decision", "FAIL")
            score = result.get("score_percent", 0)

            if decision == "PASS":
                st.success(f"🎉 Congratulations! You scored **{score}%** — You PASSED!")
                st.info("The recruitment team will contact you shortly to schedule your interview.")
            else:
                st.info("Thank you for your time. The recruitment team will be in touch.")

            st.markdown("---")
            st.caption("You may close this page now.")

        st.stop()
    # ═══ END CANDIDATE MODE ═══
    #         result = {}
    #         decision = result.get("decision", "FAIL")
    #         score = result.get("score_percent", 0)

    #         if decision == "PASS":
    #             st.success(f"🎉 Congratulations! You scored **{score}%** — You PASSED!")
    #             st.info("The recruitment team will contact you shortly to schedule your interview.")
    #         else:
    #             # st.error(f"Your score: **{score}%** (required: >90%). Unfortunately you did not pass.")
    #             st.info("Thank you for your time. The recruitment team will be in touch.")

    #         st.markdown("---")
    #         st.caption("You may close this page now.")

    #     st.stop()  # ← CRITICAL: prevents the rest of the recruiter app from loading
    # # ═══ END CANDIDATE MODE ═══

    # ── SIDEBAR ──
    st.sidebar.markdown("""
    <div style="text-align:center; padding: 1rem 0;">
        <span style="font-size:2.5rem;">\U0001f680</span><br>
        <span style="font-family:'Poppins',sans-serif; font-size:1.3rem; font-weight:800; color:#F1F5F9 !important;">TalentEdge AI</span><br>
        <span style="font-size:0.8rem; color:#94A3B8 !important;">Recruitment Platform</span>
    </div>
    """, unsafe_allow_html=True)

    # Theme Toggle
    st.sidebar.markdown("---")
    theme_label = "\U0001f31e Light Mode" if st.session_state.theme == "dark" else "\U0001f319 Dark Mode"
    if st.sidebar.button(theme_label, use_container_width=True, key="theme_toggle"):
        st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"
        st.rerun()

    # User Info
    user = st.session_state.get("current_user")
    if user:
        st.sidebar.markdown(f"""
        <div style="background:rgba(99,102,241,0.15); border-radius:12px; padding:0.8rem 1rem; margin:0.5rem 0;">
            <div style="font-weight:700; color:#F1F5F9 !important;">\U0001f464 {user['name']}</div>
            <div style="font-size:0.75rem; color:#94A3B8 !important;">{user['role'].title()} \u2022 {user.get('company', '')} \u2022 {user['role'].title()}</div>
        </div>
        """, unsafe_allow_html=True)
    if st.sidebar.button("\U0001f6aa Logout", use_container_width=True, key="logout_btn"):
        st.session_state.authenticated = False
        st.session_state.current_user = None
        st.session_state.show_landing = True
        st.rerun()

    st.sidebar.markdown("---")

    _default_page_idx = 0
    if st.session_state.get("_arrived_via_link"):
        _default_page_idx = 1

    page = st.sidebar.radio(
        "Navigation",
        ["\U0001f4c4 CV Upload & ATS", "\U0001f4dd Assessment", "\U0001f4ca Results & Interview",
         "\U0001f4cb Pipeline Logs", "\U0001f4e7 Email Log", "\U0001f464 Candidate Dashboard", "\U0001f4ca Analytics"],
        index=_default_page_idx,
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### \U0001f4e7 Email Automation")
    st.session_state.auto_email_enabled = st.sidebar.checkbox(
        "Enable Auto Email Sending", value=st.session_state.auto_email_enabled,
        help="When enabled, emails are sent automatically at each pipeline stage."
    )

    with st.sidebar.expander("\u2699\ufe0f SMTP Configuration"):
        st.session_state.smtp_server = st.text_input("SMTP Server", value=st.session_state.smtp_server, key="sb_smtp_server")
        st.session_state.smtp_port = st.number_input("SMTP Port", value=st.session_state.smtp_port, min_value=1, max_value=65535, key="sb_smtp_port")
        st.session_state.sender_email = st.text_input("Sender Email", value=st.session_state.sender_email, key="sb_sender_email")
        st.session_state.sender_password = st.text_input("Sender Password", value=st.session_state.sender_password, type="password", key="sb_sender_pwd")
        # if st.session_state.sender_email and st.session_state.sender_password:
        #     st.session_state.smtp_configured = True
        if st.session_state.sender_email and st.session_state.sender_password:
            st.session_state.smtp_configured = True
            db.save_setting("smtp_email", st.session_state.sender_email)
            db.save_setting("smtp_password", st.session_state.sender_password)
            db.save_setting("smtp_server", st.session_state.smtp_server)
            db.save_setting("smtp_port", str(st.session_state.smtp_port))
        else:
            st.session_state.smtp_configured = False
        if st.button("\U0001f50c Test SMTP"):
            if not st.session_state.smtp_configured:
                st.error("Fill in email and password first.")
            else:
                try:
                    with smtplib.SMTP(st.session_state.smtp_server, st.session_state.smtp_port, timeout=10) as server:
                        server.ehlo(); server.starttls(); server.ehlo()
                        server.login(st.session_state.sender_email, st.session_state.sender_password)
                    st.success("\u2705 Connection successful!")
                except Exception as e:
                    st.error(f"\u274c Failed: {str(e)}")

    st.sidebar.markdown("---")
    st.sidebar.markdown("### \u2699\ufe0f Recruiter Settings")
    st.session_state.recruiter_name = st.sidebar.text_input("Team Name", value=st.session_state.recruiter_name)
    st.session_state.recruiter_email = st.sidebar.text_input("Recruiter Email", value=st.session_state.recruiter_email)

    if st.session_state.current_candidate_id and st.session_state.current_candidate_id in st.session_state.candidates:
        cand_sb = st.session_state.candidates[st.session_state.current_candidate_id]
        st.sidebar.markdown("---")
        st.sidebar.markdown("### \U0001f464 Active Candidate")
        st.sidebar.markdown(f"**{cand_sb.get('name','N/A')}** — {cand_sb.get('role','N/A')}")
        st.sidebar.markdown(f"Status: **{cand_sb.get('status','Pending')}**")

    st.sidebar.markdown("---")
    if st.sidebar.button("\U0001f5d1\ufe0f Reset All Data", use_container_width=True):
        keep_keys = ["authenticated", "current_user", "users_db", "theme", "show_landing"]
        keep_vals = {k: st.session_state[k] for k in keep_keys if k in st.session_state}
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        for k, v in keep_vals.items():
            st.session_state[k] = v
        st.rerun()


    # ═════════════════════════════════════════════
    # PAGE 1: CV UPLOAD & ATS
    # ═════════════════════════════════════════════
    if page == "📄 CV Upload & ATS":
        st.markdown("""
        <div class="hero-banner animate-in">
            <h1>📄 CV Upload & ATS Screening</h1>
            <p>Upload candidate CVs, analyze against the job description, and let AI handle the rest.</p>
        </div>
        """, unsafe_allow_html=True)

        upload_mode = st.radio("Upload Mode", ["📄 Single CV", "📥 Batch Upload (Multiple CVs)"], horizontal=True, key="upload_mode_radio")

        if upload_mode == "📄 Single CV":
            col_left, col_right = st.columns([1, 1], gap="large")
            with col_left:
                st.markdown('<div class="section-card"><h3>👤 Candidate Information</h3>', unsafe_allow_html=True)
                c_id = st.text_input("Candidate ID", value=f"CAND-{datetime.now().strftime('%Y%m%d%H%M%S')}")
                st.markdown("#### 📎 Upload CV")
                uploaded_cv = st.file_uploader("Upload CV (PDF, TXT, DOCX)", type=["pdf", "txt", "docx"], key="single_cv_uploader")
                if uploaded_cv is not None:
                    if st.session_state.get("_last_file") != uploaded_cv.name:
                        with st.spinner("🔍 Auto-detecting candidate info from CV..."):
                            info = auto_detect_cv_info(uploaded_cv)
                            st.session_state["_auto_name"] = info["name"]
                            st.session_state["_auto_email"] = info["email"]
                            st.session_state["_auto_cv_text"] = info["cv_text"]
                            st.session_state["_last_file"] = uploaded_cv.name
                            if info["name"]:
                                st.session_state["single_c_name"] = info["name"]
                            if info["email"]:
                                st.session_state["single_c_email"] = info["email"]
                            st.rerun()
                    detected_name = st.session_state.get("_auto_name", "")
                    detected_email = st.session_state.get("_auto_email", "")
                    cv_text_parsed = st.session_state.get("_auto_cv_text", "")
                    if detected_name or detected_email:
                        parts = []
                        if detected_name: parts.append(f"**Name:** {detected_name}")
                        if detected_email: parts.append(f"**Email:** {detected_email}")
                        st.info(f"🤖 Auto-detected from CV: {' · '.join(parts)}")
                else:
                    cv_text_parsed = ""
                c_name = st.text_input("Candidate Name", placeholder="e.g., John Doe", key="single_c_name")
                c_email = st.text_input("Candidate Email", placeholder="e.g., john@email.com", key="single_c_email")
                role_options = list(JD_TEMPLATES.keys()) + ["Custom Role"]
                role_applied = st.selectbox("Role Applied For", role_options, key="single_role")
                if role_applied == "Custom Role":
                    role_applied = st.text_input("Enter Custom Role Title", key="single_custom_role")
                cv_text_manual = st.text_area("Or paste CV text here", height=150, key="single_cv_manual")
                st.markdown('</div>', unsafe_allow_html=True)
            with col_right:
                st.markdown('<div class="section-card"><h3>📋 Job Description</h3>', unsafe_allow_html=True)
                if role_applied in JD_TEMPLATES:
                    jd_text = st.text_area("Job Description", value=JD_TEMPLATES[role_applied], height=400, key="single_jd")
                else:
                    jd_text = st.text_area("Enter Job Description", height=400, key="single_jd_custom")
                with st.expander("ℹ️ Scoring Methodology"):
                    st.markdown("""| Component | Weight |\n|---|---|\n| Skill Match | 40% |\n| Experience | 20% |\n| Education | 15% |\n| Certifications | 10% |\n| Tools / Platforms | 15% |\n\n**Pass: > 85%** · Borderline (75–85%) = human review""")
                st.markdown('</div>', unsafe_allow_html=True)            
            # Custom Assessment (Optional)
            with st.expander("📋 Custom Assessment (Optional)", expanded=False):
                st.markdown("Upload your own assessment or use the built-in role-specific questions.")
                assess_mode = st.radio(
                    "Assessment Type",
                    ["🤖 Built-in (Auto-generated)", "📤 Upload JSON", "📊 Upload CSV", "✍️ Add Manually"],
                    horizontal=True, key="assess_mode_radio"
                )
                custom_questions = None

                if assess_mode == "📤 Upload JSON":
                    st.markdown("**Format:** List of objects with `q`, `options` (4 items), `answer` (0-3 index), `topic`, `difficulty`")
                    st.code('[{"q": "Question?", "options": ["A","B","C","D"], "answer": 0, "topic": "SQL", "difficulty": "easy"}]', language="json")
                    json_file = st.file_uploader("Upload JSON", type=["json"], key="assess_json")
                    if json_file:
                        try:
                            parsed = json.loads(json_file.read().decode("utf-8"))
                            if isinstance(parsed, list) and len(parsed) > 0:
                                valid = all("q" in q and "options" in q and "answer" in q for q in parsed)
                                if valid:
                                    custom_questions = parsed
                                    st.success(f"✅ Loaded {len(parsed)} questions")
                                    for i, q in enumerate(parsed[:3]):
                                        st.markdown(f"**Q{i+1}.** {q['q']} *(Answer: {['A','B','C','D'][q['answer']]})*")
                                    if len(parsed) > 3:
                                        st.caption(f"...and {len(parsed)-3} more")
                                else:
                                    st.error("❌ Each question needs: q, options, answer")
                        except:
                            st.error("❌ Invalid JSON file")

                elif assess_mode == "📊 Upload CSV":
                    st.markdown("**Columns:** question, option_a, option_b, option_c, option_d, correct_answer (A/B/C/D), topic, difficulty")
                    csv_file = st.file_uploader("Upload CSV", type=["csv"], key="assess_csv")
                    if csv_file:
                        try:
                            df = pd.read_csv(csv_file)
                            required = ["question", "option_a", "option_b", "option_c", "option_d", "correct_answer"]
                            if all(c in df.columns for c in required):
                                amap = {"A": 0, "B": 1, "C": 2, "D": 3}
                                parsed = []
                                for _, r in df.iterrows():
                                    parsed.append({
                                        "q": str(r["question"]),
                                        "options": [str(r["option_a"]), str(r["option_b"]), str(r["option_c"]), str(r["option_d"])],
                                        "answer": amap.get(str(r["correct_answer"]).strip().upper(), 0),
                                        "topic": str(r.get("topic", "General")),
                                        "difficulty": str(r.get("difficulty", "medium")),
                                    })
                                custom_questions = parsed
                                st.success(f"✅ Loaded {len(parsed)} questions from CSV")
                                st.dataframe(df.head(3), use_container_width=True, hide_index=True)
                            else:
                                missing = [c for c in required if c not in df.columns]
                                st.error(f"❌ Missing columns: {', '.join(missing)}")
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")

                elif assess_mode == "✍️ Add Manually":
                    if "manual_questions" not in st.session_state:
                        st.session_state["manual_questions"] = []
                    with st.form("add_q_form", clear_on_submit=True):
                        mq = st.text_input("Question *")
                        mc1, mc2 = st.columns(2)
                        with mc1:
                            oa = st.text_input("Option A *")
                            ob = st.text_input("Option B *")
                        with mc2:
                            oc = st.text_input("Option C *")
                            od = st.text_input("Option D *")
                        mc3, mc4 = st.columns(2)
                        with mc3:
                            correct = st.selectbox("Correct Answer", ["A", "B", "C", "D"])
                        with mc4:
                            topic = st.text_input("Topic (optional)", value="General")
                        if st.form_submit_button("➕ Add Question", type="primary"):
                            if mq and oa and ob and oc and od:
                                st.session_state["manual_questions"].append({
                                    "q": mq, "options": [oa, ob, oc, od],
                                    "answer": {"A":0,"B":1,"C":2,"D":3}[correct],
                                    "topic": topic or "General", "difficulty": "medium"
                                })
                            else:
                                st.warning("Fill all required fields")
                    if st.session_state.get("manual_questions"):
                        mqs = st.session_state["manual_questions"]
                        st.success(f"✅ {len(mqs)} question(s) added")
                        for i, q in enumerate(mqs):
                            st.markdown(f"**Q{i+1}.** {q['q']} *(Answer: {['A','B','C','D'][q['answer']]})*")
                        custom_questions = mqs
                        if st.button("🗑️ Clear All", key="clear_manual"):
                            st.session_state["manual_questions"] = []
                            st.rerun()

                # if custom_questions:
                #     st.session_state["_custom_assessment"] = custom_questions
                #     st.info(f"📋 **{len(custom_questions)} custom questions** will be used for this candidate.")
                # else:
                #     st.session_state["_custom_assessment"] = None  
                # Assessment duration setting
                st.markdown("---")
                assess_duration = st.number_input("⏱️ Assessment Duration (minutes)", min_value=5, max_value=120, value=20, step=5, key="assess_duration_input")
                st.session_state["_assess_duration"] = assess_duration

                if custom_questions:
                    st.session_state["_custom_assessment"] = custom_questions
                    st.info(f"📋 **{len(custom_questions)} custom questions** | **{assess_duration} minutes** will be used for this candidate.")
                else:
                    st.session_state["_custom_assessment"] = None              
            st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)
            if st.button("🔍 Analyze CV & Generate ATS Score", type="primary", use_container_width=True, key="single_analyze_btn"):
                if not c_name: st.error("❌ Please enter the candidate's name.")
                elif not c_email: st.error("❌ Please enter the candidate's email.")
                elif not jd_text.strip(): st.error("❌ Please provide a job description.")
                else:
                    cv_text = cv_text_parsed if cv_text_parsed else ""
                    if not cv_text and uploaded_cv:
                        with st.spinner("Parsing CV..."): cv_text = parse_cv_text(uploaded_cv)
                    if not cv_text and cv_text_manual.strip(): cv_text = cv_text_manual.strip()
                    if not cv_text: st.error("❌ No CV content found.")
                    else:
                        with st.spinner("🔄 Analyzing CV..."):
                            result = calculate_ats_score(cv_text, jd_text, role_applied)
                        # candidate_data = {
                        #     "id": c_id, "name": c_name, "email": c_email, "role": role_applied,
                        #     "cv_text": cv_text[:500] + "..." if len(cv_text) > 500 else cv_text,
                        #     "ats_result": result,
                        #     "status": "Passed ATS" if result["decision"] == "PASS" else ("Manual Review" if result["requires_human_review"] else "Failed ATS"),
                        #     "assessment_result": None, "interview_scheduled": False, "emails_sent": [],
                        #     "interview_slots": [], "interview_panel": [],
                        #     "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        # }
                        candidate_data = {
                            "id": c_id, "name": c_name, "email": c_email, "role": role_applied,
                            "cv_text": cv_text[:500] + "..." if len(cv_text) > 500 else cv_text,
                            "ats_result": result,
                            "status": "Passed ATS" if result["decision"] == "PASS" else ("Manual Review" if result["requires_human_review"] else "Failed ATS"),
                            "assessment_result": None, "interview_scheduled": False, "emails_sent": [],
                            "interview_slots": [], "interview_panel": [],
                            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "assess_duration": st.session_state.get("_assess_duration", 20),
                        }
                        st.session_state.candidates[c_id] = candidate_data
                        db.save_candidate(candidate_data)
                        st.session_state.current_candidate_id = c_id
                        score = result["ats_score"]; dec = result["decision"]
                        circ_class = "pass" if dec == "PASS" else ("review" if result["requires_human_review"] else "fail")
                        circ_color = "#065F46" if dec == "PASS" else ("#92400E" if result["requires_human_review"] else "#991B1B")
                        st.markdown(f'<div style="text-align:center; margin:2rem 0;"><div class="score-circle {circ_class}" style="margin:0 auto;"><div class="score-value" style="color:{circ_color}">{score}</div><div class="score-label" style="color:{circ_color}">ATS Score</div></div></div>', unsafe_allow_html=True)
                        if dec == "PASS":
                            st.markdown(f'<div class="result-banner pass-banner">🎉 {c_name} PASSED — Score: {score}%</div>', unsafe_allow_html=True)
                        elif result["requires_human_review"]:
                            st.markdown(f'<div class="result-banner review-banner">⚠️ {c_name} scored {score}% — Flagged for Review</div>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'<div class="result-banner fail-banner">❌ {c_name} did NOT pass — Score: {score}%</div>', unsafe_allow_html=True)
                        breakdown = result.get("score_breakdown", {})
                        labels = {"skill_score": ("Skill Match", 40, "stat-blue"), "experience_score": ("Experience", 20, "stat-green"),
                                  "education_score": ("Education", 15, "stat-purple"), "certification_score": ("Certifications", 10, "stat-orange"),
                                  "tool_platform_score": ("Tools", 15, "stat-red")}
                        cols = st.columns(5)
                        for idx, (comp, val) in enumerate(breakdown.items()):
                            lbl, mx, cls = labels.get(comp, (comp, 20, "stat-blue"))
                            with cols[idx]:
                                st.markdown(f'<div class="stat-card {cls}"><div class="stat-value">{val}</div><div class="stat-label">{lbl} (/{mx})</div></div>', unsafe_allow_html=True)
                        sk1, sk2 = st.columns(2)
                        with sk1:
                            st.markdown("#### ✅ Matched Skills")
                            if result["matched_skills"]:
                                st.markdown(" ".join([f'<span class="skill-tag skill-matched">{s}</span>' for s in result["matched_skills"]]), unsafe_allow_html=True)
                            else: st.info("No matched skills.")
                        with sk2:
                            st.markdown("#### ❌ Missing Skills")
                            if result["missing_skills"]:
                                st.markdown(" ".join([f'<span class="skill-tag skill-missing">{s}</span>' for s in result["missing_skills"]]), unsafe_allow_html=True)
                            else: st.success("No gaps!")
                        with st.expander("🔧 Full ATS JSON"):
                            st.json({"candidate_id": c_id, "ats_score": result["ats_score"], "decision": result["decision"],
                                     "matched_skills": result["matched_skills"], "missing_skills": result["missing_skills"]})
                        st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)
                        # if dec == "PASS":
                        #     add_log(c_id, "ATS_SCREENING", "PASS", result["ats_score"], result["reasoning_summary"], "Send Assessment (Auto)")
                        #     with st.spinner("⚡ Sending assessment invitation..."):
                        #         actions = auto_pipeline_action(candidate_data, "ats_pass")
                        #     candidate_data["status"] = "Assessment Sent"
                        #     st.session_state.candidates[c_id] = candidate_data
                        #     db.save_candidate(candidate_data)
                        #     show_automation_results(actions)
                        #     st.info("👉 Navigate to **📝 Assessment** page to proceed.")
                        if dec == "PASS":
                            add_log(c_id, "ATS_SCREENING", "PASS", result["ats_score"], result["reasoning_summary"], "Send Assessment (Auto)")
                            if st.session_state.get("_custom_assessment"):
                                db.save_custom_assessment(c_id, role_applied, json.dumps(st.session_state["_custom_assessment"]))
                            with st.spinner("⚡ Sending assessment invitation..."):
                                actions = auto_pipeline_action(candidate_data, "ats_pass")
                            candidate_data["status"] = "Assessment Sent"
                            st.session_state.candidates[c_id] = candidate_data
                            db.save_candidate(candidate_data)
                            show_automation_results(actions)
                            st.info("👉 Navigate to **📝 Assessment** page to proceed.")
                        elif result["requires_human_review"]:
                            add_log(c_id, "ATS_SCREENING", "REVIEW", result["ats_score"], "Borderline score", "Awaiting Recruiter Decision")
                            st.markdown("---")
                            st.markdown("### 🧑‍💼 Recruiter Decision Required")
                            st.markdown(f"**{c_name}** scored **{result['ats_score']}%** (threshold: 85%). Review the skills match above and decide:")
                            rev_c1, rev_c2 = st.columns(2)
                            with rev_c1:
                                if st.button("✅ Approve — Send Assessment", type="primary", use_container_width=True, key=f"approve_{c_id}"):
                                    candidate_data["status"] = "Assessment Sent"
                                    candidate_data["ats_result"]["decision"] = "PASS"
                                    add_log(c_id, "RECRUITER_OVERRIDE", "PASS", result["ats_score"], "Manually approved by recruiter", "Send Assessment")
                                    with st.spinner("⚡ Sending assessment invitation..."):
                                        actions = auto_pipeline_action(candidate_data, "ats_pass")
                                    st.session_state.candidates[c_id] = candidate_data
                                    db.save_candidate(candidate_data)
                                    show_automation_results(actions)
                                    st.success("✅ Candidate approved! Assessment invitation sent.")
                            with rev_c2:
                                if st.button("❌ Reject — Send Rejection", use_container_width=True, key=f"reject_{c_id}"):
                                    candidate_data["status"] = "Failed ATS"
                                    candidate_data["ats_result"]["decision"] = "FAIL"
                                    add_log(c_id, "RECRUITER_OVERRIDE", "FAIL", result["ats_score"], "Manually rejected by recruiter", "Send Rejection")
                                    with st.spinner("⚡ Sending rejection..."):
                                        actions = auto_pipeline_action(candidate_data, "ats_fail")
                                    st.session_state.candidates[c_id] = candidate_data
                                    db.save_candidate(candidate_data)
                                    show_automation_results(actions)
                                    st.error("❌ Candidate rejected. Rejection email sent.")
                        else:
                            add_log(c_id, "ATS_SCREENING", "FAIL", result["ats_score"], result["reasoning_summary"], "Send Rejection (Auto)")
                            with st.spinner("⚡ Sending rejection..."):
                                actions = auto_pipeline_action(candidate_data, "ats_fail")
                            st.session_state.candidates[c_id] = candidate_data
                            db.save_candidate(candidate_data)
                            show_automation_results(actions)

        # ────── BATCH UPLOAD MODE ──────
        else:
            st.markdown("""
            <div class="section-card">
            <h3>📥 Batch CV Upload & Processing</h3>
            <p>Upload multiple CVs at once. The system will <strong>auto-detect names & emails</strong>, run ATS scoring, and <strong>send all emails automatically</strong>.</p>
            </div>
            """, unsafe_allow_html=True)
            batch_col1, batch_col2 = st.columns([1.2, 0.8], gap="large")
            with batch_col1:
                st.markdown("#### 📎 Upload Multiple CVs")
                batch_files = st.file_uploader("Upload CVs (PDF, TXT, DOCX) — select multiple files", type=["pdf", "txt", "docx"], accept_multiple_files=True, key="batch_cv_uploader")
                role_options = list(JD_TEMPLATES.keys()) + ["Custom Role"]
                batch_role = st.selectbox("Role Applied For (all candidates)", role_options, key="batch_role")
                if batch_role == "Custom Role":
                    batch_role = st.text_input("Enter Custom Role Title", key="batch_custom_role")
                if batch_role in JD_TEMPLATES:
                    batch_jd = st.text_area("Job Description", value=JD_TEMPLATES[batch_role], height=300, key="batch_jd")
                else:
                    batch_jd = st.text_area("Enter Job Description", height=300, key="batch_jd_custom")
            with batch_col2:
                st.markdown("#### ℹ️ Batch Processing Info")
                if batch_files:
                    st.metric("CVs Uploaded", len(batch_files))
                    for bf in batch_files:
                        st.markdown(f"- 📄 `{bf.name}` ({bf.size/1024:.1f} KB)")
                else:
                    st.info("Upload one or more CV files to begin batch processing.")
                st.markdown("""
                **What happens automatically:**
                1. Each CV is parsed & name/email auto-detected
                2. ATS score calculated against the JD
                3. PASS → Assessment invite email sent
                4. FAIL → Rejection email sent
                5. Recruiter notified for each candidate
                """)
            st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)
            if batch_files and batch_jd.strip():
                if st.button(f"🚀 Process All {len(batch_files)} CVs", type="primary", use_container_width=True, key="batch_process_btn"):
                    results_list = []
                    progress_bar = st.progress(0, text="Processing CVs...")
                    for i, cv_file in enumerate(batch_files):
                        progress_bar.progress((i + 1) / len(batch_files), text=f"Processing {i+1}/{len(batch_files)}: {cv_file.name}")
                        cv_file.seek(0)
                        cv_text = parse_cv_text(cv_file)
                        cv_file.seek(0)
                        det_name = extract_candidate_name(cv_text) if cv_text else ""
                        det_email = extract_candidate_email(cv_text) if cv_text else ""
                        if not det_name:
                            det_name = cv_file.name.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title()
                        import time as _t
                        _t.sleep(0.05)
                        c_id = f"CAND-{datetime.now().strftime('%Y%m%d%H%M%S')}-{i+1:03d}"
                        if not cv_text or "ERROR_PARSING" in cv_text:
                            results_list.append({"file": cv_file.name, "name": det_name, "email": det_email or "—", "ats_score": 0, "decision": "ERROR", "status": "Parse Failed", "email_status": "—", "id": c_id})
                            add_log(c_id, "ATS_SCREENING", "ERROR", 0, "CV parsing failed", "Manual Review Required")
                            continue
                        result = calculate_ats_score(cv_text, batch_jd, batch_role)
                        candidate_data = {
                            "id": c_id, "name": det_name, "email": det_email, "role": batch_role,
                            "cv_text": cv_text[:500] + "..." if len(cv_text) > 500 else cv_text,
                            "ats_result": result,
                            "status": "Passed ATS" if result["decision"] == "PASS" else ("Manual Review" if result["requires_human_review"] else "Failed ATS"),
                            "assessment_result": None, "interview_scheduled": False, "emails_sent": [],
                            "interview_slots": [], "interview_panel": [],
                            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        }
                        dec = result["decision"]
                        email_status = "—"
                        if dec == "PASS":
                            add_log(c_id, "ATS_SCREENING", "PASS", result["ats_score"], result["reasoning_summary"], "Send Assessment (Auto)")
                            if st.session_state.get("_custom_assessment"):
                                db.save_custom_assessment(c_id, batch_role, json.dumps(st.session_state["_custom_assessment"]))
                            if det_email:
                                actions = auto_pipeline_action(candidate_data, "ats_pass")
                                candidate_data["status"] = "Assessment Sent"
                                email_status = "Sent" if any(a["status"] == "SENT" for a in actions) else "Queued"
                            else: email_status = "No email"
                        elif result["requires_human_review"]:
                            add_log(c_id, "ATS_SCREENING", "REVIEW", result["ats_score"], "Borderline score", "Escalate to Recruiter")
                            email_status = "Review"
                        else:
                            add_log(c_id, "ATS_SCREENING", "FAIL", result["ats_score"], result["reasoning_summary"], "Send Rejection (Auto)")
                            if det_email:
                                actions = auto_pipeline_action(candidate_data, "ats_fail")
                                email_status = "Sent" if any(a["status"] == "SENT" for a in actions) else "Queued"
                            else: email_status = "No email"
                        st.session_state.candidates[c_id] = candidate_data
                        db.save_candidate(candidate_data)
                        results_list.append({"file": cv_file.name, "name": det_name, "email": det_email or "—", "ats_score": result["ats_score"], "decision": dec, "status": candidate_data["status"], "email_status": email_status, "id": c_id})
                    progress_bar.progress(1.0, text="✅ All CVs processed!")
                    st.markdown("---")
                    st.markdown("## 📊 Batch Processing Results")
                    total_b = len(results_list)
                    passed_b = sum(1 for r in results_list if r["decision"] == "PASS")
                    failed_b = sum(1 for r in results_list if r["decision"] == "FAIL")
                    review_b = total_b - passed_b - failed_b
                    mc1, mc2, mc3, mc4 = st.columns(4)
                    with mc1: st.markdown(f'<div class="stat-card stat-blue"><div class="stat-value">{total_b}</div><div class="stat-label">Total CVs</div></div>', unsafe_allow_html=True)
                    with mc2: st.markdown(f'<div class="stat-card stat-green"><div class="stat-value">{passed_b}</div><div class="stat-label">Passed</div></div>', unsafe_allow_html=True)
                    with mc3: st.markdown(f'<div class="stat-card stat-red"><div class="stat-value">{failed_b}</div><div class="stat-label">Failed</div></div>', unsafe_allow_html=True)
                    with mc4: st.markdown(f'<div class="stat-card stat-orange"><div class="stat-value">{review_b}</div><div class="stat-label">Review/Error</div></div>', unsafe_allow_html=True)
                    st.markdown("### 📋 Detailed Results")
                    results_df = pd.DataFrame(results_list)
                    display_df = results_df[["file", "name", "email", "ats_score", "decision", "status", "email_status"]].copy()
                    display_df.columns = ["CV File", "Name", "Email", "ATS Score", "Decision", "Status", "Email Status"]
                    st.dataframe(display_df, use_container_width=True, hide_index=True)
                    st.markdown("### 👤 Individual Details")
                    for r in results_list:
                        dec_icon = "🟢" if r["decision"] == "PASS" else ("🔴" if r["decision"] == "FAIL" else "🟠")
                        with st.expander(f"{dec_icon} {r['name']} — {r['file']} — Score: {r['ats_score']} — {r['decision']}"):
                            cand_data = st.session_state.candidates.get(r["id"], {})
                            ats_r = cand_data.get("ats_result", {})
                            st.markdown(f"**ID:** {r['id']} | **Email:** {r['email']} | **ATS Score:** {r['ats_score']}")
                            if ats_r.get("matched_skills"):
                                st.markdown("**Matched:** " + " ".join([f'`{s}`' for s in ats_r["matched_skills"]]))
                            if ats_r.get("missing_skills"):
                                st.markdown("**Missing:** " + " ".join([f'`{s}`' for s in ats_r["missing_skills"]]))
                            if ats_r.get("reasoning_summary"):
                                st.caption(ats_r["reasoning_summary"])
                            cv_preview = cand_data.get("cv_text", "")[:300]
                            if cv_preview:
                                st.text_area("Parsed CV Preview", cv_preview, height=100, disabled=True, key=f"debug_{r['id']}")

        render_footer()

    


    # ═════════════════════════════════════════════
    # PAGE 2: ASSESSMENT
    # ═════════════════════════════════════════════
    elif page == "\U0001f4dd Assessment":
        st.markdown("""
        <div class="hero-banner animate-in">
            <h1>\U0001f4dd Role-Specific Assessment</h1>
            <p>30 curated questions • 20-minute timer • Anti-cheating monitored • Auto-scored</p>
        </div>
        """, unsafe_allow_html=True)

        if st.session_state.get("_arrived_via_link"):
            st.success("\u2705 Welcome via assessment link!")
            st.session_state["_arrived_via_link"] = False
            st.query_params.clear()

        cid = st.session_state.current_candidate_id
        if not cid or cid not in st.session_state.candidates:
            st.warning("\u26a0\ufe0f No active candidate. Complete ATS screening first.")
        else:
            cand = st.session_state.candidates[cid]
            status = cand.get("status", "")

            if status == "Failed ATS":
                st.error("\u274c This candidate did not pass ATS.")

            elif status in ["Passed Assessment", "Failed Assessment", "Interview Scheduled"] or cand.get("assessment_result"):
                ar = cand.get("assessment_result", {})
                score = ar.get("score_percent", "N/A")
                decision = ar.get("decision", status)

                # Show score circle
                if ar:
                    circ_class = "pass" if decision == "PASS" else "fail"
                    circ_color = "#065F46" if decision == "PASS" else "#991B1B"
                    st.markdown(f'<div style="text-align:center; margin:2rem 0;"><div class="score-circle {circ_class}" style="margin:0 auto;"><div class="score-value" style="color:{circ_color}">{score}%</div><div class="score-label" style="color:{circ_color}">{"PASSED" if decision == "PASS" else "FAILED"}</div></div></div>', unsafe_allow_html=True)

                    if decision == "PASS":
                        st.markdown(f'<div class="result-banner pass-banner">\U0001f389 {cand["name"]} PASSED — {ar.get("correct",0)}/{ar.get("total",0)} correct ({score}%)</div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="result-banner fail-banner">\u274c {cand["name"]} FAILED — {ar.get("correct",0)}/{ar.get("total",0)} correct ({score}%)</div>', unsafe_allow_html=True)

                    # Topic breakdown
                    with st.expander("\U0001f4c8 Topic Breakdown", expanded=True):
                        for topic, data in ar.get("topic_breakdown", {}).items():
                            pct = (data["correct"]/data["total"]*100) if data["total"] > 0 else 0
                            st.markdown(f"**{topic}**: {data['correct']}/{data['total']} ({pct:.0f}%)")
                            st.progress(min(pct/100, 1.0))

                    # Show strong/weak areas
                    s1, s2 = st.columns(2)
                    with s1:
                        st.markdown("#### \u2705 Strong Areas")
                        for s in ar.get("strength_areas", []):
                            st.markdown(f"- {s}")
                        if not ar.get("strength_areas"):
                            st.info("No strong areas identified.")
                    with s2:
                        st.markdown("#### \u26a0\ufe0f Weak Areas")
                        for w in ar.get("weak_areas", []):
                            st.markdown(f"- {w}")
                        if not ar.get("weak_areas"):
                            st.success("No weak areas!")
                else:
                    st.info(f"\u2139\ufe0f Assessment completed. Status: **{status}**. Check **Results & Interview** page.")

                st.info("\U0001f449 Go to **Results & Interview** page for next steps.")

            else:
                # Assessment not yet taken — show start button (for recruiter view)
                st.markdown(f'<div class="section-card"><strong>Candidate:</strong> {cand["name"]} | <strong>Role:</strong> {cand["role"]} | <strong>ATS:</strong> {cand["ats_result"]["ats_score"]}%</div>', unsafe_allow_html=True)
                with st.expander("\U0001f4cb Instructions", expanded=not st.session_state.assessment_started):
                    st.markdown("**30 MCQs • 20 min • Pass: > 90%**\n\n\u26a0\ufe0f No tab switching, copy-paste monitored.")

                if not st.session_state.assessment_started:
                    # if st.button("\U0001f680 Start Assessment", type="primary", use_container_width=True):
                        # st.session_state.assessment_questions = get_assessment_questions(cand["role"], 30)
                    if st.button("\U0001f680 Start Assessment", type="primary", use_container_width=True):
                        custom_qs = db.get_custom_assessment(cid)
                        if custom_qs and len(custom_qs) >= 5:
                            questions = custom_qs
                            random.shuffle(questions)
                            # st.session_state.assessment_questions = questions[:30]
                            st.session_state.assessment_questions = questions  # Use ALL custom questions
                        else:
                            st.session_state.assessment_questions = get_assessment_questions(cand["role"], 30)    
                        st.session_state.assessment_started = True
                        st.session_state.assessment_answers = {}
                        st.session_state.assessment_submitted = False
                        st.session_state.assessment_start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        add_log(cid, "ASSESSMENT_STARTED", "IN_PROGRESS", "N/A", "Started", "Awaiting submission")
                        st.rerun()
                else:
                    questions = st.session_state.get("assessment_questions", [])
                    if not questions:
                        st.error("Error loading questions.")
                    elif not st.session_state.assessment_submitted:
                        st.info(f"\u23f1\ufe0f **Started:** {st.session_state.get('assessment_start_time','')} | **Questions:** {len(questions)}")
                        for i, q in enumerate(questions):
                            st.markdown(f'<div class="question-card"><span class="q-number">Q{i+1}</span> <span class="q-meta">({q.get("topic","")}, {q.get("difficulty","")})</span><br><strong>{q["q"]}</strong></div>', unsafe_allow_html=True)
                            answer = st.radio(f"Q{i+1}:", options=q["options"], key=f"assess_q_{i}", index=None, label_visibility="collapsed")
                            if answer is not None:
                                st.session_state.assessment_answers[str(i)] = q["options"].index(answer)

                        answered = len(st.session_state.assessment_answers)
                        st.markdown(f"**Answered:** {answered} / {len(questions)}")
                        st.progress(answered / len(questions))

                        if st.button("\u2705 Submit Assessment", type="primary", use_container_width=True):
                            st.session_state.assessment_submitted = True
                            result = score_assessment(questions, st.session_state.assessment_answers)
                            st.session_state.assessment_result = result
                            decision = "PASS" if result["score_percent"] > 90 else "FAIL"
                            result["decision"] = decision
                            cand["assessment_result"] = result
                            cand["status"] = "Passed Assessment" if decision == "PASS" else "Failed Assessment"
                            add_log(cid, "ASSESSMENT", decision, result["score_percent"],
                                    f"{result['correct']}/{result['total']} ({result['score_percent']}%)",
                                    "Interview (Auto)" if decision == "PASS" else "Rejection (Auto)")
                            if decision == "PASS":
                                actions = auto_pipeline_action(cand, "assessment_pass")
                                cand["status"] = "Interview Scheduled"
                            else:
                                actions = auto_pipeline_action(cand, "assessment_fail")
                            cand["auto_actions_assessment"] = actions
                            st.session_state.candidates[cid] = cand
                            db.save_candidate(cand)
                            db.save_assessment_result(cid, result, cand["status"])
                            st.rerun()
                    else:
                        result = st.session_state.get("assessment_result", cand.get("assessment_result", {}))
                        decision = result.get("decision", "FAIL")
                        circ_class = "pass" if decision == "PASS" else "fail"
                        circ_color = "#065F46" if decision == "PASS" else "#991B1B"
                        st.markdown(f'<div style="text-align:center; margin:2rem 0;"><div class="score-circle {circ_class}" style="margin:0 auto;"><div class="score-value" style="color:{circ_color}">{result.get("score_percent",0)}%</div><div class="score-label" style="color:{circ_color}">{"PASSED" if decision == "PASS" else "FAILED"}</div></div></div>', unsafe_allow_html=True)
                        if decision == "PASS":
                            st.markdown(f'<div class="result-banner pass-banner">\U0001f389 PASSED — {result.get("correct",0)}/{result.get("total",0)}</div>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'<div class="result-banner fail-banner">\u274c FAILED — {result.get("correct",0)}/{result.get("total",0)}</div>', unsafe_allow_html=True)
                        with st.expander("\U0001f4c8 Topic Breakdown", expanded=True):
                            for topic, data in result.get("topic_breakdown", {}).items():
                                pct = (data["correct"]/data["total"]*100) if data["total"] > 0 else 0
                                st.markdown(f"**{topic}**: {data['correct']}/{data['total']} ({pct:.0f}%)")
                                st.progress(min(pct/100, 1.0))
                        auto_acts = cand.get("auto_actions_assessment", [])
                        if auto_acts:
                            show_automation_results(auto_acts)

        render_footer()


    # ═════════════════════════════════════════════
    # PAGE 3: RESULTS & INTERVIEW
    # ═════════════════════════════════════════════
    elif page == "\U0001f4ca Results & Interview":
        st.markdown("""
        <div class="hero-banner animate-in">
            <h1>\U0001f4ca Results & Interview Scheduling</h1>
            <p>Comprehensive results overview with automated interview scheduling</p>
        </div>
        """, unsafe_allow_html=True)

        cid = st.session_state.current_candidate_id
        if not cid or cid not in st.session_state.candidates:
            st.warning("\u26a0\ufe0f No active candidate.")
        else:
            cand = st.session_state.candidates[cid]
            st.markdown(f'<div class="section-card"><strong>{cand["name"]}</strong> | {cand["role"]} | <span class="status-badge badge-pending">{cand.get("status","Pending")}</span></div>', unsafe_allow_html=True)
            with st.expander("\U0001f4c4 ATS Summary"):
                ats = cand.get("ats_result", {})
                if ats: st.metric("ATS Score", f"{ats.get('ats_score', 0)}/100", delta=ats.get("decision","N/A"))
            assessment = cand.get("assessment_result")
            if assessment:
                with st.expander("\U0001f4dd Assessment Summary", expanded=True):
                    a1, a2, a3 = st.columns(3)
                    with a1: st.metric("Score", f"{assessment.get('score_percent', 0)}%")
                    with a2: st.metric("Result", assessment.get("decision","N/A"))
                    with a3: st.metric("Correct", f"{assessment.get('correct',0)}/{assessment.get('total',0)}")
                if assessment.get("decision") == "PASS":
                    st.success("\U0001f389 Interview scheduled!")
                    panel = cand.get("interview_panel", []); slots = cand.get("interview_slots", [])
                    if not panel or not slots:
                        avail = get_panel_availability(cand["role"]); panel = avail["panel"]; slots = avail["slots"]
                    st.markdown("### \U0001f465 Panel")
                    for p in panel: st.markdown(f"- **{p['name']}** — {p['title']}")
                    if slots:
                        st.dataframe(pd.DataFrame(slots).assign(panel=lambda x: x["panel"].apply(lambda v: ", ".join(v) if isinstance(v,list) else v)), use_container_width=True, hide_index=True)
                elif assessment.get("decision") == "FAIL":
                    st.error(f"\u274c Scored {assessment.get('score_percent', 0)}%")
            else:
                st.info("\u2139\ufe0f Assessment not yet completed.")
            emails = cand.get("emails_sent", [])
            if emails:
                st.markdown("### \U0001f4ec Emails")
                for em in emails:
                    with st.expander(f"{em['type']} — {em['timestamp']}"): st.code(em["content"], language="text")

        render_footer()


    # ═════════════════════════════════════════════
    # PAGE 4: PIPELINE LOGS
    # ═════════════════════════════════════════════
    elif page == "\U0001f4cb Pipeline Logs":
        st.markdown("""<div class="hero-banner animate-in"><h1>\U0001f4cb Pipeline Logs</h1><p>Full audit trail of all decisions</p></div>""", unsafe_allow_html=True)
        # logs = st.session_state.pipeline_logs
        logs = db.get_logs()  # Load from SQLite
        if not logs: st.info("No logs yet.")
        else:
            all_cids = list(set(l["candidate_id"] for l in logs))
            filt = st.selectbox("Filter by Candidate", ["All"] + all_cids)
            filtered = logs if filt == "All" else [l for l in logs if l["candidate_id"] == filt]
            st.dataframe(pd.DataFrame(filtered), use_container_width=True, hide_index=True)
            for log in filtered:
                icon = {"\u0050\u0041\u0053\u0053": "\U0001f7e2", "FAIL": "\U0001f534", "REVIEW": "\U0001f7e0", "IN_PROGRESS": "\U0001f535"}.get(log["decision"], "\u26aa")
                st.markdown(f"{icon} **[{log['timestamp']}]** `{log['stage']}` — **{log['decision']}** (Score: {log['score']})")
            st.download_button("\U0001f4e5 Download JSON", json.dumps(filtered, indent=2),
                               f"logs_{datetime.now().strftime('%Y%m%d')}.json", "application/json")
        render_footer()


    # ═════════════════════════════════════════════
    # PAGE 5: EMAIL LOG
    # ═════════════════════════════════════════════
    elif page == "\U0001f4e7 Email Log":
        st.markdown("""<div class="hero-banner animate-in"><h1>\U0001f4e7 Email Log</h1><p>Track all automated emails</p></div>""", unsafe_allow_html=True)
        # email_log = st.session_state.email_log
        email_log = db.get_email_logs()  # Load from SQLite
        if not email_log: st.info("No emails yet.")
        else:
            total = len(email_log)
            sent = sum(1 for e in email_log if e["status"] == "SENT")
            failed = sum(1 for e in email_log if e["status"] == "FAILED")
            queued = sum(1 for e in email_log if e["status"] == "QUEUED")
            c1, c2, c3, c4 = st.columns(4)
            with c1: st.markdown(f'<div class="stat-card stat-blue"><div class="stat-value">{total}</div><div class="stat-label">Total</div></div>', unsafe_allow_html=True)
            with c2: st.markdown(f'<div class="stat-card stat-green"><div class="stat-value">{sent}</div><div class="stat-label">Sent</div></div>', unsafe_allow_html=True)
            with c3: st.markdown(f'<div class="stat-card stat-red"><div class="stat-value">{failed}</div><div class="stat-label">Failed</div></div>', unsafe_allow_html=True)
            with c4: st.markdown(f'<div class="stat-card stat-orange"><div class="stat-value">{queued}</div><div class="stat-label">Queued</div></div>', unsafe_allow_html=True)
            st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)
            sf = st.selectbox("Filter Status", ["All", "SENT", "FAILED", "QUEUED"])
            fe = email_log if sf == "All" else [e for e in email_log if e["status"] == sf]
            for em in fe:
                tl = {"SENT": "timeline-sent", "FAILED": "timeline-failed", "QUEUED": "timeline-queued"}.get(em["status"], "")
                st.markdown(f'<div class="timeline-item {tl}"><strong>{em["type"]}</strong> \u2192 {em.get("to") or em.get("to_addr", "")}<br><small>{em["timestamp"]} — <strong>{em["status"]}</strong></small></div>', unsafe_allow_html=True)
            st.dataframe(pd.DataFrame(fe), use_container_width=True, hide_index=True)
            st.download_button("\U0001f4e5 Download", json.dumps(email_log, indent=2), f"emails_{datetime.now().strftime('%Y%m%d')}.json", "application/json")
        render_footer()


    # ═════════════════════════════════════════════
    # PAGE 6: CANDIDATE DASHBOARD
    # ═════════════════════════════════════════════
    elif page == "\U0001f464 Candidate Dashboard":
        st.markdown("""<div class="hero-banner animate-in"><h1>\U0001f464 Candidate Dashboard</h1><p>Overview of all candidates in the pipeline</p></div>""", unsafe_allow_html=True)
        candidates = st.session_state.candidates
        if not candidates: st.info("No candidates yet.")
        else:
            total = len(candidates)
            p_ats = sum(1 for c in candidates.values() if (c.get("ats_result") or {}).get("decision") == "PASS")
            p_ass = sum(1 for c in candidates.values() if c and (c.get("assessment_result") or {}).get("decision") == "PASS")
            ivw = sum(1 for c in candidates.values() if c.get("interview_scheduled"))
            c1, c2, c3, c4 = st.columns(4)
            with c1: st.markdown(f'<div class="stat-card stat-blue"><div class="stat-value">{total}</div><div class="stat-label">Total</div></div>', unsafe_allow_html=True)
            with c2: st.markdown(f'<div class="stat-card stat-green"><div class="stat-value">{p_ats}</div><div class="stat-label">Passed ATS</div></div>', unsafe_allow_html=True)
            with c3: st.markdown(f'<div class="stat-card stat-purple"><div class="stat-value">{p_ass}</div><div class="stat-label">Passed Assessment</div></div>', unsafe_allow_html=True)
            with c4: st.markdown(f'<div class="stat-card stat-orange"><div class="stat-value">{ivw}</div><div class="stat-label">Interviews</div></div>', unsafe_allow_html=True)
            st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)
            for cid_key, cv in candidates.items():
                status = cv.get("status", "Unknown")
                badge = "badge-pass" if "Pass" in status or "Interview" in status else ("badge-fail" if "Fail" in status else "badge-pending")
                with st.expander(f"**{cv['name']}** — {cv['role']} — {status}"):
                    st.markdown(f'<div class="candidate-card"><strong>{cv["name"]}</strong> <span class="status-badge {badge}">{status}</span><br><small>ID: {cid_key} | Email: {cv.get("email","N/A")}</small></div>', unsafe_allow_html=True)
                    i1, i2 = st.columns(2)
                    with i1: st.markdown(f"**ATS:** {cv.get('ats_result',{}).get('ats_score','N/A')}")
                    with i2: st.markdown(f"**Assessment:** {(cv.get('assessment_result') or {}).get('score_percent','N/A')}")
                    if st.button(f"Load {cv['name']}", key=f"load_{cid_key}"):
                        st.session_state.current_candidate_id = cid_key; st.rerun()
                    if cv.get("status") == "Manual Review":
                        st.markdown("---")
                        st.warning(f"⚠️ **Recruiter Decision Required** — ATS Score: {cv.get('ats_result',{}).get('ats_score','N/A')}%")
                        _dc1, _dc2 = st.columns(2)
                        with _dc1:
                            if st.button("✅ Approve", type="primary", use_container_width=True, key=f"da_{cid_key}"):
                                cv["status"] = "Assessment Sent"
                                cv["ats_result"]["decision"] = "PASS"
                                add_log(cid_key, "RECRUITER_OVERRIDE", "PASS", cv["ats_result"]["ats_score"], "Approved by recruiter", "Send Assessment")
                                auto_pipeline_action(cv, "ats_pass")
                                st.session_state.candidates[cid_key] = cv
                                st.rerun()
                        with _dc2:
                            if st.button("❌ Reject", use_container_width=True, key=f"dr_{cid_key}"):
                                cv["status"] = "Failed ATS"
                                cv["ats_result"]["decision"] = "FAIL"
                                add_log(cid_key, "RECRUITER_OVERRIDE", "FAIL", cv["ats_result"]["ats_score"], "Rejected by recruiter", "Send Rejection")
                                auto_pipeline_action(cv, "ats_fail")
                                st.session_state.candidates[cid_key] = cv
                                st.rerun()    
        render_footer()


    # ═════════════════════════════════════════════
    # PAGE 7: ANALYTICS
    # ═════════════════════════════════════════════
    elif page == "\U0001f4ca Analytics":
        render_analytics_page()
