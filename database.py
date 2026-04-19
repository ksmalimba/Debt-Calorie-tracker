import sqlite3
import os
from datetime import date, datetime
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "accountability.db")
USE_SUPABASE = os.getenv("USE_SUPABASE", "false").lower() == "true"

# ── Supabase client (only loaded when needed) ─────────────────────────────────
def get_supabase():
    from supabase import create_client
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env")
    return create_client(url, key)


# ── SQLite bootstrap ───────────────────────────────────────────────────────────
def init_db():
    """Create all tables if they don't exist (SQLite only)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            email           TEXT    UNIQUE NOT NULL,
            password_hash   TEXT    NOT NULL,
            name            TEXT,
            height_cm       REAL,
            weight_kg       REAL,
            age             INTEGER,
            gender          TEXT,
            activity_level  TEXT,
            tdee            REAL,
            target_weight   REAL,
            weekly_target   REAL    DEFAULT 0.5,
            kcal_per_kg     REAL    DEFAULT 7700,
            created_at      TEXT    DEFAULT (datetime('now'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS daily_logs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            log_date        TEXT    NOT NULL,
            calories_in     REAL,
            tracked         INTEGER DEFAULT 1,
            calories_burned REAL,
            notes           TEXT,
            UNIQUE(user_id, log_date),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS debt_ledger (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            debt_calories   REAL    NOT NULL,
            carried_from    TEXT    NOT NULL,
            resolved        INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS weight_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            log_date    TEXT    NOT NULL,
            weight_kg   REAL    NOT NULL,
            UNIQUE(user_id, log_date),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()


# ── Generic helpers ────────────────────────────────────────────────────────────
def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── USER ──────────────────────────────────────────────────────────────────────
def create_user(email, password_hash, name, height_cm, weight_kg, age,
                gender, activity_level, tdee, target_weight, weekly_target):
    with _conn() as conn:
        conn.execute("""
            INSERT INTO users
              (email, password_hash, name, height_cm, weight_kg, age,
               gender, activity_level, tdee, target_weight, weekly_target)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (email, password_hash, name, height_cm, weight_kg, age,
              gender, activity_level, tdee, target_weight, weekly_target))
        conn.commit()


def get_user_by_email(email):
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id):
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    return dict(row) if row else None


def update_user_profile(user_id, **kwargs):
    allowed = {"name", "height_cm", "weight_kg", "age", "gender",
               "activity_level", "tdee", "target_weight", "weekly_target", "kcal_per_kg"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [user_id]
    with _conn() as conn:
        conn.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)
        conn.commit()


# ── DAILY LOG ─────────────────────────────────────────────────────────────────
def upsert_daily_log(user_id, log_date, calories_in=None,
                     tracked=1, calories_burned=None, notes=None):
    with _conn() as conn:
        existing = conn.execute(
            "SELECT id FROM daily_logs WHERE user_id=? AND log_date=?",
            (user_id, str(log_date))
        ).fetchone()
        if existing:
            conn.execute("""
                UPDATE daily_logs
                SET calories_in=?, tracked=?, calories_burned=?, notes=?
                WHERE user_id=? AND log_date=?
            """, (calories_in, tracked, calories_burned, notes,
                  user_id, str(log_date)))
        else:
            conn.execute("""
                INSERT INTO daily_logs
                  (user_id, log_date, calories_in, tracked, calories_burned, notes)
                VALUES (?,?,?,?,?,?)
            """, (user_id, str(log_date), calories_in, tracked, calories_burned, notes))
        conn.commit()


def get_log_for_date(user_id, log_date):
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM daily_logs WHERE user_id=? AND log_date=?",
            (user_id, str(log_date))
        ).fetchone()
    return dict(row) if row else None


def get_logs_for_range(user_id, start_date, end_date):
    with _conn() as conn:
        rows = conn.execute("""
            SELECT * FROM daily_logs
            WHERE user_id=? AND log_date BETWEEN ? AND ?
            ORDER BY log_date ASC
        """, (user_id, str(start_date), str(end_date))).fetchall()
    return [dict(r) for r in rows]


# ── DEBT LEDGER ───────────────────────────────────────────────────────────────
def add_debt(user_id, debt_calories, carried_from):
    with _conn() as conn:
        conn.execute("""
            INSERT INTO debt_ledger (user_id, debt_calories, carried_from)
            VALUES (?,?,?)
        """, (user_id, debt_calories, str(carried_from)))
        conn.commit()


def get_active_debt(user_id):
    with _conn() as conn:
        rows = conn.execute("""
            SELECT * FROM debt_ledger
            WHERE user_id=? AND resolved=0
            ORDER BY carried_from ASC
        """, (user_id,)).fetchall()
    return [dict(r) for r in rows]


def resolve_debt(debt_id):
    with _conn() as conn:
        conn.execute(
            "UPDATE debt_ledger SET resolved=1 WHERE id=?", (debt_id,)
        )
        conn.commit()


def get_total_active_debt(user_id):
    debts = get_active_debt(user_id)
    return sum(d["debt_calories"] for d in debts)


# ── WEIGHT LOG ────────────────────────────────────────────────────────────────
def upsert_weight(user_id, log_date, weight_kg):
    with _conn() as conn:
        existing = conn.execute(
            "SELECT id FROM weight_log WHERE user_id=? AND log_date=?",
            (user_id, str(log_date))
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE weight_log SET weight_kg=? WHERE user_id=? AND log_date=?",
                (weight_kg, user_id, str(log_date))
            )
        else:
            conn.execute(
                "INSERT INTO weight_log (user_id, log_date, weight_kg) VALUES (?,?,?)",
                (user_id, str(log_date), weight_kg)
            )
        conn.commit()
    # also update the "current" weight on the user profile
    update_user_profile(user_id, weight_kg=weight_kg)


def get_weight_history(user_id, limit=52):
    with _conn() as conn:
        rows = conn.execute("""
            SELECT * FROM weight_log
            WHERE user_id=?
            ORDER BY log_date DESC
            LIMIT ?
        """, (user_id, limit)).fetchall()
    return [dict(r) for r in reversed(rows)]
