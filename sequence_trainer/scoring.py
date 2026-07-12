"""Pure stat functions — no I/O, no randomness. Two jobs:

  1. session_stats(): reduce a session's in-memory results list into the
     numbers session.py needs for its summary + sessions.csv row. session.py
     calls this with its own in-memory results — it never re-reads a CSV to
     compute these.
  2. Home-tab aggregates (contribution / best_session / speed_trend /
     last_session_panel): computed from already-loaded CSV history
     (storage.load_sessions()), called by the /api/stats route.

All rates/averages are null-guarded against zero questions or zero elapsed
time — never raise, never divide by zero.
"""


def session_stats(results: list, actual_seconds: float) -> dict:
    """results: list of {"correct": bool, "response_time": float, ...} for
    one session (in-memory, never from CSV). Returns questions_answered,
    correct, wrong, net_score_per_min, accuracy, avg_response_time — the
    rate/average fields are None when there are 0 questions (or, degenerately,
    0 elapsed seconds).
    """
    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    wrong = total - correct

    if total == 0:
        return {
            "questions_answered": 0,
            "correct": 0,
            "wrong": 0,
            "net_score_per_min": None,
            "accuracy": None,
            "avg_response_time": None,
        }

    accuracy = round(correct / total, 4)
    avg_response_time = round(sum(r["response_time"] for r in results) / total, 4)

    minutes = actual_seconds / 60.0 if actual_seconds and actual_seconds > 0 else None
    net_score_per_min = round((correct - wrong) / minutes, 3) if minutes else None

    return {
        "questions_answered": total,
        "correct": correct,
        "wrong": wrong,
        "net_score_per_min": net_score_per_min,
        "accuracy": accuracy,
        "avg_response_time": avg_response_time,
    }


# ---------------------------------------------------------------------------
# Home-tab aggregates (input: storage.load_sessions(user) typed rows)
# ---------------------------------------------------------------------------

def _eligible(sessions: list) -> list:
    """completed==1 AND questions_answered>=1 — the "real" sessions used for
    highest score, speed trend, and the last-training panel.
    """
    return [
        s for s in sessions
        if s.get("completed") == 1 and (s.get("questions_answered") or 0) >= 1
    ]


def contribution_graph(sessions: list) -> list:
    """ALL sessions (aborted included) grouped by local date (from
    started_at's date prefix), minutes = sum(actual_seconds)/60 for that
    date. Returns a date-sorted list of {"date", "minutes"}.
    """
    by_date = {}
    for s in sessions:
        started_at = s.get("started_at") or ""
        date = started_at[:10]
        if not date:
            continue
        minutes = (s.get("actual_seconds") or 0.0) / 60.0
        by_date[date] = by_date.get(date, 0.0) + minutes
    return [{"date": d, "minutes": round(m, 2)} for d, m in sorted(by_date.items())]


def best_session(sessions: list):
    """The eligible session with the highest net_score_per_min, returning
    its score AND that SAME session's accuracy (not the overall best
    accuracy) as {"score", "accuracy"}, or None if no session is eligible.
    Ties broken by most recent started_at.
    """
    elig = [s for s in _eligible(sessions) if s["net_score_per_min"] is not None]
    if not elig:
        return None
    elig.sort(key=lambda s: (s["net_score_per_min"], s.get("started_at") or ""))
    best = elig[-1]
    return {"score": best["net_score_per_min"], "accuracy": best["accuracy"]}


def speed_trend(sessions: list) -> list:
    """Chronological [{"date", "score"}] over eligible sessions."""
    elig = [s for s in _eligible(sessions) if s["net_score_per_min"] is not None]
    elig.sort(key=lambda s: s.get("started_at") or "")
    return [{"date": (s.get("started_at") or "")[:10], "score": s["net_score_per_min"]} for s in elig]


def last_session_panel(sessions: list):
    """Stats for the latest eligible session, or None ("No sessions yet")."""
    elig = [s for s in _eligible(sessions) if s["net_score_per_min"] is not None]
    if not elig:
        return None
    elig.sort(key=lambda s: s.get("started_at") or "")
    last = elig[-1]
    return {
        "score_per_min": last["net_score_per_min"],
        "accuracy": last["accuracy"],
        "correct": last["correct"],
        "total": last["questions_answered"],
        "avg_response_time": last["avg_response_time"],
    }
