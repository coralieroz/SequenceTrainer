"""Pure sequence generators — transplanted from Number-Sequence Generator.py.

No I/O anywhere in this module (no print/input/files). Each function takes a
length `m` and returns a plain `list[int]` of length `m`; the caller (see
questions.py) decides which terms to show and which to hide.

Fixes carried over from the source script (see plan's "Python transplant
map"):
  - geometric(): now ALL-INTEGER for every ratio, including the "half" ratio
    (built by exact //2 halving instead of float division) and a capped
    starting value for r=3 so the 9th term doesn't explode.
  - mixed(): the multiplication step now excludes 0 (which collapsed the
    sequence to a repeating value) and +/-1 (which killed the "two-rule
    trap" the family is meant to teach), while also avoiding the
    magnitude blow-up of +/-4 or +/-5 repeated across 9 terms.
"""

import random


def arithmetic(m):
    """an = a0 + n*d — verbatim from the source script."""
    a0 = random.randint(-20, 50)
    d = random.randint(-12, 12)
    while d == 0:
        d = random.randint(-12, 12)
    sequence = [a0]
    for i in range(m - 1):
        sequence.append(sequence[i] + d)
    return sequence


def geometric(m):
    """an = a0 * r^n — all-integer for every ratio choice.

    r in {2, 3, "half", -2}.
      - r == "half": a0 = randint(1,12) * 2**(m-1), then built by repeated
        exact //2 halving so every term (including the last) stays a whole
        number — no floats anywhere.
      - r == 3: a0 = randint(1,4), capping the 9th term (a0 * 3**8) at
        4 * 6561 = 26244 instead of exploding to 78732+.
      - r in {2, -2}: a0 = randint(1,12), as in the source script (these
        ratios don't need extra capping at m=9).
    """
    r = random.choice([2, 3, "half", -2])

    if r == "half":
        a0 = random.randint(1, 12) * 2 ** (m - 1)
        sequence = [a0]
        for _ in range(m - 1):
            sequence.append(sequence[-1] // 2)
        return sequence

    a0 = random.randint(1, 4) if r == 3 else random.randint(1, 12)
    sequence = [a0 * r ** i for i in range(m)]
    return sequence


def quadratic(m):
    """an = A*n^2 + B*n + C — verbatim from the source script."""
    A = random.randint(1, 4)
    B = random.randint(-5, 5)
    C = random.randint(-5, 10)
    sequence = [A * i * i + B * i + C for i in range(m)]
    return sequence


def fibonacci(m):
    """an = k*a(n-1) + a(n-2) — verbatim, plus a contract guard.

    interleaved() calls this with short lengths ((m+i)//2), so the m>=2
    contract that was implicit in the source script is made explicit here.
    """
    assert m >= 2, "fibonacci(m) needs at least 2 terms to seed the recurrence"
    a0 = random.randint(1, 8)
    a1 = random.randint(1, 8)
    k = random.choice([-1, 1, 2, 3])
    sequence = [a0, a1]
    for i in range(m - 2):
        sequence.append(k * sequence[i + 1] + sequence[i])
    return sequence


def interleaved(m):
    """Two independent strands (each one of the four base families) woven
    together, e.g. 2,3,7,6,12,17,24. Verbatim decider logic from the source
    script, including its edge-case quirk: random.random() is a continuous
    draw, so `decider == 0.9` exactly is a probability-zero event, but as
    written it falls through to the `else` (fibonacci) branch because
    neither the geometric branch (`< 0.9`) nor the quadratic branch
    (`> 0.9`) catches it. Left as-is rather than "fixed" per the plan.
    """
    i = 0
    strands = []
    while i < 2:
        decider = random.random()
        length = (m + i) // 2
        if decider < 0.45:
            seq = arithmetic(length)
        elif decider >= 0.45 and decider < 0.9:
            seq = geometric(length)
        elif decider > 0.9 and decider <= 0.95:
            seq = quadratic(length)
        else:
            seq = fibonacci(length)
        strands.append(seq)
        i += 1

    result = []
    for j in range(len(strands[1])):
        result.append(strands[1][j])
        if j < len(strands[0]):
            result.append(strands[0][j])
    return result


def mixed(m):
    """Alternating +c / *c, e.g. 1,2,5,10,13,26,29.

    Addition step: c in [-50,50], nonzero (verbatim from source script).
    Multiplication step: c drawn from {-3,-2,2,3} — excludes 0 (which
    collapses the sequence to a repeated value), +/-1 (which makes the
    multiplication step a no-op / sign-flip and kills the trap), and
    +/-4 / +/-5 (which blow up the magnitude across 9 terms).
    """
    def make_op():
        if random.random() < 0.5:
            c = random.randint(-50, 50)
            while c == 0:
                c = random.randint(-50, 50)
            return lambda x: x + c
        else:
            c = random.choice([-3, -2, 2, 3])
            return lambda x: x * c

    ops = [make_op(), make_op()]
    sequence = [random.randrange(-50, 50)]
    for i in range(m - 1):
        sequence.append(ops[i % 2](sequence[i]))
    return sequence
