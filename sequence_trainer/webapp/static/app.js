/* ==========================================================================
   Number Sequence Generator — app.js
   Vanilla JS, no build step, no external libraries. Talks to the Flask
   backend over the JSON API in the plan's "API contract" section, and to
   window.Charts (charts.js, owned by a different agent) defensively — every
   Charts.* call is wrapped so a missing/broken charts.js never breaks the
   page.
   ========================================================================== */

(function () {
  "use strict";

  /* ------------------------------------------------------------------
   * DOM references
   * ------------------------------------------------------------------ */

  const viewHomeEl = document.getElementById("view-home");
  const viewPractiseEl = document.getElementById("view-practise");
  const viewResultsEl = document.getElementById("view-results");

  const userSelectEl = document.getElementById("user-select");
  const addUserModalEl = document.getElementById("add-user-modal");
  const addUserFormEl = document.getElementById("add-user-form");
  const newUserNameEl = document.getElementById("new-user-name");
  const addUserConfirmEl = document.getElementById("add-user-confirm");
  const addUserCancelEl = document.getElementById("add-user-cancel");
  const addUserErrorEl = document.getElementById("add-user-error");

  const contribChartEl = document.getElementById("contrib-chart");
  const trendChartEl = document.getElementById("trend-chart");
  const donutChartEl = document.getElementById("donut-chart");

  const bestScoreEl = document.getElementById("best-score");
  const bestAccuracyEl = document.getElementById("best-accuracy");
  const lastScoreEl = document.getElementById("last-score");
  const lastCorrectEl = document.getElementById("last-correct");
  const lastSpeedEl = document.getElementById("last-speed");

  const durationSliderEl = document.getElementById("duration-slider");
  const durationLabelEl = document.getElementById("duration-label");
  const optiverCaptionEl = document.getElementById("optiver-caption");
  const practiseBtnEl = document.getElementById("practise-btn");

  const countdownEl = document.getElementById("countdown");
  const sequenceEl = document.getElementById("sequence");
  const answerInputEl = document.getElementById("answer-input");
  const timerEl = document.getElementById("timer");
  const backBtnEl = document.getElementById("back-btn");

  const resultsScoreEl = document.getElementById("results-score");
  const resultsDonutEl = document.getElementById("results-donut");
  const resultsCorrectEl = document.getElementById("results-correct");
  const resultsSpeedEl = document.getElementById("results-speed");
  const resultsMissesEl = document.getElementById("results-misses");
  const resultsHomeBtnEl = document.getElementById("results-home-btn");

  const flashEdgeEls = [
    document.getElementById("flash-top"),
    document.getElementById("flash-right"),
    document.getElementById("flash-bottom"),
    document.getElementById("flash-left"),
  ];

  /* ------------------------------------------------------------------
   * State
   * ------------------------------------------------------------------ */

  const state = {
    currentView: "home", // 'home' | 'practise' | 'results'
    users: [],
    selectedUser: null,
    previousUserValue: null, // used to revert the <select> when '__add__' is chosen

    sessionId: null,
    currentQuestionId: null,
    deadlineMs: null,
    timerHandle: null,
    inFlight: false, // guards against double-submitting /api/answer
  };

  /* ------------------------------------------------------------------
   * Small fetch helper — never throws; always resolves to a uniform shape
   * so callers can branch on {ok, status, data} without try/catch.
   * ------------------------------------------------------------------ */

  async function apiCall(path, options) {
    try {
      const res = await fetch(path, options);
      let data = null;
      try {
        data = await res.json();
      } catch (_parseErr) {
        data = null;
      }
      return { ok: res.ok, status: res.status, data: data };
    } catch (_networkErr) {
      return { ok: false, status: 0, data: null, networkError: true };
    }
  }

  function postJson(path, body) {
    return apiCall(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  }

  /* ------------------------------------------------------------------
   * Formatting helpers
   * ------------------------------------------------------------------ */

  function formatScore(v) {
    if (v === null || v === undefined || Number.isNaN(v)) return "—"; // —
    const sign = v > 0 ? "+" : "";
    return sign + v.toFixed(2);
  }

  function formatPercent(v) {
    if (v === null || v === undefined || Number.isNaN(v)) return "—";
    return Math.round(v * 100) + "%";
  }

  function formatSpeed(v) {
    if (v === null || v === undefined || Number.isNaN(v)) return "—";
    return v.toFixed(2) + "s";
  }

  function formatCount(a, b) {
    return (a ?? 0) + " / " + (b ?? 0);
  }

  /* ------------------------------------------------------------------
   * View switching (no router — just toggling .hidden)
   * ------------------------------------------------------------------ */

  function switchView(name) {
    state.currentView = name;
    viewHomeEl.classList.toggle("hidden", name !== "home");
    viewPractiseEl.classList.toggle("hidden", name !== "practise");
    viewResultsEl.classList.toggle("hidden", name !== "results");
    // #back-btn lives outside the view sections and is shared by practise + results.
    backBtnEl.classList.toggle("hidden", name === "home");

    if (name === "practise") {
      focusAnswerInput();
      autoscaleSequence();
    }
  }

  async function goHome() {
    switchView("home");
    await loadStats();
  }

  /* ------------------------------------------------------------------
   * Charts bridge — defensive wrapper around window.Charts
   * ------------------------------------------------------------------ */

  function safeChart(fn) {
    if (!window.Charts) return;
    try {
      fn();
    } catch (err) {
      // charts.js is owned by another agent; never let it break the page.
      console.error("[charts]", err);
    }
  }

  /* ------------------------------------------------------------------
   * User picker
   * ------------------------------------------------------------------ */

  function populateUserSelect(selectValue) {
    userSelectEl.innerHTML = "";
    state.users.forEach(function (name) {
      const opt = document.createElement("option");
      opt.value = name;
      opt.textContent = name;
      userSelectEl.appendChild(opt);
    });
    const addOpt = document.createElement("option");
    addOpt.value = "__add__";
    addOpt.textContent = "➕ Add User…"; // ➕ Add User…
    userSelectEl.appendChild(addOpt);

    if (selectValue && state.users.includes(selectValue)) {
      userSelectEl.value = selectValue;
    }
  }

  async function initUserPicker() {
    const res = await apiCall("/api/users");
    state.users = res.ok && res.data && Array.isArray(res.data.users) ? res.data.users : [];

    populateUserSelect();

    const stored = localStorage.getItem("nsg_user");
    const fallback = state.users.length > 0 ? state.users[0] : null;
    const selected = stored && state.users.includes(stored) ? stored : fallback;

    state.selectedUser = selected;
    state.previousUserValue = selected;
    if (selected) {
      userSelectEl.value = selected;
      localStorage.setItem("nsg_user", selected);
    }

    userSelectEl.addEventListener("change", onUserSelectChange);
  }

  function onUserSelectChange() {
    const val = userSelectEl.value;
    if (val === "__add__") {
      // revert the dropdown to whatever was selected before opening the modal
      userSelectEl.value = state.previousUserValue || "";
      openAddUserModal();
      return;
    }
    state.selectedUser = val;
    state.previousUserValue = val;
    localStorage.setItem("nsg_user", val);
    loadStats();
  }

  function openAddUserModal() {
    hideAddUserError();
    newUserNameEl.value = "";
    addUserModalEl.showModal();
    newUserNameEl.focus();
  }

  function showAddUserError(msg) {
    addUserErrorEl.textContent = msg;
    addUserErrorEl.classList.remove("hidden");
  }

  function hideAddUserError() {
    addUserErrorEl.textContent = "";
    addUserErrorEl.classList.add("hidden");
  }

  async function handleAddUserConfirm() {
    const name = newUserNameEl.value.trim();
    if (!name) {
      showAddUserError("Please enter a name.");
      return;
    }
    const res = await postJson("/api/users", { name: name });

    if (res.ok && res.data && Array.isArray(res.data.users)) {
      state.users = res.data.users;
      populateUserSelect(name);
      state.selectedUser = name;
      state.previousUserValue = name;
      localStorage.setItem("nsg_user", name);
      hideAddUserError();
      addUserModalEl.close();
      loadStats();
      return;
    }

    if (res.status === 409) {
      const msg = (res.data && res.data.error) || "That name is already taken.";
      showAddUserError(msg);
      return;
    }

    showAddUserError("Couldn't add that user. Please try again.");
  }

  function wireUserModalEvents() {
    addUserConfirmEl.addEventListener("click", handleAddUserConfirm);
    addUserCancelEl.addEventListener("click", function () {
      addUserModalEl.close();
    });
    // Enter inside the name field submits, since both buttons are type="button"
    // (kept that way so a stray Enter can't trigger native <dialog method="dialog">
    // auto-close before we've validated against the server).
    newUserNameEl.addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        e.preventDefault();
        handleAddUserConfirm();
      }
    });
    // Prevent the form's default "dialog" submit behaviour (would close without
    // our validation running) if anything else triggers a submit.
    addUserFormEl.addEventListener("submit", function (e) {
      e.preventDefault();
    });
    // Escape key fires a native 'cancel' event on <dialog> and closes it with no
    // side effects — nothing extra to do here, that's the desired behaviour.
  }

  /* ------------------------------------------------------------------
   * Home stats
   * ------------------------------------------------------------------ */

  function emptyStats() {
    return { best: null, contribution: [], speed_trend: [], last_session: null };
  }

  async function loadStats() {
    if (!state.selectedUser) {
      renderHomeStats(emptyStats());
      return;
    }
    const res = await apiCall("/api/stats?user=" + encodeURIComponent(state.selectedUser));
    if (!res.ok || !res.data) {
      renderHomeStats(emptyStats());
      return;
    }
    renderHomeStats(res.data);
  }

  function renderHomeStats(stats) {
    const last = stats.last_session || null;
    const best = stats.best || null;

    bestScoreEl.textContent = best ? formatScore(best.score) : "No sessions yet";
    bestAccuracyEl.textContent = best ? formatPercent(best.accuracy) : "—";

    if (!last) {
      lastScoreEl.textContent = "No sessions yet";
      lastCorrectEl.textContent = "0 / 0";
      lastSpeedEl.textContent = "—";
    } else {
      lastScoreEl.textContent = formatScore(last.score_per_min);
      lastCorrectEl.textContent = formatCount(last.correct, last.total);
      lastSpeedEl.textContent = formatSpeed(last.avg_response_time);
    }

    safeChart(function () {
      window.Charts.contribution(contribChartEl, stats.contribution || []);
    });
    safeChart(function () {
      window.Charts.line(trendChartEl, stats.speed_trend || []);
    });
    const pct = last ? last.accuracy : null;
    safeChart(function () {
      window.Charts.donut(donutChartEl, { pct: pct, centerLabel: formatPercent(pct) });
    });
  }

  /* ------------------------------------------------------------------
   * Duration slider
   * ------------------------------------------------------------------ */

  function updateDurationLabel() {
    const v = parseInt(durationSliderEl.value, 10);
    durationLabelEl.textContent = v + " minutes";
    optiverCaptionEl.classList.toggle("hidden", v !== 25);
  }

  function initSlider() {
    durationSliderEl.value = "10";
    updateDurationLabel();
    durationSliderEl.addEventListener("input", updateDurationLabel);
  }

  /* ------------------------------------------------------------------
   * Practise flow: countdown -> session/start -> timer + askNext loop
   * ------------------------------------------------------------------ */

  function runCountdown() {
    return new Promise(function (resolve) {
      countdownEl.classList.remove("hidden");
      let n = 3;
      countdownEl.textContent = String(n);
      const iv = setInterval(function () {
        n -= 1;
        if (n <= 0) {
          clearInterval(iv);
          countdownEl.classList.add("hidden");
          resolve();
        } else {
          countdownEl.textContent = String(n);
        }
      }, 1000);
    });
  }

  async function startPractiseFlow() {
    switchView("practise");
    answerInputEl.value = "";
    timerEl.textContent = "0:00";
    sequenceEl.textContent = "";

    await runCountdown();

    // If the user hit Back during the countdown, bail out quietly.
    if (state.currentView !== "practise") return;

    const minutes = parseInt(durationSliderEl.value, 10);
    const res = await postJson("/api/session/start", { minutes: minutes, user: state.selectedUser });

    if (!res.ok || !res.data || !res.data.session_id) {
      // Backend unreachable / rejected the request — fail gracefully back to home
      // rather than stranding the user on a dead practise screen.
      await goHome();
      return;
    }

    state.sessionId = res.data.session_id;
    syncDeadline(res.data.seconds_left);
    startTimerLoop();
    focusAnswerInput();
    askNext();
  }

  /* ------------------------------------------------------------------
   * Timer — server is the authority; every response with seconds_left
   * re-syncs the local deadline.
   * ------------------------------------------------------------------ */

  function syncDeadline(secondsLeft) {
    if (typeof secondsLeft !== "number") return;
    state.deadlineMs = performance.now() + secondsLeft * 1000;
  }

  function startTimerLoop() {
    stopTimerLoop();
    renderTimer();
    state.timerHandle = setInterval(tickTimer, 250);
  }

  function stopTimerLoop() {
    if (state.timerHandle) {
      clearInterval(state.timerHandle);
      state.timerHandle = null;
    }
  }

  function renderTimer() {
    if (state.deadlineMs === null) return;
    const remainingMs = Math.max(0, state.deadlineMs - performance.now());
    const totalSeconds = Math.ceil(remainingMs / 1000);
    const mm = Math.floor(totalSeconds / 60);
    const ss = totalSeconds % 60;
    timerEl.textContent = mm + ":" + String(ss).padStart(2, "0");
  }

  function tickTimer() {
    renderTimer();
    if (state.deadlineMs !== null && performance.now() >= state.deadlineMs) {
      stopTimerLoop();
      pollSummaryAtExpiry();
    }
  }

  async function pollSummaryAtExpiry() {
    if (!state.sessionId) return;
    const res = await apiCall("/api/session/summary?session_id=" + encodeURIComponent(state.sessionId));
    if (!res.ok || !res.data) {
      // transient network error at exactly 0:00 — retry shortly
      state.timerHandle = setTimeout(pollSummaryAtExpiry, 500);
      return;
    }
    if (res.data.expired) {
      showResults(res.data.summary);
    } else {
      // server disagrees about expiry (clock drift) — resume
      syncDeadline(res.data.seconds_left);
      startTimerLoop();
    }
  }

  /* ------------------------------------------------------------------
   * Question loop
   * ------------------------------------------------------------------ */

  async function askNext() {
    if (!state.sessionId) return;
    const res = await apiCall("/api/question?session_id=" + encodeURIComponent(state.sessionId));
    if (!res.ok || !res.data) return; // transient failure; user's next Enter or the timer will recover

    if (res.data.expired) {
      stopTimerLoop();
      showResults(res.data.summary);
      return;
    }

    state.currentQuestionId = res.data.question_id;
    syncDeadline(res.data.seconds_left);
    renderSequence(res.data.terms || []);
    answerInputEl.value = "";
    focusAnswerInput();
  }

  /* ------------------------------------------------------------------
   * Sequence rendering + one-shot font autoscale
   * ------------------------------------------------------------------ */

  const SEQUENCE_FONT_MAX = 72;
  const SEQUENCE_FONT_MIN = 16;

  function renderSequence(terms) {
    sequenceEl.textContent = terms.join(", ") + ", _";
    autoscaleSequence();
  }

  function autoscaleSequence() {
    if (!sequenceEl.textContent) return;
    const container = sequenceEl.parentElement; // .sequence-wrap
    if (!container) return;

    sequenceEl.style.fontSize = SEQUENCE_FONT_MAX + "px";
    const boxWidth = container.clientWidth;
    const scrollWidth = sequenceEl.scrollWidth || 1;

    // One measurement + one linear correction — no iterative reflow loop needed
    // for a single nowrap line.
    let size = SEQUENCE_FONT_MAX * ((0.92 * boxWidth) / scrollWidth);
    size = Math.min(SEQUENCE_FONT_MAX, Math.max(SEQUENCE_FONT_MIN, size));
    sequenceEl.style.fontSize = size + "px";
  }

  window.addEventListener("resize", function () {
    if (state.currentView === "practise") autoscaleSequence();
  });

  /* ------------------------------------------------------------------
   * Input handling — real, visible, centred <input> so native caret /
   * backspace / IME all work. Kept focused aggressively during practise.
   * ------------------------------------------------------------------ */

  function focusAnswerInput() {
    if (state.currentView === "practise") answerInputEl.focus();
  }

  function wireAnswerInputEvents() {
    // Filter insertion to digits and minus only; deletions (e.data === null)
    // always pass through untouched.
    answerInputEl.addEventListener("beforeinput", function (e) {
      if (e.data == null) return;
      if (!/^[0-9-]*$/.test(e.data)) {
        e.preventDefault();
      }
    });

    answerInputEl.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.isComposing) {
        e.preventDefault();
        handleEnter();
      }
    });

    // Refocus immediately on blur while still in the practise view, unless the
    // user is deliberately moving focus to the Back button.
    answerInputEl.addEventListener("blur", function (e) {
      if (state.currentView !== "practise") return;
      if (e.relatedTarget === backBtnEl) return;
      setTimeout(function () {
        if (state.currentView === "practise") answerInputEl.focus();
      }, 0);
    });

    // Refocus whenever a relevant key is pressed anywhere else on the page.
    document.addEventListener("keydown", function (e) {
      if (state.currentView !== "practise") return;
      if (document.activeElement === answerInputEl) return;
      if (/^[0-9]$/.test(e.key) || e.key === "-" || e.key === "Backspace") {
        focusAnswerInput();
      }
    });

    answerInputEl.addEventListener("animationend", function (e) {
      if (e.animationName === "shake") answerInputEl.classList.remove("shake");
    });
  }

  function triggerShake() {
    answerInputEl.classList.remove("shake");
    void answerInputEl.offsetWidth; // force reflow so a repeated shake restarts
    answerInputEl.classList.add("shake");
  }

  async function handleEnter() {
    if (state.inFlight) return;

    const raw = answerInputEl.value.trim();

    // Hard "no skipping" rule: empty Enter is a total no-op.
    if (raw === "") return;

    if (!/^-?\d+$/.test(raw)) {
      triggerShake();
      answerInputEl.value = "";
      focusAnswerInput();
      return;
    }

    if (!state.sessionId || state.currentQuestionId === null || state.currentQuestionId === undefined) {
      return;
    }

    state.inFlight = true;
    const res = await postJson("/api/answer", {
      session_id: state.sessionId,
      question_id: state.currentQuestionId,
      answer: raw,
    });
    state.inFlight = false;

    if (res.status === 409) {
      // stale/double-submit — move on to whatever question is actually current
      answerInputEl.value = "";
      askNext();
      return;
    }

    if (!res.ok || !res.data) {
      answerInputEl.value = "";
      focusAnswerInput();
      return;
    }

    if (res.data.expired) {
      stopTimerLoop();
      answerInputEl.value = "";
      showResults(res.data.summary);
      return;
    }

    syncDeadline(res.data.seconds_left);

    if (res.data.result === "correct") {
      triggerFlash("correct");
    } else if (res.data.result === "wrong") {
      triggerFlash("wrong");
    }
    // result === "rejected" (server-side regex backstop) is treated as neutral:
    // no flash, just move on — the client already validated the format above,
    // so this should be rare.

    answerInputEl.value = "";
    askNext(); // don't wait for the flash animation to finish
  }

  /* ------------------------------------------------------------------
   * Edge flash
   * ------------------------------------------------------------------ */

  // Reads --flash-duration straight from CSS so JS never hardcodes a duration of
  // its own — editing the single constant in style.css is enough to change both
  // the visual fade and this cleanup fallback.
  function getFlashDurationMs() {
    const raw = getComputedStyle(document.body).getPropertyValue("--flash-duration").trim();
    const value = parseFloat(raw);
    if (Number.isNaN(value)) return 100;
    return raw.indexOf("ms") !== -1 ? value : value * 1000;
  }

  function triggerFlash(kind) {
    document.body.removeAttribute("data-flash");
    void document.body.offsetWidth; // forced reflow so back-to-back flashes retrigger
    document.body.setAttribute("data-flash", kind);
    // Belt-and-braces cleanup: animationend (below) usually clears this first, but
    // a backgrounded/throttled tab can skip animation events entirely, so also
    // clear on a plain timeout sized to the current --flash-duration.
    setTimeout(function () {
      if (document.body.getAttribute("data-flash") === kind) {
        document.body.removeAttribute("data-flash");
      }
    }, getFlashDurationMs() + 30);
  }

  function wireFlashCleanup() {
    // All four edges share the same animation-duration; listening on one is enough.
    const el = flashEdgeEls[0];
    if (!el) return;
    el.addEventListener("animationend", function () {
      document.body.removeAttribute("data-flash");
    });
  }

  /* ------------------------------------------------------------------
   * Results view
   * ------------------------------------------------------------------ */

  function showResults(summary) {
    state.sessionId = null;
    state.currentQuestionId = null;
    stopTimerLoop();
    switchView("results");
    renderResults(summary || {});
  }

  function renderResults(summary) {
    resultsScoreEl.textContent = formatScore(summary.score_per_min);
    resultsCorrectEl.textContent = formatCount(summary.correct, summary.total);
    resultsSpeedEl.textContent = formatSpeed(summary.avg_response_time);

    const pct = summary.accuracy === undefined ? null : summary.accuracy;
    safeChart(function () {
      // charts.js owns the colour thresholds; we just pass the raw accuracy value.
      window.Charts.donut(resultsDonutEl, { pct: pct, centerLabel: formatPercent(pct) });
    });

    renderMisses(summary.misses || []);
  }

  function renderMisses(misses) {
    resultsMissesEl.innerHTML = "";

    if (!misses || misses.length === 0) {
      const li = document.createElement("li");
      li.className = "misses-empty";
      li.textContent = "No misses — clean sheet.";
      resultsMissesEl.appendChild(li);
      return;
    }

    misses.forEach(function (m) {
      const li = document.createElement("li");
      li.className = "miss-row";

      const seq = document.createElement("span");
      seq.className = "miss-row__seq";
      seq.textContent = (m.terms || []).join(", ") + ", _";

      const you = document.createElement("span");
      you.className = "miss-row__you";
      you.textContent = "you: " + m.user_answer;

      const ans = document.createElement("span");
      ans.className = "miss-row__answer";
      ans.textContent = "answer: " + m.correct_answer;

      const fam = document.createElement("span");
      fam.className = "miss-row__family";
      fam.textContent = m.family || "";

      li.appendChild(seq);
      li.appendChild(you);
      li.appendChild(ans);
      li.appendChild(fam);
      resultsMissesEl.appendChild(li);
    });
  }

  /* ------------------------------------------------------------------
   * Back button (shared by practise + results) and pagehide beacon
   * ------------------------------------------------------------------ */

  async function handleBack() {
    if (state.currentView === "practise") {
      const sid = state.sessionId;
      stopTimerLoop();
      state.sessionId = null;
      state.currentQuestionId = null;
      if (sid) {
        await postJson("/api/session/end", { session_id: sid });
      }
      await goHome();
    } else if (state.currentView === "results") {
      await goHome();
    }
  }

  function wirePagehideBeacon() {
    window.addEventListener("pagehide", function () {
      if (state.sessionId && state.currentView === "practise" && navigator.sendBeacon) {
        const payload = JSON.stringify({ session_id: state.sessionId });
        navigator.sendBeacon("/api/session/end", new Blob([payload], { type: "application/json" }));
      }
    });
  }

  /* ------------------------------------------------------------------
   * Bootstrap
   * ------------------------------------------------------------------ */

  function wireStaticEvents() {
    practiseBtnEl.addEventListener("click", startPractiseFlow);
    backBtnEl.addEventListener("click", handleBack);
    resultsHomeBtnEl.addEventListener("click", goHome);
    wireUserModalEvents();
    wireAnswerInputEvents();
    wireFlashCleanup();
    wirePagehideBeacon();
  }

  async function init() {
    initSlider();
    wireStaticEvents();
    await initUserPicker();
    await loadStats();
    switchView("home");
  }

  init();
})();
