"""Plain-assert sanity tests. Run with:  py -m sequence_trainer.tests

Deliberately dependency-free (no pytest) so the plan's Verification step
needs nothing beyond `pip install -r requirements.txt`.

Covers:
  - each generator's family property over ~200 seeded runs
  - parse_answer() / check()
  - a simulated short-duration Session that expires and finalizes exactly
    once, producing a 0-question summary with null fields, without raising.
"""

import random
import time
import traceback

from . import generators, session as session_module, storage
from .config import M
from .questions import Question, check, parse_answer

N_TRIALS = 200


# ---------------------------------------------------------------------------
# Generator family-property helpers (also reused permissively by the
# interleaved test, which doesn't know in advance which family each of its
# two strands came from).
# ---------------------------------------------------------------------------

def _is_arithmetic(seq):
    if len(seq) < 2:
        return False
    diffs = {seq[i + 1] - seq[i] for i in range(len(seq) - 1)}
    return len(diffs) == 1 and next(iter(diffs)) != 0


def _is_geometric(seq):
    if len(seq) < 2 or any(v == 0 for v in seq[:-1]):
        return False
    a0, a1 = seq[0], seq[1]
    if a1 == a0 * 2:
        r = 2
    elif a1 == a0 * 3:
        r = 3
    elif a1 == a0 * -2:
        r = -2
    elif a1 * 2 == a0:
        r = "half"
    else:
        return False
    if r == "half":
        return all(seq[i] % 2 == 0 and seq[i + 1] == seq[i] // 2 for i in range(len(seq) - 1))
    return all(seq[i + 1] == seq[i] * r for i in range(len(seq) - 1))


def _is_quadratic(seq):
    if len(seq) < 3:
        return False
    first = [seq[i + 1] - seq[i] for i in range(len(seq) - 1)]
    second = {first[i + 1] - first[i] for i in range(len(first) - 1)}
    return len(second) == 1


def _is_fibonacci(seq):
    if len(seq) < 3:
        return False
    a0, a1 = seq[0], seq[1]
    if a1 == 0:
        return False
    num = seq[2] - a0
    if num % a1 != 0:
        return False
    k = num // a1
    return all(seq[i + 2] == k * seq[i + 1] + seq[i] for i in range(len(seq) - 2))


def _infer_op(pairs):
    """For a fixed sequence of (x, y) pairs all produced by the SAME
    operation, decide whether that operation was "add c" or "mul c" and
    return (kind, c), or None if inconsistent.
    """
    deltas = {y - x for x, y in pairs}
    if len(deltas) == 1:
        return ("add", next(iter(deltas)))
    ratios = set()
    for x, y in pairs:
        if x == 0:
            if y != 0:
                return None
            continue
        if y % x != 0:
            return None
        ratios.add(y // x)
    if len(ratios) == 1:
        return ("mul", ratios.pop())
    return None


# ---------------------------------------------------------------------------
# Generator tests
# ---------------------------------------------------------------------------

def test_arithmetic():
    for seed in range(N_TRIALS):
        random.seed(seed)
        seq = generators.arithmetic(M)
        assert len(seq) == M
        assert all(isinstance(v, int) for v in seq)
        assert _is_arithmetic(seq), f"arithmetic property failed: {seq}"
    print("arithmetic: OK")


def test_geometric():
    for seed in range(N_TRIALS):
        random.seed(seed)
        seq = generators.geometric(M)
        assert len(seq) == M
        assert all(isinstance(v, int) for v in seq), f"geometric produced non-int: {seq}"
        assert _is_geometric(seq), f"geometric property failed: {seq}"

        a0, a1 = seq[0], seq[1]
        if a1 == a0 * 3:  # r == 3 branch: a0 capped at randint(1, 4)
            assert 1 <= abs(a0) <= 4, f"r=3 a0 should be capped at 1..4: {seq}"
            assert abs(seq[-1]) <= 4 * 3 ** (M - 1), f"r=3 last term exceeds documented cap: {seq}"
    print("geometric: OK")


def test_quadratic():
    for seed in range(N_TRIALS):
        random.seed(seed)
        seq = generators.quadratic(M)
        assert len(seq) == M
        assert all(isinstance(v, int) for v in seq)
        assert _is_quadratic(seq), f"quadratic second-difference not constant: {seq}"
        first = [seq[i + 1] - seq[i] for i in range(len(seq) - 1)]
        second_diff = first[1] - first[0]
        assert second_diff % 2 == 0, f"second diff should equal 2A (even): {second_diff}"
    print("quadratic: OK")


def test_fibonacci():
    for seed in range(N_TRIALS):
        random.seed(seed)
        seq = generators.fibonacci(M)
        assert len(seq) == M
        assert all(isinstance(v, int) for v in seq)
        assert _is_fibonacci(seq), f"fibonacci recurrence violated: {seq}"


def test_fibonacci_guard():
    raised = False
    try:
        generators.fibonacci(1)
    except AssertionError:
        raised = True
    assert raised, "fibonacci(m) should assert m >= 2"
    print("fibonacci + guard: OK")


def test_interleaved():
    for seed in range(N_TRIALS):
        random.seed(seed)
        seq = generators.interleaved(M)
        assert len(seq) == M, f"interleaved length != {M}: {seq}"
        assert all(isinstance(v, int) for v in seq)

        # Per interleaved()'s weave: strand for i=1 (length (M+1)//2) sits at
        # even result indices, strand for i=0 (length (M+0)//2) at odd ones.
        strand1 = seq[0::2]
        strand0 = seq[1::2]
        for strand in (strand0, strand1):
            recognised = (
                _is_arithmetic(strand) or _is_geometric(strand)
                or _is_quadratic(strand) or _is_fibonacci(strand)
            )
            assert recognised, f"interleaved strand matches no known family: {strand} (full={seq})"
    print("interleaved: OK")


def test_mixed():
    for seed in range(N_TRIALS):
        random.seed(seed)
        seq = generators.mixed(M)
        assert len(seq) == M
        assert all(isinstance(v, int) for v in seq)
        # Worst case: |start| up to 49, all 8 steps multiplying by 3 -> 49*3**8
        # = 321,489. Generous headroom above that, well below the old +/-4/+/-5
        # regime this bound is meant to rule out.
        assert all(abs(v) < 500_000 for v in seq), f"mixed sequence magnitude exploded: {seq}"

        slot0 = [(seq[i], seq[i + 1]) for i in range(0, M - 1, 2)]
        slot1 = [(seq[i], seq[i + 1]) for i in range(1, M - 1, 2)]
        for slot in (slot0, slot1):
            if all(x == 0 and y == 0 for x, y in slot):
                # Degenerate case: the *starting value* (random.randrange(-50,50),
                # left verbatim per the plan) happened to be 0, and this slot's
                # op happened to be multiplicative -> 0*c stays 0 for any c, so
                # the multiplier can't be recovered from the output. This is not
                # the "multiplier==0" collapse bug the plan fixed (that bug was
                # the multiplier itself being drawable as 0); nothing to check.
                continue
            op = _infer_op(slot)
            assert op is not None, f"could not infer a consistent op for {slot} (seq={seq})"
            kind, c = op
            assert c != 0, f"op constant must never be 0: {seq}"
            if kind == "mul":
                assert c not in (1, -1), f"multiplier must exclude +/-1: {seq}"
                assert abs(c) in (2, 3), f"multiplier out of expected {{2,3}} set: {c} in {seq}"
    print("mixed: OK")


# ---------------------------------------------------------------------------
# questions.py tests
# ---------------------------------------------------------------------------

def test_parse_answer():
    assert parse_answer("-42") == -42
    assert parse_answer(" 17 ") == 17
    assert parse_answer("0") == 0
    assert parse_answer("") is None
    assert parse_answer("   ") is None
    assert parse_answer("3.5") is None
    assert parse_answer("abc") is None
    assert parse_answer("-") is None
    assert parse_answer("--5") is None
    assert parse_answer("5-") is None
    assert parse_answer(None) is None
    print("parse_answer: OK")


def test_check():
    q = Question(family="arithmetic", shown_terms=[1, 2, 3], answer=4)
    assert check(q, 4) is True
    assert check(q, 5) is False
    assert check(q, -4) is False
    print("check: OK")


# ---------------------------------------------------------------------------
# session.py: expiry + finalize-once, without waiting for a real deadline
# ---------------------------------------------------------------------------

def test_session_expiry_finalizes_once():
    calls = {"session": 0, "question": 0}
    orig_session_row = storage.append_session_row
    orig_question_row = storage.append_question_row

    def fake_session_row(user, row):
        calls["session"] += 1

    def fake_question_row(user, row):
        calls["question"] += 1

    storage.append_session_row = fake_session_row
    storage.append_question_row = fake_question_row
    try:
        s = session_module.Session(user="__test_user__", minutes=2)
        # Force immediate expiry rather than waiting out a real deadline.
        s._deadline = time.perf_counter() - 0.01

        result1 = s.next_question()
        assert result1["expired"] is True
        summary1 = result1["summary"]
        assert summary1["total"] == 0
        assert summary1["correct"] == 0
        assert summary1["score_per_min"] is None
        assert summary1["accuracy"] is None
        assert summary1["avg_response_time"] is None
        assert summary1["misses"] == []

        # Re-entering through other routes must not re-finalize / re-write.
        result2 = s.summary_poll()
        assert result2["expired"] is True
        assert result2["summary"] is summary1

        end_result = s.end()
        assert end_result == {"ended": True}

        assert calls["session"] == 1, f"sessions.csv should be written exactly once, got {calls['session']}"
        assert calls["question"] == 0, "0-question session should log no questions.csv rows"
    finally:
        storage.append_session_row = orig_session_row
        storage.append_question_row = orig_question_row
    print("session expiry / finalize-once: OK")


# ---------------------------------------------------------------------------

def main():
    tests = [
        test_arithmetic,
        test_geometric,
        test_quadratic,
        test_fibonacci,
        test_fibonacci_guard,
        test_interleaved,
        test_mixed,
        test_parse_answer,
        test_check,
        test_session_expiry_finalizes_once,
    ]
    failures = []
    for t in tests:
        try:
            t()
        except Exception:
            print(f"FAILED: {t.__name__}")
            traceback.print_exc()
            failures.append(t.__name__)

    if failures:
        print(f"\n{len(failures)} test(s) FAILED: {failures}")
        raise SystemExit(1)
    print("\nALL TESTS PASSED")


if __name__ == "__main__":
    main()
