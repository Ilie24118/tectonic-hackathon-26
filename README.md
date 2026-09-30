# Veritas — answers that show their work

**Team Alpha** · Tectonic Hackathon 2026 · for SD Worx

Import your PDFs, ask a question, get an answer with a **receipt**: every claim links to its
source, and every source shows plain trust signals — is it fresh, who owns it, does it apply
here, does it conflict with anything else.

> **The LLM answers; metadata decides trust.** The LLM writes the answer and cites sources.
> It never rates trustworthiness — signals (freshness, owner, scope, conflicts) are computed
> deterministically in `trust/signals.py`. No opaque "confidence %".

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env        # paste your OPENROUTER_API_KEY (free: openrouter.ai/keys)
python app.py               # → http://127.0.0.1:5000
```

No key? It still runs in **mock mode** (answers quote the top source, no real extraction) —
fine for a UI walkthrough, not for real content.

## Use it

1. **Import** PDFs (**Import PDFs** page, or drop into `data/docs/` + re-index). Try `samples/`.
2. New docs show **red** — no owner, never verified. *That's the point: importing raises the
   trust questions.* Add an owner + `last_verified` to `data/docs/<name>.meta.json`, re-index →
   card turns **green**.
3. **Ask** a question. Answer carries citation chips `[1] [2]`; each source shows its signals.
   Out-of-scope sources are greyed as "Doesn't apply here".
4. **Conflicts** show side by side. Confirm the owner's version → the other is **superseded** and
   the conflict goes green. **Conflict Radar** (`/radar`) aggregates everything found.

**Reset demo** (header) clears confirmations + conflict cache; your PDFs stay.

## How it works

Per question: retrieve (BM25) → **Context Lens** scopes in/out of scope → LLM answers from
in-scope sources (strict JSON) → LLM conflict check → render receipt.

```
app.py              Flask routes + view assembly
trust/retrieval.py  load PDFs (pypdf) + metadata sidecars + Teams, BM25 index
trust/context.py    Context Lens: detect + scope by country/client
trust/llm.py        OpenRouter: extract_metadata, answer, detect_conflicts (+ mock fallbacks)
trust/signals.py    deterministic trust signals + verdicts (freshness thresholds live here)
trust/conflicts.py  LLM conflict detection, cached in data/conflicts_found.json
trust/state.py      flags + owner confirmations in data/state.json
```

Each module self-checks: `python -m trust.signals` (also `retrieval`, `context`, `conflicts`,
`state`, `llm`).

## Deploy (Vercel)

```bash
vercel --prod
```

Set `OPENROUTER_API_KEY` and `MOCK_MODE=0` in the dashboard. Entry point is `api/index.py`.
Serverless note: only `/tmp` is writable and it's wiped on cold starts, so imported docs and
confirmations don't persist between them — fine for a demo, not for real storage.

## Notes

- **Bring-your-own PDFs.** Owner and verified-date aren't in a document, so they start null (red)
  until someone fills the sidecar — honest by design.
- State + conflict cache are single JSON files, single-process — fine for one demo machine.
- Sample PDFs and content are fictional.
