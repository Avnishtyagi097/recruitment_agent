"""
db_manager.py — SQLite persistence layer for TalentEdge Recruitment App.

Drop this file next to your main app .py file.
Import and use instead of session_state for all candidate/log/email data.

Usage:
    from db_manager import db
    db.init()
    db.save_candidate(candidate_data)
    candidates = db.get_all_candidates()
"""

import sqlite3
import json
import os
from datetime import datetime

DB_FILE = "recruitment_users.db"


def _conn():
    """Get a database connection with row factory."""
    c = sqlite3.connect(DB_FILE)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")  # Better concurrent access
    return c


# ═══════════════════════════════════════════
# INITIALIZATION
# ═══════════════════════════════════════════

def init():
    """Create all tables if they don't exist. Call once at app startup."""
    c = _conn()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS candidates (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            role TEXT,
            cv_text TEXT,
            ats_result TEXT,
            ats_score REAL DEFAULT 0,
            ats_decision TEXT DEFAULT '',
            assessment_result TEXT,
            assessment_score REAL,
            assessment_decision TEXT,
            status TEXT DEFAULT 'Pending',
            interview_scheduled INTEGER DEFAULT 0,
            interview_slots TEXT,
            interview_panel TEXT,
            emails_sent TEXT DEFAULT '[]',
            auto_actions TEXT,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS pipeline_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id TEXT,
            timestamp TEXT,
            stage TEXT,
            decision TEXT,
            score TEXT,
            reason TEXT,
            next_action TEXT,
            owner TEXT DEFAULT 'AI_AGENT'
        );

        CREATE TABLE IF NOT EXISTS email_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            to_addr TEXT,
            subject TEXT,
            type TEXT,
            status TEXT,
            detail TEXT
        );

        CREATE TABLE IF NOT EXISTS assessment_credentials (
            token TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            candidate_id TEXT NOT NULL,
            candidate_name TEXT NOT NULL,
            created_at TEXT
        );
        
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
    """)
    c.commit()
    c.close()


# ═══════════════════════════════════════════
# CANDIDATES
# ═══════════════════════════════════════════

def save_candidate(data):
    """Save or update a candidate record. `data` is the candidate dict from session_state."""
    c = _conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("""
        INSERT OR REPLACE INTO candidates
        (id, name, email, role, cv_text, ats_result, ats_score, ats_decision,
         assessment_result, assessment_score, assessment_decision,
         status, interview_scheduled, interview_slots, interview_panel,
         emails_sent, auto_actions, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        data.get("id", ""),
        data.get("name", ""),
        data.get("email", ""),
        data.get("role", ""),
        data.get("cv_text", ""),
        json.dumps(data.get("ats_result", {})),
        data.get("ats_result", {}).get("ats_score", 0),
        data.get("ats_result", {}).get("decision", ""),
        json.dumps(data.get("assessment_result")) if data.get("assessment_result") else None,
        (data.get("assessment_result") or {}).get("score_percent"),
        (data.get("assessment_result") or {}).get("decision"),
        data.get("status", "Pending"),
        1 if data.get("interview_scheduled") else 0,
        json.dumps(data.get("interview_slots", [])),
        json.dumps(data.get("interview_panel", [])),
        json.dumps(data.get("emails_sent", [])),
        json.dumps(data.get("auto_actions_assessment", [])),
        data.get("created_at", now),
        now,
    ))
    c.commit()
    c.close()




def save_setting(key, value):
    c = _conn()
    c.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?,?)", (key, value))
    c.commit()
    c.close()

def get_setting(key, default=""):
    c = _conn()
    row = c.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    c.close()
    return row["value"] if row else default

def _row_to_candidate(row):
    """Convert a database row to a candidate dict matching session_state format."""
    if not row:
        return None

    def _pj(val, default=None):
        if val is None:
            return default
        if isinstance(val, (dict, list)):
            return val
        try:
            return json.loads(val)
        except Exception:
            return default

    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "role": row["role"],
        "cv_text": row["cv_text"] or "",
        "ats_result": _pj(row["ats_result"], {}),
        "assessment_result": _pj(row["assessment_result"], None),
        "status": row["status"] or "Pending",
        "interview_scheduled": bool(row["interview_scheduled"]),
        "interview_slots": _pj(row["interview_slots"], []),
        "interview_panel": _pj(row["interview_panel"], []),
        "emails_sent": _pj(row["emails_sent"], []),
        "auto_actions_assessment": _pj(row["auto_actions"], []),
        "created_at": row["created_at"] or "",
    }

def get_candidate(candidate_id):
    """Get a single candidate by ID. Returns dict or None."""
    c = _conn()
    row = c.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    c.close()
    return _row_to_candidate(row)


def get_all_candidates():
    """Get all candidates as a dict: {id: candidate_data}."""
    c = _conn()
    rows = c.execute("SELECT * FROM candidates ORDER BY created_at DESC").fetchall()
    c.close()
    result = {}
    for row in rows:
        cand = _row_to_candidate(row)
        if cand:
            result[cand["id"]] = cand
    return result


