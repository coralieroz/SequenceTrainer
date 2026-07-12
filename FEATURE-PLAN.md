# Plan: Number-Sequence Trainer — from single-file terminal script to Flask web game

## 0. The one architectural idea everything hangs on

The current file mixes three jobs in one place: `user_input()` **generates the display string, reads the keyboard, checks the answer, and draws the result** — four responsibilities in eleven lines. The whole roadmap is one move, applied repeatedly:

| Layer | Job | Talks to |
|---|---|---|
| **Game logic** (pure) | make sequences, know the right answer, check a candidate answer, compute stats | nothing — no `print`, no `input()`, no files |
| **Session / harness** | run one session: hand out questions, time them, collect results, know when the session is over | game logic + storage |
| **Interface** | show a question, get an answer, show feedback | session layer only |

*Why:* the terminal and the browser are just two different interfaces. If the session layer exposes plain methods (`next_question()`, `submit_answer()`, `is_over()`, `report()`) and never prints, then the Flask version is ~150 new lines of routes and HTML calling the **same** session object — not a rewrite. Every design choice below is judged by "does game logic stay I/O-free?"

## 1. Proposed file layout

Keep it flat and boring — this is a learning project, not a framework.

```
sequence_trainer/               <- new folder (fixes the space-in-filename problem)
    generators.py       arithmetic(), geometric(), quadratic(), fibonacci_like(),
                        interleaved(), mixed() — each returns a list of numbers, nothing else
    questions.py        Question dataclass + make_question(family, length) + check_answer()
    scoring.py          accuracy, median time, per-family breakdown, weakest_categories()
    storage.py          append_results_csv(), load_history() — the ONLY file that touches results.csv
    session.py          Session class: countdown deadline, question dispensing, result collection
    terminal_ui.py      all print/input/ANSI/emoji code (the ✅/❌ trick lives here)
    timer_thread.py     the background countdown thread (terminal-only)
    play_terminal.py    entry point: wires session + terminal_ui together (`python play_terminal.py`)
    plots.py            matplotlib progress charts from results.csv
    webapp/             (later)
        app.py
        templates/  index.html, play.html, report.html
        static/     style.css, game.js
    results.csv         (created at runtime, one row per question, grows forever)
```

**What goes where, concretely, from the current file:**

- `arithmetic/geometric/quadratic/fibonacci/interleaved/mixed` → `generators.py`, almost verbatim.
- The *hidden-last-term* idea → `questions.py`. Define something like:

```python
@dataclass
class Question:
    family: str          # "arithmetic", "geometric", ...
    difficulty: int
    shown_terms: list    # first m-1 terms
    answer: object       # exact value (int or Fraction)

def check_answer(question, raw_text: str) -> bool: ...
```

- The `while t < N` loop → becomes `Session` in `session.py` plus a thin loop in `play_terminal.py`.
- Everything involving `print`, `input`, `\033[...`, `✅` → `terminal_ui.py` only.

## 2. Step order (with effort and pitfalls per step)

### Step 1 — Rename, restructure, and put it under git (≈30 min)
Create the `sequence_trainer` folder, split the file as above (contents mostly copy-paste for now), `git init` so every later step is a commit you can diff.

**Pitfalls specific to your code:**
1. `Number-Sequence Generator.py` can never be imported (`import Number-Sequence Generator` is a syntax error twice over — the space *and* the hyphen). Nothing works until the rename happens, which is why this is step 1.
2. The folder lives in OneDrive; OneDrive sync can lock `results.csv` mid-write later. Fine to keep, but if you ever see `PermissionError` on the CSV, that's why.
3. Resist "improving" logic while splitting. Step 1 should change *where* code lives, not *what* it does — otherwise you can't tell whether a new bug came from the move or the change.

### Step 2 — Purify the game logic (1 evening)
Make `generators.py` + `questions.py` genuinely pure, and fix the latent correctness bugs while you're in there.

