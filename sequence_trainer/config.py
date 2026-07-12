"""Static configuration for the sequence trainer.

Kept deliberately tiny: sequence length, and where on disk user data lives.
No game rules here — see generators.py / questions.py / session.py.
"""

from pathlib import Path

# Length of every generated sequence (m-1 terms shown, 1 hidden as the answer).
# m=7: interleaved() is restricted to arithmetic/geometric strands (see
# generators.py), both unambiguous at the 3-4 terms a strand shows at this
# length, so the longer m=9 the source script needed for quadratic/fibonacci
# strands is no longer necessary.
M = 7

# Root package directory (…/sequence_trainer)
PACKAGE_DIR = Path(__file__).resolve().parent

# Runtime data directory: sequence_trainer/data/
DATA_DIR = PACKAGE_DIR / "data"

# Registry file: sequence_trainer/data/users.json
USERS_FILE = DATA_DIR / "users.json"

# Default user created on first run.
DEFAULT_USER = "Cora"

# Practise session duration bounds (minutes), server clamps to this range.
MIN_SESSION_MINUTES = 2
MAX_SESSION_MINUTES = 25
