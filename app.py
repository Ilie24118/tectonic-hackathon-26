"""Trust Receipt — Flask app. Run: python app.py  (mock mode needs no API key)."""
import os

from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, url_for

from trust import conflicts as conflicts_mod
from trust import llm, state
from trust.context import apply_lens, detect_context
from trust.retrieval import get_index
from trust.signals import build_receipt

load_dotenv()
app = Flask(__name__)

DEMO_Q = ("How is double holiday pay calculated for a part-time employee who leaves mid-year? "
          "Client: Brouwerij Vandamme (BE).")

# The 2026 change from Teams that the owner can fold into the procedure (drives "Update my doc").
TEAMS_NOTE = ("From 2026, when a part-time employee has had multiple occupation fractions during "
              "the qualifying year, use the time-weighted average fraction (not the fraction at the "
              "leaving date) to calculate departure double holiday pay. Flagged by Jonas Maes in "
              "#payroll-be.")


def assemble(question, country, client):
    """Run the full pipeline and return a view model for the receipt template."""
    ctx = {"country": country or None, "client": client or None}
    detected = detect_context(question)
    ctx["country"] = ctx["country"] or detected["country"]
    ctx["client"] = ctx["client"] or detected["client"]

    st = state.load()
    idx = get_index()
    hits = idx.search(question)
    in_scope, out_of_scope = apply_lens(hits, ctx)

    ans = llm.answer(question, ctx, in_scope, out_of_scope)

    # Build source cards in display order: in-scope first, then out-of-scope (greyed).
    ordered = in_scope + out_of_scope
    cards, num_by_id = [], {}
    for i, it in enumerate(ordered, start=1):
        card = build_receipt(it, ctx, st)
        card["num"] = i
        num_by_id[it["id"]] = i
        cards.append(card)

    # Conflicts across everything shown; attach to the two cards involved.
    cons = conflicts_mod.find_conflicts([it["id"] for it in ordered], st)
    for c in cons:
        a, b = num_by_id.get(c["doc_a"]), num_by_id.get(c["doc_b"])
        for card in cards:
            if card["id"] == c["doc_a"]:
                card.setdefault("conflicts", []).append({"with": b, "topic": c["topic"],
                    "mine": c["snippet_a"], "theirs": c["snippet_b"], "resolved": c["resolved"]})
            elif card["id"] == c["doc_b"]:
                card.setdefault("conflicts", []).append({"with": a, "topic": c["topic"],
                    "mine": c["snippet_b"], "theirs": c["snippet_a"], "resolved": c["resolved"]})

    # Map answer sentence source_ids -> display numbers.
    sentences = []
    for s in ans["answer_sentences"]:
        nums = sorted(num_by_id[sid] for sid in s["source_ids"] if sid in num_by_id)
        sentences.append({"text": s["text"], "nums": nums, "source_ids": s["source_ids"]})

    plain = " ".join(s["text"] for s in ans["answer_sentences"])

    return {
        "question": question, "ctx": ctx,
        "sentences": sentences, "plain": plain,
        "cards": cards, "conflicts": cons,
        "gaps": ans["gaps"], "out_of_scope_notes": ans["out_of_scope_notes"],
        "experts": who_knows(ans, in_scope, ctx),
        "teams_note": TEAMS_NOTE,
        "mock": llm.is_mock(),
    }


def who_knows(ans, in_scope, ctx):
    """P2: on gaps, suggest an expert. Cheap heuristic over people.json."""
    if not ans["gaps"]:
        return []
    import json
    people = json.load(open(os.path.join(os.path.dirname(__file__), "data", "people.json")))
    owners = {it.get("owner") for it in in_scope if it.get("owner")}
    picks = []
    for p in people:
        score = 0
        if p["name"] in owners:
            score += 2
        if ctx.get("country") and ctx["country"] in p["countries"]:
            score += 1
        if score:
            picks.append((score, p))
    picks.sort(key=lambda x: x[0], reverse=True)
    return [{"name": p["name"], "team": p["team"], "email": p["email"],
             "why": f"Owns/handles {', '.join(p['topics'][:2])} in {'/'.join(p['countries'])}"}
            for _, p in picks[:2]]


@app.route("/")
def home():
    return render_template("ask.html", demo_q=DEMO_Q, mock=llm.is_mock())


@app.route("/ask")
def ask():
    q = request.args.get("q", "").strip()
    if not q:
        return redirect(url_for("home"))
    view = assemble(q, request.args.get("country", ""), request.args.get("client", ""))
    return render_template("receipt.html", **view)


@app.route("/flag", methods=["POST"])
def flag():
    f = request.form
    state.add_request({
        "doc_id": f["doc_id"], "conflict_with": f.get("conflict_with") or None,
        "owner": f["owner"], "topic": f.get("topic", ""),
        "snippet_a": f.get("snippet_a", ""), "snippet_b": f.get("snippet_b", ""),
        "doc_version": int(f.get("doc_version") or 1),
        "teams_note": f.get("teams_note", ""),
        "question": f.get("question", ""), "country": f.get("country", ""),
        "client": f.get("client", ""),
    })
    return redirect(url_for("owner", name=f["owner"]))


@app.route("/owner/<name>")
def owner(name):
    return render_template("owner.html", name=name, requests=state.requests_for(name))


@app.route("/owner/<name>/resolve", methods=["POST"])
def resolve(name):
    f = request.form
    rid, action = f["req_id"], f["action"]
    if action == "confirm":
        state.resolve_confirm(rid)
    elif action == "update":
        state.resolve_update(rid, f.get("append_text", "").strip() or "(owner confirmed the update)")
    else:
        state.resolve_dismiss(rid)
    req = state.get_request(rid) or {}
    if req.get("question"):
        return redirect(url_for("ask", q=req["question"], country=req.get("country", ""),
                                client=req.get("client", "")))
    return redirect(url_for("owner", name=name))


@app.route("/radar")
def radar():
    st = state.load()
    idx = get_index()
    cards = [build_receipt(d, {}, st) for d in idx.items if d["kind"] == "doc"]
    orphans = [c for c in cards if c["owner"]["label"] == "No owner"]
    orphan_ids = {c["id"] for c in orphans}
    stale = [c for c in cards
             if c["verification"]["level"] == "red" and c["id"] not in orphan_ids]
    return render_template("radar.html", conflicts=conflicts_mod.all_conflicts(st),
                           orphans=orphans, stale=stale, idx=idx)


@app.route("/reset")
def reset():
    state.reset()
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
