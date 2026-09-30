"""LLM calls via OpenRouter: extract metadata from a PDF, answer a question, detect conflicts.

The LLM writes the answer, maps claims to sources, extracts metadata and spots contradictions.
It NEVER judges how trustworthy a source is — that stays deterministic in signals.py.

With no OPENROUTER_API_KEY (or MOCK_MODE=1) the app still runs: metadata falls back to the
filename, answers quote the top source, and conflict detection returns nothing. Real use needs
a key. All three functions return the same JSON shapes in mock and live mode.
"""
import json
import os
import re

import requests

API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = os.environ.get("LLM_MODEL", "nvidia/nemotron-3-super-120b-a12b:free")


def is_mock():
    return os.environ.get("MOCK_MODE") == "1" or not os.environ.get("OPENROUTER_API_KEY")


def _extract_json(text):
    m = re.search(r"[\[{].*[\]}]", text, re.DOTALL)
    return json.loads(m.group(0) if m else text)


def _post(system, prompt, max_tokens):
    r = requests.post(API_URL, timeout=120,
        headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
                 "Content-Type": "application/json"},
        json={"model": os.environ.get("LLM_MODEL", MODEL), "max_tokens": max_tokens,
              "messages": [{"role": "system", "content": system},
                           {"role": "user", "content": prompt}]})
    r.raise_for_status()
    return r.json()["choices"][0]["message"].get("content") or ""


def _call_json(system, prompt, max_tokens=1500):
    """One call + one retry, returning parsed JSON or None."""
    for attempt in range(2):
        try:
            text = _post(system, prompt if attempt == 0
                         else prompt + "\n\nYour last reply was not valid JSON. Return ONLY the JSON.",
                         max_tokens)
            return _extract_json(text)
        except (ValueError, KeyError, json.JSONDecodeError, requests.RequestException):
            continue
    return None


# ------------------------------------------------------------- metadata extraction

_META_SYSTEM = (
    "You extract metadata from a payroll/HR document. Return STRICT JSON with keys: "
    "title, source_type (one of procedure|policy|faq|checklist|manual|analysis|document), "
    "scope {countries: [ISO2 codes], clients: [names], products: [payroll|hr|reward|finance]}, "
    "owner (person's name or null), owner_team (or null), "
    "last_updated (YYYY-MM-DD or null), last_verified (YYYY-MM-DD or null), version (int or null). "
    "CRITICAL: only fill owner/last_updated/last_verified/version if the value is EXPLICITLY stated "
    "in the text. If it is not in the document, use null — never guess. No prose outside the JSON."
)


def _fallback_meta(filename):
    title = re.sub(r"[-_]+", " ", os.path.splitext(filename)[0]).strip().title()
    return {"title": title, "source_type": "document",
            "scope": {"countries": [], "clients": [], "products": []},
            "owner": None, "owner_team": None,
            "last_updated": None, "last_verified": None, "version": None}


def extract_metadata(text, filename):
    if is_mock() or not text.strip():
        return _fallback_meta(filename)
    data = _call_json(_META_SYSTEM,
                      f"Filename: {filename}\n\nDocument text:\n{text[:6000]}\n\nReturn the JSON now.")
    if not isinstance(data, dict):
        return _fallback_meta(filename)
    base = _fallback_meta(filename)
    base.update({k: data.get(k, base[k]) for k in base})
    base["scope"] = data.get("scope") or base["scope"]
    return base


# ------------------------------------------------------------- answering

_ANSWER_SYSTEM = (
    "You are a payroll/HR knowledge assistant. Answer ONLY using the provided in-scope sources. "
    "Map every sentence to the source ids it came from. Never invent facts. If something is "
    "missing, list it in gaps. Do NOT judge how trustworthy sources are. Return STRICT JSON with "
    "keys: answer_sentences (list of {text, source_ids}), gaps (list of strings), "
    "out_of_scope_notes (list of strings). No prose outside the JSON."
)


