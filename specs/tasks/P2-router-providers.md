# P2 — Router & Providers (specs 02, 04 · KRs 1.1, 1.4)

Read first: OVERVIEW.md, specs 00, 01. You own specs 02 (built — maintenance) and
04 (you build). The router is the product's brain; its acceptance tests ARE KR1.1.

## M1 — Provider smoke (h0–2)
- [ ] With keys in `.env`: one real call per provider —
      `uv run python -c "from backend.providers import registry; print(registry.chat('groq:llama-3.1-8b-instant', [{'role':'user','content':'hi'}]).tokens_out)"`
      Repeat for `anthropic:claude-opus-4-8` and `gemini:gemini-2.5-flash`.
- [ ] If the sponsor Gemini key gates models, adjust `JUDGE_MODEL` in `.env` +
      note in spec 02 (same commit).

## M2 — Classifier (h2–4) — spec 04 `classifier.py`
- [ ] Heuristic signals: char/word length; math tokens (`digits, = + × ∫ solve prove`);
      code markers (fences, `def/class/{};`); reasoning keywords (`why, explain,
      step by step, compare`); output-size hints (`essay, detailed, list all`).
- [ ] Score → tier map with two thresholds in `config.py`; ties round UP (safer).
- [ ] Unsure band → one call to trivial-tier model: "Rate difficulty 1-3. Reply
      with one digit." `max_tokens=4`; parse digit; unparseable → "moderate".
      Return its impact info so `route()` books it (D4).
- [ ] Check: 10 hand cases classify sensibly in <300 ms (heuristic path).

## M3 — Selector + quality gate (h4–7) — spec 04
- [ ] `selector.py`: wrap `carbon.greenest_zone()`; return both simulated pick and
      `BASELINE_ZONE`; label "simulated placement".
- [ ] `quality_gate.py` — **hybrid by tier (D19), two functions, not one:**
      - `check_confidence(chat_result)` — **trivial tier only.** No second model
        call. Reads `chat_result.confidence` (geometric-mean token probability,
        already populated by `registry.chat(..., logprobs=True)` on the trivial
        call). `pass = score >= config.CONFIDENCE_FLOOR`. Missing/`None`
        confidence (e.g. resolved model doesn't support logprobs) → fail, caller
        falls back to `verify()` instead — never silently skip verification.
      - `verify(query, answer)` — **moderate tier only** (hard is exempt). Judge
        prompt (rubric: correctness, completeness, instruction-following → single
        JSON `{"score": 0.0-1.0}`); strict-retry once; unparseable → fail
        (escalate direction). Judge = `config.JUDGE_MODEL`; fallback tier-plus-one
        when Gemini key absent. Return judge's own `measure()` record.
      - **Do not judge trivial-tier answers.** The whole point of D19 is that the
        judge's own footprint (`wh_per_1k_out: 0.3`) exceeds the trivial model's
        (`0.12`) — a judge call there costs more than the answer it's checking.
- [ ] Check: `check_confidence` passes a high-confidence trivial answer and fails
      a mocked low-confidence one (no judge call in either case). `verify` passes
      a correct moderate answer, fails a deliberately wrong one.

## M4 — route() (h7–8, integrate with P1 at h8 sync) — spec 04
- [ ] Orchestrate classify → zone → answer with `ladder[tier]` →
      - trivial → `check_confidence` (request `logprobs=True` on this call only)
      - moderate → `verify`
      - hard → skip entirely
      → escalate (one rung, ≤2 hops, Opus accepted unjudged). Aggregate `calls[]`
      (every impact record incl. classifier + judges) and `totals` = exact sum.
- [ ] Return dict exactly per spec 04 — **frozen at h8; P3's harness consumes it.**

## M5 — Acceptance tests (h8–10) — KR1.1
- [ ] `backend/router/route_test.py` (plain script, no framework):
      1. `route("What is 2+2?")` → tier_final == trivial, `calls` has exactly one
         entry (no judge call present).
      2. Mocked low-confidence trivial answer → escalates to moderate, `verify()`
         runs there as normal.
      3. Hard prompt (multi-step proof) → ≥1 escalation, lands on Opus.
      4. `QUALITY_FLOOR=1.01` + `CONFIDENCE_FLOOR=1.01` env override → full ladder
         walk, terminates at Opus.
      5. assert totals == sum(calls) to the cent/milligram.
- [ ] `uv run python -m backend.router.route_test` exits 0, prints each case.

## M6 — Floor tuning with P3 (h14–20) — KR1.4
- [ ] On the 20-task dry run: check the trivial-tier escalation rate separately
      from moderate's. Trivial escalating too often → inspect confidence scores
      vs obvious correctness, adjust `CONFIDENCE_FLOOR`. Moderate: <10% → spot-check
      5 accepted answers by hand; >30% → inspect judge scores vs obvious quality,
      adjust `QUALITY_FLOOR` (or classifier thresholds). Re-dry-run after each
      change. Record final floors (both) in spec 04 + `.env.example` (same commit).
