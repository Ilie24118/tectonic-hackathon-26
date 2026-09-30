# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**Veritas** — a Flask hackathon PoC (SD Worx). You import PDFs; the app answers questions over
them and attaches a "receipt": each claim cites a source, and each source shows deterministic trust
signals (freshness, owner, scope, conflicts) plus a plain verdict. See `README.md` for the product
pitch and demo flow.

## Commands

A local virtualenv lives at `./venv` — use it directly (don't rely on an activated shell):

```bash
./venv/bin/pip install -r requirements.txt   # first-time setup
./venv/bin/python app.py                      # run → http://127.0.0.1:5000
```

There is **no test framework, linter, or build step.** Each `trust/` module has an `assert`-based
self-check in its `if __name__ == "__main__"` block — that is how you verify logic:

```bash
./venv/bin/python -m trust.signals      # also: retrieval, context, conflicts, state, llm
```

Self-checks force `MOCK_MODE=1` internally, so they run without an API key. Run them after touching
any `trust/` module. The app loads `.env` (git-ignored) via `python-dotenv`; `.env.example` shows the
keys.

## Core principle — do not violate

**The LLM answers; metadata decides trust.** The LLM (`trust/llm.py`) writes the answer, maps each
sentence to source ids, extracts document metadata, and detects conflicts. It **never** judges how
trustworthy a source is. All trust signals and verdicts are computed deterministically from metadata
in `trust/signals.py`. Keep these two responsibilities separate — never let the LLM emit a
trust/confidence score, and never hardcode answer content into `signals.py`.

## Mock vs live mode

`llm.is_mock()` is the single gate, true when `MOCK_MODE=1` or `OPENROUTER_API_KEY` is unset. In mock
mode the app still runs end-to-end but degrades: metadata falls back to the filename, `answer()` quotes
the top source verbatim, and `detect_conflicts()` returns nothing. Every LLM function returns the
**same JSON shape** in both modes so templates never branch on it. The backend is **OpenRouter** (an
OpenAI-compatible endpoint hit via `requests` in `llm._post`), default model
`nvidia/nemotron-3-super-120b-a12b:free` — not the Anthropic SDK.

## Request pipeline

`app.assemble()` is the heart of a question. The order matters:

1. `retrieval.get_index()` — loads PDFs + Teams messages and builds a fresh BM25 index **per request**
   (corpus is tiny; this lets owner edits re-index immediately).
2. `context.detect_context()` + `apply_lens()` — infer country/client, split hits into in-scope vs
   out-of-scope. Only in-scope sources are handed to the LLM; out-of-scope are still rendered, greyed.
3. `llm.answer()` — strict JSON `{answer_sentences:[{text,source_ids}], gaps, out_of_scope_notes}`.
4. `conflicts.detect_for()` — LLM conflict check across **all shown** sources, then attached to the
   two cards involved.
5. Build source cards via `signals.build_receipt()`, number them, map sentence `source_ids` → card
   numbers for the citation chips.

## Non-obvious mechanics

- **PDF ingestion + sidecars** (`retrieval.ingest_pdf`): each `data/docs/<name>.pdf` gets a cached
  `<name>.meta.json` written once by LLM extraction. Regenerated only if the sidecar is missing or
  older than the PDF (mtime check), or with `force=True` (the `/reindex` route). **Owner and
  last-verified date are not in a PDF**, so they extract as `null` → red signals until someone edits
  the sidecar. Both PDFs and sidecars are git-ignored (user content).
- **Closing loop** (`state.py` + `/flag` → `/owner/<name>` → `/resolve`): confirming a conflict writes
  an *override* into `data/state.json` — re-verifies the owner's doc today and marks the conflicting
  doc `superseded`. `signals._effective()` applies these overrides on top of the raw item at render
  time. The loop is owner-agnostic: with no extracted owner it routes to a generic "Reviewer" inbox,
  so it still works. `/reset` clears state + the conflict cache.
- **Conflict cache** (`data/conflicts_found.json`): `detect_for` caches results keyed by the sorted
  set of source ids, so re-runs (the closing-loop demo) are instant and deterministic, and the Radar
  aggregates everything found. **A failed LLM call returns `None` and is deliberately not cached** —
  otherwise a transient free-tier rate-limit freezes in as "no conflicts". Preserve this distinction
  (`detect_conflicts` returns `None` on failure vs `[]` for genuinely none).
- **Freshness thresholds** are one dict, `signals.FRESHNESS` (verified <6mo green, 6–18 amber,
  older/never red). Change signal rules there, nowhere else.
- **Retrieval quotas**: `search()` fills separate doc and Teams slots (`n_docs`/`n_teams`) so short
  Teams chatter can't crowd out real documents on a small corpus.

## State & data files

Single-process, file-backed (no DB): `data/state.json` (flags + overrides) and
`data/conflicts_found.json` (conflict cache) are mutated at runtime. `data/docs/` and `data/teams/`
hold user content and ship empty (`.gitkeep`); `samples/` has test PDFs. `data/people.json` /
`data/clients.json` are optional (`[]` by default) — they only enrich Who-Knows and client detection.

**All data paths come from `trust/config.py`** (`DATA`, `DOCS`, `TEAMS`) — never hardcode `data/`
paths in a module; import from config. On Vercel (detected via the `VERCEL` env var, or forced with
`DATA_DIR`) it seeds a writable copy under `/tmp/trust-data`, since the serverless FS is read-only
except `/tmp`. That `/tmp` copy is ephemeral — state doesn't survive cold starts. Vercel entrypoint
is `api/index.py` (exposes the WSGI `app`) wired by `vercel.json`.
