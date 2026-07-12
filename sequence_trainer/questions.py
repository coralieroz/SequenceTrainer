"""Question dataclass + the six-way generator dispatch + answer parsing.

Still pure — no I/O. `make_question` reproduces the source script's
`random.randint(0,5)` six-way dispatch over the module-level loop; every
consumer downstream reads `question.shown_terms` (never a global `m`), which
kills the global-`m` bug the plan calls out in the original `user_input()`.
"""

import random
import re
from dataclasses import dataclass, field

from . import generators
from .config import M

ANSWER_RE = re.compile(r"^-?\d+$")

_FAMILIES = ("arithmetic", "geometric", "quadratic", "fibonacci", "interleaved", "mixed")
_GENERATORS = {
    "arithmetic": generators.arithmetic,
    "geometric": generators.geometric,
    "quadratic": generators.quadratic,
    "fibonacci": generators.fibonacci,
    "interleaved": generators.interleaved,
    "mixed": generators.mixed,
}


@dataclass
class Question:
    family: str
    shown_terms: list = field(default_factory=list)
    answer: int = 0


def make_question(m: int = M) -> Question:
    """Reproduces the source script's `decider = random.randint(0, 5)` dispatch:
    0=arithmetic 1=geometric 2=quadratic 3=fibonacci 4=interleaved 5=mixed
    (equal-weight, six-way). Returns a Question with the last term hidden as
    the answer and the first m-1 terms as shown_terms.
    """
    decider = random.randint(0, 5)
    family = _FAMILIES[decider]
    sequence = _GENERATORS[family](m)
    return Question(family=family, shown_terms=sequence[:-1], answer=sequence[-1])


def parse_answer(raw: str):
    """strip + `^-?\\d+$` + int() — exact-int parsing. Returns None (neutral
    rejection) for empty/blank input, non-numeric text, or malformed signs
    like "-" or "3.5". This REPLACES the old `float(ans) == seq[-1]` float
    equality in the source script's user_input().
    """
    text = (raw or "").strip()
    if not ANSWER_RE.match(text):
        return None
    return int(text)


def check(question: Question, answer: int) -> bool:
    """Exact int equality — no float tolerance anywhere."""
    return answer == question.answer
