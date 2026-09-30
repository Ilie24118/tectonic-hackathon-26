"""Context Lens: detect country/client from the question and scope sources to context."""
import json
import os

from trust.config import DATA
from trust.signals import scope_matches

COUNTRIES = ["BE", "NL", "FR", "DE", "LU"]
_COUNTRY_WORDS = {
    "belgium": "BE", "belgian": "BE", "belgië": "BE", "belgique": "BE",
    "netherlands": "NL", "dutch": "NL", "nederland": "NL", "holland": "NL",
    "france": "FR", "french": "FR", "germany": "DE", "german": "DE",
    "luxembourg": "LU",
}


def _clients():
    try:
        return json.load(open(os.path.join(DATA, "clients.json"), encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def detect_context(question):
    """Best-effort country/client detection. Explicit selectors in the UI override this."""
    q = question.lower()
    country = None
    for code in COUNTRIES:
        if f"({code.lower()})" in q or f" {code.lower()} " in q or f":{code.lower()}" in q:
            country = code
            break
    if not country:
        for word, code in _COUNTRY_WORDS.items():
            if word in q:
                country = code
                break
    client = None
    for c in _clients():
        if c["name"].lower() in q or c["id"] in q:
            client = c["id"]
            country = country or c["country"]
            break
    return {"country": country, "client": client}


def apply_lens(items, ctx):
    """Split retrieved items into in-scope (usable by the LLM) and out-of-scope (shown, greyed)."""
    in_scope, out_of_scope = [], []
    for it in items:
        if it.get("kind") == "teams" or scope_matches(it.get("scope") or {}, ctx):
            in_scope.append(it)
        else:
            out_of_scope.append(it)
    return in_scope, out_of_scope


if __name__ == "__main__":
    assert detect_context("What is the rule in Belgium (BE)?")["country"] == "BE"
    assert detect_context("How does it work in the Netherlands?")["country"] == "NL"
    items = [{"id": "d", "kind": "doc", "scope": {"countries": ["NL"], "clients": ["all"]}}]
    ins, oos = apply_lens(items, {"country": "BE", "client": None})
    assert oos and not ins, "NL doc should be out of scope for BE"
    print("context ok")