def update_candidate_status(candidate_id, status):
    """Quick status update."""
    c = _conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("UPDATE candidates SET status = ?, updated_at = ? WHERE id = ?",
              (status, now, candidate_id))
    c.commit()
    c.close()


def save_assessment_result(candidate_id, result_dict, status):
    """Save assessment result for a candidate."""
    c = _conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("""
        UPDATE candidates SET
            assessment_result = ?,
            assessment_score = ?,
            assessment_decision = ?,
            status = ?,
            updated_at = ?
        WHERE id = ?
    """, (
        json.dumps(result_dict),
        result_dict.get("score_percent"),
        result_dict.get("decision"),
        status,
        now,
        candidate_id,
    ))
    c.commit()
    c.close()


# ═══════════════════════════════════════════
# PIPELINE LOGS
# ═══════════════════════════════════════════

def save_log(entry):
    """Save a pipeline log entry. `entry` is a dict with candidate_id, stage, decision, etc."""
    c = _conn()
    c.execute("""
        INSERT INTO pipeline_logs (candidate_id, timestamp, stage, decision, score, reason, next_action, owner)
        VALUES (?,?,?,?,?,?,?,?)
    """, (
        entry.get("candidate_id", ""),
        entry.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        entry.get("stage", ""),
        entry.get("decision", ""),
        str(entry.get("score", "")),
        entry.get("reason", ""),
        entry.get("next_action", ""),
        entry.get("owner", "AI_AGENT"),
    ))
    c.commit()
    c.close()


def get_logs(candidate_id=None):
    """Get pipeline logs, optionally filtered by candidate_id."""
    c = _conn()
    if candidate_id:
        rows = c.execute("SELECT * FROM pipeline_logs WHERE candidate_id = ? ORDER BY id DESC", (candidate_id,)).fetchall()
    else:
        rows = c.execute("SELECT * FROM pipeline_logs ORDER BY id DESC").fetchall()
    c.close()
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════
# EMAIL LOGS
# ═══════════════════════════════════════════

def save_email_log(entry):
    """Save an email log entry."""
    c = _conn()
    c.execute("""
        INSERT INTO email_logs (timestamp, to_addr, subject, type, status, detail)
        VALUES (?,?,?,?,?,?)
    """, (
        entry.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        entry.get("to", ""),
        entry.get("subject", ""),
        entry.get("type", ""),
        entry.get("status", ""),
        entry.get("detail", ""),
    ))
    c.commit()
    c.close()


def get_email_logs():
    """Get all email logs."""
    c = _conn()
    rows = c.execute("SELECT * FROM email_logs ORDER BY id DESC").fetchall()
    c.close()
    results = []
    for r in rows:
        d = dict(r)
        d["to"] = d.pop("to_addr", "")  # Rename to match session_state format
        results.append(d)
    return results


# ═══════════════════════════════════════════
# ASSESSMENT CREDENTIALS
# ═══════════════════════════════════════════

def save_assessment_creds(token, username, password, candidate_id, candidate_name):
    """Store assessment login credentials."""
    c = _conn()
    c.execute("""
        INSERT OR REPLACE INTO assessment_credentials (token, username, password, candidate_id, candidate_name, created_at)
        VALUES (?,?,?,?,?,?)
    """, (token, username, password, candidate_id, candidate_name,
          datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    c.commit()
    c.close()


def get_assessment_creds(token):
    """Get assessment credentials by token. Returns dict or None."""
    c = _conn()
    row = c.execute("SELECT * FROM assessment_credentials WHERE token = ?", (token,)).fetchone()
    c.close()
    if row:
        return {
            "username": row["username"],
            "password": row["password"],
            "candidate_id": row["candidate_id"],
            "candidate_name": row["candidate_name"],
        }
    return None


# ═══════════════════════════════════════════
# SYNC HELPERS (bridge session_state ↔ SQLite)
# ═══════════════════════════════════════════

# def sync_candidates_to_session(session_state):
#     """Load all candidates from SQLite into session_state.candidates."""
#     db_candidates = get_all_candidates()
#     for cid, cand in db_candidates.items():
#         if cid not in session_state.candidates:
#             session_state.candidates[cid] = cand
#         else:
#             # Update from DB if DB has newer data (e.g., assessment submitted by candidate)
#             ss_cand = session_state.candidates[cid]
#             if not ss_cand.get("assessment_result") and cand.get("assessment_result"):
#                 session_state.candidates[cid] = cand
#             elif cand.get("status") != ss_cand.get("status"):
#                 # DB might have updates from candidate session
#                 if cand.get("assessment_result"):
#                     session_state.candidates[cid] = cand

def sync_candidates_to_session(session_state):
    """Load all candidates from SQLite into session_state. SQLite always wins."""
    db_candidates = get_all_candidates()
    for cid, cand in db_candidates.items():
        session_state.candidates[cid] = cand


def sync_session_to_db(session_state):
    """Save all session_state candidates to SQLite."""
    for cid, cand in session_state.candidates.items():
        save_candidate(cand)