"""storage.py — the ONLY module in this package that touches the filesystem.

Owns: users.json registry, and per-user questions.csv / sessions.csv under
sequence_trainer/data/<sanitised-name>/. Every write retries once after a
short pause on PermissionError, because data/ lives inside OneDrive and its
sync client can transiently lock a file mid-write.

CSV writes use csv.DictWriter in append mode with newline="" (per the csv
module's own recommendation on Windows) and write the header only when the
file doesn't exist yet.
"""

import csv
import json
import re
import time
from pathlib import Path

from . import config

_RETRY_DELAY = 0.5
USERNAME_RE = re.compile(r"^[A-Za-z0-9 _-]{1,30}$")

QUESTION_FIELDS = [
    "session_id", "timestamp", "item_type", "difficulty", "correct",
    "response_time", "shown_terms", "user_answer", "correct_answer",
]
SESSION_FIELDS = [
    "session_id", "started_at", "planned_seconds", "actual_seconds",
    "questions_answered", "correct", "wrong", "net_score_per_min",
    "accuracy", "avg_response_time", "completed",
]


class UsernameError(ValueError):
    """Invalid or duplicate username (server-side add-user validation)."""


def _retry_on_permission_error(fn):
    try:
        return fn()
    except PermissionError:
        time.sleep(_RETRY_DELAY)
        return fn()


# ---------------------------------------------------------------------------
# Users registry
# ---------------------------------------------------------------------------

def _ensure_data_dir():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)


def _read_registry():
    if not config.USERS_FILE.exists():
        return None

    def _read():
        with open(config.USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    data = _retry_on_permission_error(_read)
    return data.get("users", [])


def _write_registry(users: list):
    def _write():
        with open(config.USERS_FILE, "w", encoding="utf-8") as f:
            json.dump({"users": users}, f, indent=2)

    _retry_on_permission_error(_write)


def sanitise_folder(display_name: str) -> str:
    """Folder name = trimmed, lowercased, spaces -> underscores. Display name
    is kept verbatim in users.json; only the folder is normalised.
    """
    return display_name.strip().lower().replace(" ", "_")


def user_dir(display_name: str) -> Path:
    return config.DATA_DIR / sanitise_folder(display_name)


def load_users() -> list:
    """Returns the registry list, creating it (with default user "Cora") on
    first run, and ensures every registered user has a data folder.
    """
    _ensure_data_dir()
    users = _read_registry()
    if users is None:
        users = [config.DEFAULT_USER]
        _write_registry(users)
    for u in users:
        user_dir(u).mkdir(parents=True, exist_ok=True)
    return users


def validate_username(name: str) -> str:
    """Returns the trimmed name if valid, else raises UsernameError.

    Rules: non-empty after trim, 1-30 chars, letters/digits/space/hyphen/
    underscore only.
    """
    trimmed = (name or "").strip()
    if not trimmed:
        raise UsernameError("Name cannot be empty.")
    if not USERNAME_RE.match(trimmed):
        raise UsernameError(
            "Name may only contain letters, digits, spaces, hyphens and "
            "underscores (max 30 characters)."
        )
    return trimmed


def user_exists(name: str) -> bool:
    return any(u.lower() == (name or "").strip().lower() for u in load_users())


def add_user(name: str) -> list:
    """Validates + adds a new user; returns the updated registry list.

    Raises UsernameError on invalid input or a case-insensitive duplicate.
    """
    trimmed = validate_username(name)
    users = load_users()
    if any(u.lower() == trimmed.lower() for u in users):
        raise UsernameError(f'"{trimmed}" is already taken.')
    users.append(trimmed)
    _write_registry(users)
    user_dir(trimmed).mkdir(parents=True, exist_ok=True)
    return users


# ---------------------------------------------------------------------------
# CSV append helpers (session.py is the only caller)
# ---------------------------------------------------------------------------

def _append_row(path: Path, fieldnames: list, row: dict):
    path.parent.mkdir(parents=True, exist_ok=True)

    def _write():
        is_new = not path.exists()
        with open(path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if is_new:
                writer.writeheader()
            writer.writerow(row)

    _retry_on_permission_error(_write)


def append_question_row(user: str, row: dict):
    _append_row(user_dir(user) / "questions.csv", QUESTION_FIELDS, row)


def append_session_row(user: str, row: dict):
    _append_row(user_dir(user) / "sessions.csv", SESSION_FIELDS, row)


# ---------------------------------------------------------------------------
# CSV load helpers (typed) — scoring.py home-tab aggregates read through these
# ---------------------------------------------------------------------------

def _read_csv(path: Path) -> list:
    if not path.exists():
        return []

    def _read():
        with open(path, "r", newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    return _retry_on_permission_error(_read)


def _to_int(v):
    return int(v) if v not in (None, "") else None


def _to_float(v):
    return float(v) if v not in (None, "") else None


def load_sessions(user: str) -> list:
    """Typed rows from sessions.csv (empty rate/avg fields become None)."""
    rows = _read_csv(user_dir(user) / "sessions.csv")
    out = []
    for r in rows:
        out.append({
            "session_id": r["session_id"],
            "started_at": r["started_at"],
            "planned_seconds": _to_int(r["planned_seconds"]),
            "actual_seconds": _to_float(r["actual_seconds"]),
            "questions_answered": _to_int(r["questions_answered"]),
            "correct": _to_int(r["correct"]),
            "wrong": _to_int(r["wrong"]),
            "net_score_per_min": _to_float(r["net_score_per_min"]),
            "accuracy": _to_float(r["accuracy"]),
            "avg_response_time": _to_float(r["avg_response_time"]),
            "completed": _to_int(r["completed"]),
        })
    return out


def load_questions(user: str) -> list:
    """Typed rows from questions.csv."""
    rows = _read_csv(user_dir(user) / "questions.csv")
    out = []
    for r in rows:
        out.append({
            "session_id": r["session_id"],
            "timestamp": r["timestamp"],
            "item_type": r["item_type"],
            "difficulty": _to_int(r["difficulty"]),
            "correct": _to_int(r["correct"]),
            "response_time": _to_float(r["response_time"]),
            "shown_terms": r["shown_terms"].split("|") if r["shown_terms"] else [],
            "user_answer": r["user_answer"],
            "correct_answer": r["correct_answer"],
        })
    return out