def _sources_block(items, label):
    if not items:
        return f"## {label}\n(none)"
    return f"## {label}\n" + "\n".join(
        f"[{it['id']}] {it.get('title', it['id'])}\n{it.get('body', '')}\n" for it in items)


def _generic_answer(question, in_scope, out_of_scope):
    notes = []
    for it in out_of_scope:
        notes.append(f"{it.get('title', it['id'])} looked related but is out of scope for this "
                     f"context, so it was not used.")
    if not in_scope:
        return {"answer_sentences": [], "gaps": ["No in-scope source was found for this "
                "question and context."], "out_of_scope_notes": notes}
    top = in_scope[0]
    body = re.sub(r"\s+", " ", re.sub(r"#+ ", "", top.get("body", ""))).strip()
    sentences = re.split(r"(?<=[.!?])\s+", body)
    text = " ".join(sentences[:3]).strip() or body[:300]
    return {"answer_sentences": [{"text": text, "source_ids": [top["id"]]}],
            "gaps": ["Mock mode: this quotes the closest source verbatim. Set ANTHROPIC_API_KEY "
                     "for a real synthesised answer."],
            "out_of_scope_notes": notes}


def answer(question, ctx, in_scope, out_of_scope):
    if is_mock():
        return _generic_answer(question, in_scope, out_of_scope)
    prompt = (f"Question: {question}\nContext: country={ctx.get('country')}, "
              f"client={ctx.get('client')}\n\n"
              f"{_sources_block(in_scope, 'IN-SCOPE SOURCES (use these)')}\n\n"
              f"{_sources_block(out_of_scope, 'OUT-OF-SCOPE SOURCES (do not use; note if misleading)')}\n\n"
              "Return the strict JSON now.")
    data = _call_json(_ANSWER_SYSTEM, prompt)
    if not isinstance(data, dict) or "answer_sentences" not in data:
        return _generic_answer(question, in_scope, out_of_scope)
    data.setdefault("gaps", [])
    data.setdefault("out_of_scope_notes", [])
    return data


# ------------------------------------------------------------- conflict detection

_CONFLICT_SYSTEM = (
    "You compare payroll/HR sources for FACTUAL CONTRADICTIONS (different numbers, dates, rules, "
    "thresholds for the same thing). Return STRICT JSON: a list of objects with keys doc_a, doc_b "
    "(the source ids), topic (short phrase), snippet_a, snippet_b (the conflicting quotes). Only "
    "report genuine contradictions between two DIFFERENT sources. If none, return []. No prose."
)


def detect_conflicts(sources):
    """sources: list of {id, title, body}. Returns a list of conflict dicts, or None if the
    call failed (so callers can avoid caching a failure as 'no conflicts')."""
    if is_mock() or len(sources) < 2:
        return []
    block = "\n".join(f"[{s['id']}] {s.get('title', s['id'])}\n{s.get('body', '')[:2500]}\n"
                      for s in sources)
    data = _call_json(_CONFLICT_SYSTEM, f"Sources:\n{block}\n\nReturn the JSON list now.")
    if data is None:
        return None
    if isinstance(data, dict):
        data = data.get("conflicts", [])
    ids = {s["id"] for s in sources}
    return [c for c in (data or [])
            if c.get("doc_a") in ids and c.get("doc_b") in ids and c["doc_a"] != c["doc_b"]]


if __name__ == "__main__":
    os.environ["MOCK_MODE"] = "1"
    assert extract_metadata("", "be-holiday-pay-procedure.pdf")["title"] == "Be Holiday Pay Procedure"
    assert detect_conflicts([{"id": "a", "body": "x"}, {"id": "b", "body": "y"}]) == []
    a = answer("q", {}, [{"id": "d1", "title": "T", "body": "The rate is 8%. More text here. And more."}], [])
    assert a["answer_sentences"][0]["source_ids"] == ["d1"], a
    print("llm mock ok")
