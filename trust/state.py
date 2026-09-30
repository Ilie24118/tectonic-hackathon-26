"""Tiny JSON-file state for owner requests and doc overrides. Single-process demo only."""
import json
import os
from datetime import date

from trust.config import DATA

STATE_PATH = os.path.join(DATA, "state.json")
EMPTY = {"requests": [], "overrides": {}}


def load():
    try:
        return json.load(open(STATE_PATH, encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(EMPTY)


def save(state):
    json.dump(state, open(STATE_PATH, "w", encoding="utf-8"), indent=2)


def reset():
    save({"requests": [], "overrides": {}})


def add_request(req):
    """Create an 'ask the owner' request. Dedupes on (doc_id, conflict_with)."""
    state = load()
    key = (req.get("doc_id"), req.get("conflict_with"))
    for r in state["requests"]:
        if (r.get("doc_id"), r.get("conflict_with")) == key and r["status"] == "open":
            return r["id"]
    req["id"] = f"req-{len(state['requests']) + 1}"
    req["status"] = "open"
    req["created"] = date.today().isoformat()
    state["requests"].append(req)
    save(state)
    return req["id"]


def requests_for(owner):
    return [r for r in load()["requests"] if r.get("owner") == owner]


def get_request(req_id):
    return next((r for r in load()["requests"] if r["id"] == req_id), None)


def resolve_confirm(req_id):
    """Owner confirms their doc is correct: re-verify it today, supersede the conflicting doc."""
    state = load()
    req = next((r for r in state["requests"] if r["id"] == req_id), None)
    if not req:
        return
    ov = state["overrides"]
    doc = req["doc_id"]
    ov.setdefault(doc, {})["last_verified"] = date.today().isoformat()
    if req.get("conflict_with"):
        ov.setdefault(req["conflict_with"], {})["superseded"] = True
    req["status"] = "confirmed"
    req["resolution"] = "Confirmed correct; conflicting source superseded."
    save(state)


def resolve_update(req_id, appended_text):
    """Owner updates their doc: append the change, bump version, re-verify today."""
    state = load()
    req = next((r for r in state["requests"] if r["id"] == req_id), None)
    if not req:
        return
    ov = state["overrides"].setdefault(req["doc_id"], {})
    ov["appended_text"] = (ov.get("appended_text", "") + "\n\n" + appended_text).strip()
    ov["last_verified"] = date.today().isoformat()
    try:
        ov["version"] = int(float(req.get("doc_version") or 1)) + 1
    except (TypeError, ValueError):
        ov["version"] = None
    if req.get("conflict_with"):
        state["overrides"].setdefault(req["conflict_with"], {})["superseded"] = True
    req["status"] = "updated"
    req["resolution"] = "Document updated by owner."
    save(state)


def resolve_dismiss(req_id):
    state = load()
    req = next((r for r in state["requests"] if r["id"] == req_id), None)
    if req:
        req["status"] = "not_my_area"
        req["resolution"] = "Owner said this is not their area."
        save(state)


if __name__ == "__main__":
    reset()
    rid = add_request({"doc_id": "be-holiday-pay-procedure",
                       "conflict_with": "payroll-faq-old-sharepoint",
                       "owner": "An Peeters", "topic": "reference period"})
    assert add_request({"doc_id": "be-holiday-pay-procedure",
                        "conflict_with": "payroll-faq-old-sharepoint",
                        "owner": "An Peeters", "topic": "reference period"}) == rid  # deduped
    resolve_confirm(rid)
    st = load()
    assert st["overrides"]["payroll-faq-old-sharepoint"]["superseded"] is True
    assert st["overrides"]["be-holiday-pay-procedure"]["last_verified"] == date.today().isoformat()
    reset()
    print("state ok:", rid)