**Pitfalls (all live bugs in the current file):**
1. **`user_input()` reads the global `m`**, not `len(sequence)` — `prefix` is built with `range(m-1)`. It works today only because every generator happens to return exactly `m` terms. In the refactor, the `Question` carries its own `shown_terms`; no globals. (Delete `m=7; N=10` globals entirely — they become a small `Config` or function parameters.)
2. **`float(ans) == sequence[-1]`** — float equality. With `r=1/2`, `geometric(7)` produces e.g. `3 * 0.5**6 = 0.046875`; a user typing a rounded value is marked wrong, and float arithmetic itself can bite. Two clean fixes: (a) keep everything exact with `fractions.Fraction` end-to-end, or (b) constrain generators to integers — for `r=1/2` choose `a0 = random.randint(1,12) * 2**(m-1)` so every term stays whole (the PDF explicitly says "keep terms integer-ish for mental math"). (b) is simpler and better matches the assessment style; parse the user's text with a small helper that tries `int` then `Fraction`.
3. **`mixed()` can pick `c=0`** (`random.randrange(-5,5)` includes 0), collapsing the sequence to `..., 0, 0, 0` — the answer becomes trivially guessable and the "two-rule trap" is gone. Exclude 0 (and consider excluding 1/−1 for multiplication too). Also note it can explode in magnitude with `x*±4` repeated — clamp or re-roll.
4. (Bonus) `fibonacci(m)` with `m < 2` returns 2 terms regardless — harmless at `m=7`, but `interleaved` calls it with `(m+i)//2`, so at short lengths this would silently misbehave. A one-line guard or assert documents the contract.

Also in this step: write a handful of quick sanity tests (even just `assert`s in a `tests.py`) — e.g. "arithmetic differences are constant", "quadratic second differences equal 2A". Pure functions are trivially testable; that's the payoff you should *feel* here.

### Step 3 — Session layer + terminal interface, still fixed question count (1 evening)
Build `Session` and `terminal_ui.py`, and make `play_terminal.py` reproduce today's behaviour (10 questions, ✅/❌) through the new structure. The key design decision — **made now so Flask is cheap later** — is the Session API:

```python
class Session:
    def next_question(self) -> Question | None      # None when session over
    def submit_answer(self, question, raw_text, elapsed) -> bool
    def is_over(self) -> bool
    def results(self) -> list[QuestionResult]       # for report + CSV
```

