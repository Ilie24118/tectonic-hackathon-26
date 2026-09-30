# Trust Receipt — answers that show their work

A hackathon proof-of-concept for SD Worx: *How might we turn fragmented organisational knowledge
into a trusted shared resource?*

Every AI answer comes with a **receipt**: each claim links to its source, and each source shows
plain trust signals — is it fresh, who owns it, does it apply to your context, does it conflict with
anything else. Plus a **Context Lens** (answers scoped to country/client) and one **closing loop**
(a conflict gets flagged → the owner confirms → the receipt turns green).

## Design principle

> **The LLM answers, metadata decides trust.**

The LLM writes the answer and maps each sentence to its sources. It *never* judges how trustworthy a
source is. Trust signals (freshness, ownership, scope, conflicts) are computed deterministically from
document metadata in `trust/signals.py`, so they are transparent and explainable. There is no opaque
"confidence %" — every source shows its individual signals plus a one-line plain verdict.

## Setup

```bash
pip install -r requirements.txt
python app.py            # → http://127.0.0.1:5000
```

No API key needed — the app runs in **mock mode** by default and returns canned, realistic answers
for the demo questions. Mock and live render identically.

### Mock vs live mode

- **Mock (default):** `MOCK_MODE=1` *or* no `ANTHROPIC_API_KEY`. Canned answers from `trust/llm.py`;
  conflicts from `data/conflicts.json`. Recommended for the live demo — it never flakes.
- **Live:** set `ANTHROPIC_API_KEY` and `MOCK_MODE=0`. The LLM writes the answer + citations
  (strict JSON, one retry, falls back to mock if it won't return valid JSON). Model from
  `LLM_MODEL` (default `claude-sonnet-5-5`). Copy `.env.example` to `.env`.

## 3-minute demo script (click-by-click)

1. **Open** `http://127.0.0.1:5000`. The demo question is pre-filled. Click **Ask →**.
2. **Compare toggle** (top of the answer): click **Plain AI answer**. A confident paragraph, no
   sources — *"you can't tell what's reliable."* Click back to **Answer with receipt**.
3. **Context Lens** banner: the answer is scoped to **BE / vandamme**.
4. **Read the answer.** Claims carry citation chips `[1] [2]`. Click a chip → the matching source
   card flashes.
5. **Walk the source cards:**
   - **BE Holiday Pay Procedure v4** — ✅ verified by An Peeters ~3 weeks ago, in scope → **Reliable**.
   - **Payroll FAQ (old SharePoint)** — ❌ no owner, updated 2022, never verified, and **⚡ conflicts**
     with the procedure on the *reference period* (snippets shown side by side) → **Use with care**.
   - **NL Holiday Allowance Guide** — greyed out, 🌍 scope NL → **Doesn't apply here**.
   - **Teams message from Jonas Maes** — 💬 *expert remark, unverified*; flags a 2026 change not yet
     in the procedure (also called out under *What I could not confirm*).
6. **Close the loop.** On the conflict, click **Ask An Peeters to resolve →**. You land in her
   **owner inbox** (`/owner/An Peeters`) with both conflicting snippets.
   - Click **✅ Confirm my doc is correct** (or **Update my doc** — the box is pre-filled with the
     2026 Teams change to append).
7. Follow **See the updated receipt →**. Re-running shows: the procedure freshly verified **today**,
   the old FAQ marked **SUPERSEDED**, and the conflict now **Resolved** (green). The receipt turned
   green — live, on stage.
8. **Conflict Radar** (`/radar`): all conflicts, orphaned docs (nobody accountable) and stale docs.
   *"Every question asked makes the knowledge base more trustworthy."*

**Reset between runs:** click **Reset demo** in the header (or `GET /reset`, or
`python -c "from trust.state import reset; reset()"`).

### Other demo questions (in `data/demo_questions.md`)

- Sick leave reporting deadline (BE) — a second conflict (1 working day vs archived "2 days").
- End-of-year premium at 4 months' service (BE) — a third conflict (6-month procedure vs 2023 analysis).
- NL holiday allowance for a leaver — the clean, in-scope, no-conflict happy path.

## How it works

```
app.py            Flask routes + view assembly
trust/retrieval.py  load docs + Teams, BM25 index (doc/teams quotas; archived docs excluded)
trust/context.py    Context Lens: detect country/client, scope sources to context
trust/llm.py        Anthropic call + mock mode, strict-JSON parse with one retry
trust/signals.py    deterministic trust signals + plain verdicts (freshness thresholds live here)
trust/conflicts.py  conflict detection (mock: data/conflicts.json)
trust/state.py      JSON state for flags + owner confirmations (data/state.json)
data/               docs (*.md w/ YAML frontmatter), teams, people, clients, conflicts, questions
```

Pipeline per question: retrieve → **Context Lens** (in-scope vs out-of-scope) → LLM answers using
only in-scope sources (strict JSON) → conflict check across shown sources → render receipt.

Freshness thresholds are one dict in `trust/signals.py`: verified < 6 months = green,
6–18 months = amber, older/never = red.

Each module has a runnable self-check: `python -m trust.signals` (also `retrieval`, `context`,
`conflicts`, `state`, `llm`).

## Decisions / simplifications (hackathon scope)

- **~14 knowledge docs** instead of 20–25 — enough to give retrieval real competition and fill the
  Radar (3 conflicts, 2 orphans, stale duplicates) without padding.
- **BM25 retrieval** with separate doc/Teams quotas and archived-version exclusion, so the tiny
  corpus ranks deterministically for the demo.
- **State is a single JSON file**, single-process — fine for one demo machine, not concurrent users.
- **Conflicts are curated** (`data/conflicts.json`) rather than LLM-detected live, so the demo is
  stable; the live LLM path exists but the pitch relies on mock mode.
- All content is fictional; clients and people are invented.
