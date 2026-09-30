"""Conflict detection across cited sources.

Mock mode reads known conflicts from data/conflicts.json. Live mode can ask the LLM to
compare pairs, but the demo relies on the deterministic list so it never flakes.
"""
import json
import os

DATA = os.path.join(os.path.dirname(__file__), "..", "data")


def _known():
    return json.load(open(os.path.join(DATA, "conflicts.json"), encoding="utf-8"))


def find_conflicts(cited_ids, state=None):
    """Return conflicts among the cited source ids, dropping any resolved by an owner."""
    overrides = (state or {}).get("overrides", {})
    ids = set(cited_ids)
    out = []
    for c in _known():
        if c["doc_a"] in ids and c["doc_b"] in ids:
            resolved = overrides.get(c["doc_a"], {}).get("superseded") \
                or overrides.get(c["doc_b"], {}).get("superseded")
            out.append({**c, "resolved": bool(resolved)})
    return out


def all_conflicts(state=None):
    """Every known conflict (for the Radar), with resolved flags."""
    return find_conflicts(
        {c["doc_a"] for c in _known()} | {c["doc_b"] for c in _known()}, state
    )


if __name__ == "__main__":
    cs = find_conflicts(["be-holiday-pay-procedure", "payroll-faq-old-sharepoint",
                         "nl-holiday-allowance-guide"])
    assert len(cs) == 1 and cs[0]["topic"].startswith("reference period"), cs
    assert cs[0]["resolved"] is False
    st = {"overrides": {"payroll-faq-old-sharepoint": {"superseded": True}}}
    assert find_conflicts(["be-holiday-pay-procedure", "payroll-faq-old-sharepoint"], st)[0]["resolved"]
    print("conflicts ok:", cs[0]["topic"])