The terminal loop is then: ask session for a question → `terminal_ui.show_question()` → time with `time.perf_counter()` → `terminal_ui.read_answer()` → `session.submit_answer()` → `terminal_ui.show_mark()`. Timing belongs in the *interface* loop (the harness spec's step 2), because "time between showing and answering" is an interface concept.

**Pitfalls:**
1. **Windows terminals and the ANSI/emoji trick.** `\033[F` needs VT processing; Windows Terminal has it on, but the legacy console host doesn't (classic workaround: `os.system('')` once at startup, or `colorama`). Also `✅` is double-width in some fonts, so the `col = len(prefix)+len(ans)-1` column math can land the mark one cell off — and if stdout is cp1252, printing `✅` raises `UnicodeEncodeError`. Keep a plain-ASCII fallback (`[OK]`/`[X]`) behind a flag in `terminal_ui.py`.
2. The current prefix prints `float(sequence[i])`, so arithmetic sequences display as `3.0, 15.0, ...`. Once generators return ints (step 2), format numbers as-is; formatting is `terminal_ui`'s job, not the generator's.
3. Temptation check: if you find yourself importing `terminal_ui` inside `session.py`, stop — that's the dependency arrow pointing the wrong way, and it's exactly what would make the Flask port painful.

### Step 4 — CSV logging + end-of-session report (1 evening) — *feature 2 & the persistence half of 3*
`storage.py` appends one row per question, per the PDF harness spec plus what plotting needs:

```
session_id, timestamp, item_type, difficulty, correct, response_time
```

(`session_id` = session start time as ISO string works fine; it's what lets you group per-session later.) Use `csv.DictWriter`, append mode, write the header only if the file is new. `scoring.py` computes: overall accuracy, median response time (`statistics.median`), the same two per family, and "weakest categories" = families ranked by accuracy then median time. The terminal report shows, for each miss: the shown terms, the given answer, the correct answer, the family — and (nice PDF touch worth implementing) the *tell*: the first-differences / ratios table, so a wrong answer teaches you the attack.

**Pitfalls:**
1. Compute stats from the in-memory `QuestionResult` list, *not* by re-reading the CSV — the CSV is for history; the session already knows its own results. Mixing these up creates weird coupling.
2. `statistics.median` on an empty list raises — a 0-question session (possible once the countdown exists and you let time run out immediately) must not crash the report.
3. Store the user's raw answer text in `QuestionResult` (even though the CSV spec doesn't require it) — the miss-review report needs it, and you can't reconstruct it later.

### Step 5 — Global countdown with a background thread (1–2 evenings, the hard terminal step) — *feature 1*
Replace "N questions" with "as many as possible in T minutes", with a live ticking display. Structure:

- `Session` owns the deadline: `self.deadline = perf_counter() + duration`; `next_question()` returns `None` once past it. **The session is the authority on time** — the display thread is cosmetic. (This exact split is what carries to Flask, where JS is cosmetic and the server is the authority.)
- `timer_thread.py`: a `threading.Thread(daemon=True)` that wakes every ~0.5 s, redraws the remaining time, and sets a `threading.Event` when time is up.

**How the timer and `input()` coexist without garbling the ✅/❌ trick:**
- Share one `threading.Lock` for all stdout writes. The timer thread takes it to redraw; the mark-drawing code in `terminal_ui` takes it before its `\033[F...` dance. That serialises all *Python-side* escape sequences so they can't interleave mid-sequence.
- Draw the timer on a **reserved status line** using cursor save/restore: the timer thread writes `save-cursor → jump to status line → rewrite "⏱ 02:31" → restore-cursor`, so the user's typing position is untouched. Practical scheme: print the status line at the top of each question block and have `terminal_ui` track how many lines it has printed since, so the timer knows how far up to jump.
- Accept honestly: keystroke *echo* is done by the console, not Python, so a redraw landing between two echoed characters can cause a one-frame cursor flicker. You cannot fully eliminate that with blocking `input()` — and that's fine for an MVP.

**Ending mid-question — the Windows problem, pragmatically:** you cannot interrupt a blocking `input()` on Windows (no `SIGALRM`, no select-on-stdin). Two tiers:
- **MVP (recommended first):** *the question in progress is allowed to finish.* Main loop checks `expired_event` before dispensing each question; when the timer fires mid-question, the thread rewrites the status line to `TIME UP — finish this one` and the final answer still counts (optionally: discard it if submitted more than a few seconds past the deadline — the session, not the UI, decides).
- **Stretch (optional Step 5b):** replace `input()` with a `read_line_with_deadline()` built on `msvcrt.kbhit()`/`getwch()` — a loop reading one char at a time, handling Backspace and Enter yourself, checking the deadline every iteration. This gives true mid-question cutoff *and* removes the echo race (you control every write). It's a genuinely instructive piece of low-level code, but do it only after the MVP works.

**Pitfalls:**
1. Threads die loudly nowhere: an exception inside the timer thread just silently stops the ticking. Wrap the thread body in try/except that at minimum prints the traceback.
2. Make the thread a `daemon` **and** give it a clean stop (an `Event` it checks) — otherwise Ctrl-C or session end leaves a ghost thread redrawing over your report.
3. Use `perf_counter()` for the deadline but don't compare timestamps from *different* clocks (e.g. `time.time()` in one place, `perf_counter()` in another) — pick one for all in-session timing.
4. Don't let the timer thread touch `Session` data beyond reading the deadline / setting the Event — shared mutable state across threads is where the pain lives; keep the thread's job to "draw and signal".

### Step 6 — matplotlib progress graphs (1 evening) — *rest of feature 3*
`plots.py`, run standalone (`python plots.py`): load `results.csv` with `storage.load_history()`, group rows by `session_id` × `item_type`, and plot:
- accuracy per session over time (one line per family + overall),
- median response time per session over time (same layout),
- a per-family small-multiples grid (`plt.subplots`) is clearer than six lines tangled on one axes.

**Pitfalls:**
1. Everything read from CSV is a **string** — `'True'`, `'12.3'` — convert on load in `storage.py` (one place), not in every plot.
2. Early sessions have tiny per-family counts (1 geometric question → 0% or 100% accuracy): noisy, misleading lines. Either annotate point sizes by n, or only plot families with ≥3 items per session.
3. `plt.show()` blocks; fine standalone, but never call plotting from inside the game session — keep `plots.py` free of imports from `session`/`terminal_ui` (it depends only on `storage`).

### Step 7 — Flask web version (2–3 evenings) — *feature 4*

**Mental model first:** Flask is a program that sits waiting; the browser sends it HTTP requests; each of your *routes* is just a Python function that receives a request and returns HTML or JSON. There is no persistent "screen" — the browser shows the last thing it was given, and JavaScript in the page can quietly `fetch()` more data. The game becomes: page loads once → JS asks the server for a question → user types → JS posts the answer → server replies right/wrong → repeat.

**Minimal structure (`webapp/`):**

```
app.py
    GET  /                  start page: choose duration/difficulty, "Start" button
    POST /start             creates a Session (the existing class!), remembers it, redirects to /play
    GET  /play              serves play.html once
    GET  /api/question      JSON: {question_id, shown_terms, seconds_left}
    POST /api/answer        JSON in: {question_id, answer} → out: {correct, correct_answer, seconds_left}
    GET  /report            renders report.html from session.results() + scoring.py
templates/index.html, play.html, report.html
static/style.css            mostly-white, one centered question, big type (tradermath style)
static/game.js              fetch loop + countdown
```

**Server-side vs client-side state — the crucial split:**
- **Server-side (authoritative):** the `Session` object — deadline, questions issued, the *correct answers*, results so far. For a single-user local app, a module-level dict `active_sessions[session_id] = Session(...)` with the id in Flask's signed cookie is entirely adequate; don't reach for a database.
- **Client-side (cosmetic):** the ticking countdown (`setInterval`, 1 s, counting down from the `seconds_left` the server sent), the current question text, input focus. **Never send the answer to the browser before the user submits** — it's trivially visible in dev tools. And the server re-checks the deadline on every `/api/question` and `/api/answer`; when time's up it responds `{expired: true}` and JS redirects to `/report`. This is the same authority split as Step 5 — deliberately.
- Notice `/api/answer` returning `{expired: ...}` also solves the "interrupt input() mid-question" problem *for free* — HTTP is naturally non-blocking. This is a nice moment to appreciate why the problem was hard in the terminal and trivial here.

**Pitfalls:**
1. The tradermath feel depends on tiny UX details JS must own: auto-focus the input on each new question, submit on Enter, flash ✓/✗ for ~400 ms before loading the next question. Plan `game.js` around one `askNext()` function that the answer-handler calls again.
2. `random`/session state and Flask's auto-reloader: the dev server runs the module twice in debug mode and forgets in-memory sessions on every code save. Confusing the first time; it's normal, just restart the run through the flow.
3. Question identity: the client must echo back which question it's answering (`question_id`), and the server looks the answer up in *its* record — don't trust or resend `shown_terms` from the client.
4. Keep `app.py` thin. If you find game rules creeping into a route function, they belong in `session.py`/`questions.py` — the test is "could the terminal version use this too?"

## 3. Carry-over map (terminal → Flask)

| Module | Fate in the web version |
|---|---|
| `generators.py` | **untouched** |
| `questions.py` (Question, check_answer) | **untouched** |
| `scoring.py` | **untouched** |
| `storage.py` (CSV) | **untouched** — web sessions append to the same `results.csv`, so `plots.py` charts both |
| `plots.py` | **untouched** (still run standalone) |
| `session.py` | **reused** — same class, driven by routes instead of a while-loop; the only likely change is minor (e.g. exposing `seconds_left()`) |
| `terminal_ui.py` | **replaced** by templates + `style.css` + `game.js` |
| `timer_thread.py` | **replaced** by JS `setInterval` + server-side deadline checks (threading was the right *terminal* tool; the browser gives you an event loop for free) |
| `play_terminal.py` | **replaced** by `webapp/app.py` (both are ~thin wiring) |

If steps 2–3 are done honestly (no `print`/`input` below the interface layer), the replaced column is the *only* new work in step 7 — that's the payoff of the whole refactor, and a good self-check: any time Flask work forces you to edit `generators.py` or `questions.py`, something leaked in the earlier steps.

## 4. Suggested session-by-session order recap

1. Rename + split + git (30 min)
2. Pure game logic + bug fixes (`float` equality, global `m`, `mixed` zero-multiplier) + asserts (1 evening)
3. Session class + terminal UI, behaviour-identical (1 evening)
4. CSV logging + end-of-session report (1 evening)
5. Countdown thread, grace-period ending (1–2 evenings) — optional 5b: msvcrt char-by-char input
6. matplotlib progress charts (1 evening)
7. Flask app (2–3 evenings)

Each step leaves a working game — you're never more than one commit from something playable.
