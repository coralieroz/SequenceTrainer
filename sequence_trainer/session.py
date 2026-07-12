"""Session — owns one practise session end to end: deadline authority,
question dispensing, result collection, and the one-time CSV write.

Time authority: time.perf_counter() is the ONLY clock consulted anywhere in
this class (deadline math, response-time math). Wall-clock time.localtime()
is used exactly twice, at construction, purely to produce human-readable
session_id / started_at strings for the CSV — it never participates in any
expiry or duration calculation.

Stats are always computed from self._results (in-memory), never by
re-reading a CSV — see scoring.session_stats().
"""

import time
import uuid
from dataclasses import dataclass

from . import config, scoring, storage
from .questions import Question, check, make_question, parse_answer


@dataclass
class _Issued:
    question_id: str
    question: Question
    issued_at: float  # perf_counter() timestamp


class Session:
    def __init__(self, user: str, minutes):
        minutes = max(config.MIN_SESSION_MINUTES, min(config.MAX_SESSION_MINUTES, int(minutes)))
        self.user = user
        self.planned_seconds = minutes * 60

        now = time.localtime()
        self.session_id = time.strftime("%Y%m%d-%H%M%S", now)
        self.started_at = time.strftime("%Y-%m-%dT%H:%M:%S", now)

        self._start_perf = time.perf_counter()
        self._deadline = self._start_perf + self.planned_seconds

        self._current: _Issued | None = None
        self._results = []  # list of dicts, one per judged (non-rejected) answer

        self._finalized = False
        self._final_summary = None

    # ---- time ----------------------------------------------------------

    def seconds_left(self) -> float:
        return max(0.0, self._deadline - time.perf_counter())

    def is_expired(self) -> bool:
        return time.perf_counter() >= self._deadline

    # ---- question flow ---------------------------------------------------

    def next_question(self) -> dict:
        """Payload for GET /api/question."""
        if self.is_expired():
            return {"expired": True, "summary": self.finalize(completed=1)}

        question = make_question(config.M)
        question_id = uuid.uuid4().hex
        self._current = _Issued(question_id=question_id, question=question, issued_at=time.perf_counter())
        return {
            "expired": False,
            "question_id": question_id,
            "terms": [str(t) for t in question.shown_terms],
            "seconds_left": round(self.seconds_left(), 3),
        }

    def submit(self, question_id: str, raw_answer: str) -> dict:
        """Payload for POST /api/answer. Result is one of:
        "correct" | "wrong" | "rejected" (all -> expired:false),
        or expired:true + summary, or {"stale": True} for an unknown /
        already-judged / double-submitted question_id (server re-checks
        the deadline first, so a post-deadline answer is discarded — the
        in-flight question counts as neither correct nor a miss).
        """
        if self.is_expired():
            self._current = None
            return {"expired": True, "summary": self.finalize(completed=1)}

        if self._current is None or self._current.question_id != question_id:
            return {"stale": True}

        issued = self._current
        response_time = time.perf_counter() - issued.issued_at
        question = issued.question
        answer = parse_answer(raw_answer)

        # Retire the current question regardless of outcome — no grace, no
        # re-submission of the same question_id (double-submit -> stale).
        self._current = None

        if answer is None:
            # Neutral rejection: never logged to CSV, never scored.
            return {
                "expired": False,
                "result": "rejected",
                "seconds_left": round(self.seconds_left(), 3),
            }

        is_correct = check(question, answer)
        self._results.append({
            "family": question.family,
            "correct": is_correct,
            "response_time": response_time,
            "shown_terms": question.shown_terms,
            "user_answer": raw_answer.strip(),
            "correct_answer": question.answer,
        })
        storage.append_question_row(self.user, self._question_row(question, is_correct, response_time, raw_answer))

        return {
            "expired": False,
            "result": "correct" if is_correct else "wrong",
            "seconds_left": round(self.seconds_left(), 3),
        }

    def summary_poll(self) -> dict:
        """Payload for GET /api/session/summary (client polls at 0:00)."""
        if not self.is_expired():
            return {"expired": False, "seconds_left": round(self.seconds_left(), 3)}
        return {"expired": True, "summary": self.finalize(completed=1)}

    def end(self) -> dict:
        """POST /api/session/end — user aborted (Back / pagehide beacon)."""
        self.finalize(completed=0)
        return {"ended": True}

    # ---- finalize ----------------------------------------------------

    def finalize(self, completed: int = 0) -> dict:
        """Guarded by _finalized so CSV is written exactly once, regardless
        of how many routes (expiry checks, /summary poll, /session/end) end
        up calling it. The completed flag from the FIRST call wins.
        """
        if self._finalized:
            return self._final_summary

        self._finalized = True
        actual_seconds = time.perf_counter() - self._start_perf
        stats = scoring.session_stats(self._results, actual_seconds)

        misses = [
            {
                "family": r["family"],
                "terms": [str(t) for t in r["shown_terms"]],
                "user_answer": r["user_answer"],
                "correct_answer": r["correct_answer"],
            }
            for r in self._results if not r["correct"]
        ]

        summary = {
            "score_per_min": stats["net_score_per_min"],
            "accuracy": stats["accuracy"],
            "correct": stats["correct"],
            "total": stats["questions_answered"],
            "avg_response_time": stats["avg_response_time"],
            "duration_seconds": round(actual_seconds, 3),
            "misses": misses,
        }
        self._final_summary = summary

        storage.append_session_row(self.user, self._session_row(stats, actual_seconds, completed))
        return summary

    # ---- CSV row builders ----------------------------------------------

    def _question_row(self, question: Question, is_correct: bool, response_time: float, raw_answer: str) -> dict:
        return {
            "session_id": self.session_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "item_type": question.family,
            "difficulty": config.M,
            "correct": 1 if is_correct else 0,
            "response_time": round(response_time, 4),
            "shown_terms": "|".join(str(t) for t in question.shown_terms),
            "user_answer": raw_answer.strip(),
            "correct_answer": question.answer,
        }

    def _session_row(self, stats: dict, actual_seconds: float, completed: int) -> dict:
        return {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "planned_seconds": self.planned_seconds,
            "actual_seconds": round(actual_seconds, 3),
            "questions_answered": stats["questions_answered"],
            "correct": stats["correct"],
            "wrong": stats["wrong"],
            "net_score_per_min": "" if stats["net_score_per_min"] is None else stats["net_score_per_min"],
            "accuracy": "" if stats["accuracy"] is None else stats["accuracy"],
            "avg_response_time": "" if stats["avg_response_time"] is None else stats["avg_response_time"],
            "completed": completed,
        }
