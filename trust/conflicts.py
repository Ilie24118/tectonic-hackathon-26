"""Conflict detection across sources, LLM-driven with a persistent cache.

Conflicts are found among the sources cited by a question (one LLM call, cached by the set of
ids so re-runs are instant and deterministic). Everything found so far is remembered so the
Radar can show it — "every question asked makes the knowledge base more trustworthy."

Mock mode (no API key) detects nothing.
"""
import json
import os

from trust import llm

CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "conflicts_found.json")


def _load():
    try:
        return json.load(open(CACHE, encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"by_key": {}}


def _save(cache):
    json.dump(cache, open(CACHE, "w", encoding="utf-8"), indent=2)


def _resolved(c, state):
    ov = (state or {}).get("overrides", {})
    return bool(ov.get(c["doc_a"], {}).get("superseded") or ov.get(c["doc_b"], {}).get("superseded"))


def detect_for(sources, state=None):
    """sources: retrieved items (with id/title/body). Returns conflicts among them, cached."""
    key = ",".join(sorted(s["id"] for s in sources))
    cache = _load()
    if key not in cache["by_key"]:
        cache["by_key"][key] = llm.detect_conflicts(sources)
        _save(cache)
    return [{**c, "resolved": _resolved(c, state)} for c in cache["by_key"][key]]


def all_found(state=None):
    """Every conflict found so far (deduped), for the Radar."""
    seen, out = set(), []
    for conflicts in _load()["by_key"].values():
        for c in conflicts:
            k = (frozenset((c["doc_a"], c["doc_b"])), c.get("topic", ""))
            if k not in seen:
                seen.add(k)
                out.append({**c, "resolved": _resolved(c, state)})
    return out


def reset():
    _save({"by_key": {}})


if __name__ == "__main__":
    os.environ["MOCK_MODE"] = "1"
    assert detect_for([{"id": "a", "body": "x"}, {"id": "b", "body": "y"}]) == []
    print("conflicts ok (mock: none)")
