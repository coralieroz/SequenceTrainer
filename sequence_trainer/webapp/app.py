"""Flask app — thin routing only.

Every route body here is: parse request -> call session/scoring/storage ->
jsonify. No game rules, no CSV logic, no stats math lives in this file —
those live in session.py / questions.py / generators.py, scoring.py, and
storage.py respectively.

In-process session registry (SESSIONS): fine for a single local user; no DB.
"""

import json

from flask import Flask, jsonify, render_template, request

from .. import scoring, storage
from .. import session as session_module

app = Flask(__name__)

SESSIONS: dict = {}


def _json_body() -> dict:
    """Accepts application/json AND the text/plain Content-Type that
    navigator.sendBeacon() sends by default (used for the pagehide ->
    /api/session/end beacon).
    """
    data = request.get_json(silent=True)
    if data is not None:
        return data
    if request.data:
        try:
            return json.loads(request.data.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}
    return {}


def _get_session(session_id):
    return SESSIONS.get(session_id)


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

@app.get("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@app.get("/api/users")
def get_users():
    return jsonify({"users": storage.load_users()})


@app.post("/api/users")
def post_users():
    body = _json_body()
    try:
        users = storage.add_user(body.get("name", ""))
    except storage.UsernameError as e:
        return jsonify({"error": str(e)}), 409
    return jsonify({"users": users})


# ---------------------------------------------------------------------------
# Home-tab stats
# ---------------------------------------------------------------------------

@app.get("/api/stats")
def get_stats():
    user = request.args.get("user", "")
    if not storage.user_exists(user):
        return jsonify({"error": "unknown user"}), 404
    sessions = storage.load_sessions(user)
    return jsonify({
        "contribution": scoring.contribution_graph(sessions),
        "highest_score": scoring.highest_score(sessions),
        "speed_trend": scoring.speed_trend(sessions),
        "last_session": scoring.last_session_panel(sessions),
    })


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

@app.post("/api/session/start")
def start_session():
    body = _json_body()
    user = body.get("user", "")
    if not storage.user_exists(user):
        return jsonify({"error": "unknown user"}), 404
    minutes = body.get("minutes", 10)
    s = session_module.Session(user=user, minutes=minutes)
    SESSIONS[s.session_id] = s
    return jsonify({"session_id": s.session_id, "seconds_left": round(s.seconds_left(), 3)})


@app.get("/api/question")
def get_question():
    s = _get_session(request.args.get("session_id", ""))
    if s is None:
        return jsonify({"error": "unknown session"}), 404
    return jsonify(s.next_question())


@app.post("/api/answer")
def post_answer():
    body = _json_body()
    s = _get_session(body.get("session_id", ""))
    if s is None:
        return jsonify({"error": "unknown session"}), 404
    result = s.submit(body.get("question_id", ""), body.get("answer", ""))
    if result.get("stale"):
        return jsonify({"error": "stale"}), 409
    return jsonify(result)


@app.get("/api/session/summary")
def session_summary():
    s = _get_session(request.args.get("session_id", ""))
    if s is None:
        return jsonify({"error": "unknown session"}), 404
    return jsonify(s.summary_poll())


@app.post("/api/session/end")
def end_session():
    body = _json_body()
    s = _get_session(body.get("session_id", ""))
    if s is None:
        return jsonify({"error": "unknown session"}), 404
    return jsonify(s.end())
