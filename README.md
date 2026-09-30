# Trust Receipt — answers that show their work

A hackathon proof-of-concept for SD Worx: *How might we turn fragmented organisational knowledge
into a trusted shared resource?*

You import your own documents (PDFs). Every AI answer comes with a **receipt**: each claim links to
its source, and each source shows plain trust signals — is it fresh, who owns it, does it apply to
your context, does it conflict with anything else. Plus a **Context Lens** (answers scoped to
country/client) and a **closing loop** (a conflict gets flagged → someone confirms → the receipt
turns green).

## Design principle

> **The LLM answers, metadata decides trust.**

The LLM writes the answer, maps each sentence to its sources, drafts document metadata on import,
and spots contradictions. It *never* judges how trustworthy a source is. Trust signals (freshness,
ownership, scope, conflicts) are computed deterministically from metadata in `trust/signals.py`, so
they are transparent and explainable. No opaque "confidence %" — every source shows its individual
signals plus a one-line plain verdict.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env        # add ANTHROPIC_API_KEY for real extraction/answers
python app.py               # → http://127.0.0.1:5000
```

The app runs with **no API key** (mock mode) so it never crashes on stage — but importing PDFs is
only useful with a key, because metadata extraction, synthesised answers and conflict detection all
use the LLM. See mock vs live below.

## Importing documents

- **In-app:** go to **Import PDFs**, choose one or more `.pdf` files, click Import. The app reads
  the text (pypdf) and the LLM drafts the metadata (title, scope, type).
- **By hand:** drop PDFs straight into `data/docs/` and hit **re-index** (or `GET /reindex`).
- Sample PDFs to try are in `samples/`.

Extracted metadata is cached next to each PDF as `<name>.meta.json`. **Owner and last-verified date
are almost never written inside a document, so they start `null`** — which honestly shows up as a red
"No owner / never verified" signal. Edit the `.meta.json` to fill them in (owner, dates, scope), then
re-index. That edit *is* the first act of taking ownership.

## Mock vs live mode

- **Live** (`ANTHROPIC_API_KEY` set, `MOCK_MODE=0`): LLM extracts metadata, writes answers with
  citations (strict JSON, one retry), and detects conflicts across the sources a question cites.
  Model from `LLM_MODEL` (default `claude-sonnet-5-5`).
- **Mock** (`MOCK_MODE=1` or no key): the app still runs — metadata = filename, answers quote the
  top source verbatim, conflicts return none. Good for a UI walkthrough, not for real content.

## Demo flow

1. **Import** two or three PDFs on the **Import PDFs** page (use `samples/`, or your own). Watch the
   cards appear — freshly imported docs read **red**: no owner, never verified. *That's the point:
   importing a document raises the trust questions.*
2. Fix one: edit its `data/docs/<name>.meta.json` to add an owner and a recent `last_verified`,
   then **re-index**. Its card turns **green — Reliable**.
3. **Ask** a question. The **Context Lens** scopes it (country/client). The answer carries citation
   chips `[1] [2]`; click one to flash its source card. Each source shows verification / owner /
   scope signals and a plain verdict; out-of-scope sources are greyed as **Doesn't apply here**.
4. If two sources **conflict**, they're shown side by side. Click **Ask … to resolve** (or **Flag
   for review** when there's no owner) → the **inbox** → **Confirm my doc is correct** (or **Update
   my doc**). Re-run the question: the conflicting source is **SUPERSEDED** and the conflict shows
   **Resolved** (green). The receipt turned green, live.
5. **Conflict Radar** (`/radar`): every conflict found so far, orphaned docs (nobody accountable)
   and stale/never-verified docs. *"Every question asked makes the knowledge base more trustworthy."*

**Reset between runs:** **Reset demo** in the header (clears owner confirmations + conflict cache;
your imported PDFs stay).

## Deploy on Vercel

```bash
npm i -g vercel        # if needed
vercel                 # first deploy (link/create project)
vercel --prod          # production
```

In the Vercel dashboard → Settings → Environment Variables, set `OPENROUTER_API_KEY`, `MOCK_MODE=0`,
and optionally `LLM_MODEL`. The glue is `api/index.py` (serves the WSGI `app`) + `vercel.json`
(routes everything to it, 60s function timeout for the LLM calls).

**Serverless caveat:** Vercel's filesystem is read-only except `/tmp`, which is ephemeral. The app
detects Vercel and puts all mutable state (`state.json`, the conflict cache, and imported PDFs)
under `/tmp/trust-data`, seeded from the bundled `data/`. That means **imported documents and owner
confirmations persist only while an instance stays warm and are wiped on cold starts** — fine for a
live demo, not for real multi-user persistence (use a real store for that). Override the location
with the `DATA_DIR` env var.

## How it works

```
app.py              Flask routes (ask, import, flag, owner inbox, radar, reindex, reset) + view assembly
trust/retrieval.py  load PDFs (pypdf) + cached metadata sidecars + Teams, BM25 index
trust/context.py    Context Lens: detect country/client, scope sources to context
trust/llm.py        Anthropic: extract_metadata, answer, detect_conflicts (+ mock fallbacks)
trust/signals.py    deterministic trust signals + plain verdicts (freshness thresholds live here)
trust/conflicts.py  LLM conflict detection with a persistent cache (data/conflicts_found.json)
trust/state.py      JSON state for flags + owner confirmations (data/state.json)
data/docs/          your imported PDFs + <name>.meta.json sidecars (git-ignored)
data/teams/         optional exported Teams messages (JSON), shown as unverified expert remarks
```

Pipeline per question: retrieve → **Context Lens** (in-scope vs out-of-scope) → LLM answers using
only in-scope sources (strict JSON) → LLM conflict check across the cited sources → render receipt.

Freshness thresholds are one dict in `trust/signals.py`: verified < 6 months = green,
6–18 months = amber, older/never = red.

Each module has a runnable self-check: `python -m trust.signals` (also `retrieval`, `context`,
`conflicts`, `state`, `llm`).

## Decisions / simplifications (hackathon scope)

- **Bring-your-own PDFs, LLM-extracted metadata.** Owner and verified-date genuinely aren't in a
  document, so they start null (red signal) until someone fills the sidecar in — honest by design.
- **BM25 retrieval** with separate doc/Teams quotas, over whatever you import.
- **Conflicts are cached** per set of cited sources, so re-runs (the closing-loop demo) are instant
  and deterministic; the Radar aggregates everything found so far.
- **State + conflict cache are single JSON files**, single-process — fine for one demo machine.
- Sample PDFs and any content are fictional.
