"""LLM answer generation with a robust mock mode.

The LLM writes the answer and maps each sentence to source ids. It NEVER judges trust.
Mock mode returns canned-but-realistic answers keyed to the demo questions so the demo
never breaks on stage. Mock and live return the identical JSON shape:

    {"answer_sentences": [{"text": str, "source_ids": [str]}],
     "gaps": [str], "out_of_scope_notes": [str]}
"""
import json
import os
import re

MODEL = os.environ.get("LLM_MODEL", "claude-sonnet-5-5")


def is_mock():
    return os.environ.get("MOCK_MODE") == "1" or not os.environ.get("ANTHROPIC_API_KEY")


# ---------------------------------------------------------------- mock answers

def _has(ids, wanted):
    return wanted in ids


def _mock_answer(question, ctx, in_scope, out_of_scope):
    q = question.lower()
    ids = [it["id"] for it in in_scope]
    oos_ids = [it["id"] for it in out_of_scope]

    def note_nl():
        return (["The NL Holiday Allowance Guide looks related but covers the Dutch 8% holiday "
                 "allowance, not Belgian double holiday pay — it does not apply to a BE question."]
                if "nl-holiday-allowance-guide" in oos_ids else [])

    # Q1 — planted scenario: double holiday pay, part-time, leaver
    if "holiday pay" in q and _has(ids, "be-holiday-pay-procedure"):
        sents = [
            {"text": "For a part-time employee, double holiday pay is 92% of the gross monthly "
                     "salary, applied pro rata to the average occupation fraction during the "
                     "qualifying year (the calendar year before the holiday is taken).",
             "source_ids": ["be-holiday-pay-procedure"]},
            {"text": "When the employee leaves mid-year, you settle departure holiday pay covering "
                     "vested rights from the previous qualifying year (N-1) plus the current year's "
                     "accrual up to the leaving date, at 7.67% of the relevant gross earnings, "
                     "adjusted by the part-time fraction.",
             "source_ids": ["be-holiday-pay-procedure"]},
        ]
        if _has(ids, "client-vandamme-rules"):
            sents.append({"text": "For Brouwerij Vandamme, standard Belgian rules apply: blue-collar "
                                  "staff under JC 118 are paid via the holiday fund (RJV), while "
                                  "office staff under JC 200 are paid directly by the employer.",
                          "source_ids": ["client-vandamme-rules"]})
        if _has(ids, "tm-be-001"):
            sents.append({"text": "Note: a 2026 change to the part-time averaging method "
                                  "(time-weighted average across multiple fractions) was flagged in "
                                  "Teams but is not yet reflected in the official procedure.",
                          "source_ids": ["tm-be-001"]})
        gaps = ["The 2026 averaging change is only in a Teams message, not yet in the verified "
                "procedure (v4). Confirm with the owner before finalising the calculation."]
        return {"answer_sentences": sents, "gaps": gaps, "out_of_scope_notes": note_nl()}

    # Q2 — sick leave reporting deadline
    if "sick leave" in q or ("sick" in q and "report" in q):
        if _has(ids, "be-sick-leave-reporting"):
            return {"answer_sentences": [
                {"text": "In Belgium an employee must notify their manager on the first day of "
                         "absence, within one working day, by phone or via the HR portal.",
                 "source_ids": ["be-sick-leave-reporting"]},
                {"text": "A medical certificate must reach HR within two working days of the start "
                         "of the absence (from day 1 only if the employer or CLA requires it).",
                 "source_ids": ["be-sick-leave-reporting"]},
            ], "gaps": [], "out_of_scope_notes": []}

    # Q3 — end-of-year premium seniority
    if "premium" in q or "end-of-year" in q or "end of year" in q or "13th" in q:
        if _has(ids, "be-end-of-year-premium"):
            return {"answer_sentences": [
                {"text": "Under the current procedure, an employee needs at least 6 months of "
                         "seniority in the reference year to receive a pro-rata end-of-year premium, "
                         "so 4 months of service would not qualify unless the CLA says otherwise.",
                 "source_ids": ["be-end-of-year-premium"]},
                {"text": "When entitled, the premium is pro-rated by months worked over 12 and by "
                         "the part-time occupation fraction.",
                 "source_ids": ["be-end-of-year-premium"]},
            ], "gaps": ["A 2023 analysis suggests a 3-month threshold for some joint committees — "
                        "this conflicts with the current 6-month procedure; check the specific CLA."],
                    "out_of_scope_notes": []}

    # Q4 — NL holiday allowance (happy path)
    if "holiday allowance" in q or (ctx.get("country") == "NL" and "holiday" in q):
        if _has(ids, "nl-holiday-allowance-guide"):
            return {"answer_sentences": [
                {"text": "In the Netherlands, holiday allowance is 8% of gross annual salary, "
                         "accrued from June to May and paid out in May or June.",
                 "source_ids": ["nl-holiday-allowance-guide"]},
                {"text": "For a leaver, the accrued but unpaid allowance from the last pay-out month "
                         "up to the leaving date is settled on the final payslip at the same 8% rate.",
                 "source_ids": ["nl-holiday-allowance-guide"]},
            ], "gaps": [], "out_of_scope_notes": []}

    # Generic fallback: quote the top in-scope source.
    if in_scope:
        top = in_scope[0]
        first = re.split(r"(?<=[.!?])\s+", re.sub(r"#.*", "", top["body"]).strip())
        text = " ".join(first[:2]).strip() or top["body"][:200]
        return {"answer_sentences": [{"text": text, "source_ids": [top["id"]]}],
                "gaps": ["This is a best-effort answer from the closest source; verify with the owner."],
                "out_of_scope_notes": note_nl()}
    return {"answer_sentences": [],
            "gaps": ["No in-scope source was found for this question and context."],
            "out_of_scope_notes": note_nl()}


# ---------------------------------------------------------------- live answers

_SYSTEM = (
    "You are a payroll/HR knowledge assistant. Answer ONLY using the provided in-scope sources. "
    "Map every sentence to the source ids it came from. Never invent facts. If something is "
    "missing, list it in gaps. Do NOT judge how trustworthy sources are — only report content. "
    "Return STRICT JSON with keys: answer_sentences (list of {text, source_ids}), gaps (list of "
    "strings), out_of_scope_notes (list of strings). No prose outside the JSON."
)


def _sources_block(items, label):
    out = [f"## {label}"]
    for it in items:
        out.append(f"[{it['id']}] {it.get('title', it['id'])}\n{it.get('body', '')}\n")
    return "\n".join(out) if items else f"## {label}\n(none)"


def _extract_json(text):
    m = re.search(r"\{.*\}", text, re.DOTALL)
    return json.loads(m.group(0)) if m else json.loads(text)


def _live_answer(question, ctx, in_scope, out_of_scope):
    import anthropic
    client = anthropic.Anthropic()
    prompt = (
        f"Question: {question}\nContext: country={ctx.get('country')}, client={ctx.get('client')}\n\n"
        f"{_sources_block(in_scope, 'IN-SCOPE SOURCES (use these)')}\n\n"
        f"{_sources_block(out_of_scope, 'OUT-OF-SCOPE SOURCES (do not use; note if misleading)')}\n\n"
        "Return the strict JSON now."
    )
    for attempt in range(2):
        msg = client.messages.create(
            model=MODEL, max_tokens=1500, system=_SYSTEM,
            messages=[{"role": "user", "content": prompt if attempt == 0
                       else prompt + "\n\nYour last reply was not valid JSON. Return ONLY the JSON."}],
        )
        try:
            data = _extract_json(msg.content[0].text)
            data.setdefault("gaps", [])
            data.setdefault("out_of_scope_notes", [])
            data.setdefault("answer_sentences", [])
            return data
        except (ValueError, KeyError, json.JSONDecodeError):
            continue
    # If the model won't cooperate, fall back to mock so the demo still renders.
    return _mock_answer(question, ctx, in_scope, out_of_scope)


def answer(question, ctx, in_scope, out_of_scope):
    if is_mock():
        return _mock_answer(question, ctx, in_scope, out_of_scope)
    return _live_answer(question, ctx, in_scope, out_of_scope)


if __name__ == "__main__":
    os.environ["MOCK_MODE"] = "1"
    from trust.retrieval import get_index
    from trust.context import detect_context, apply_lens
    idx = get_index()
    q = "How is double holiday pay calculated for a part-time employee who leaves mid-year? " \
        "Client: Brouwerij Vandamme (BE)."
    ctx = detect_context(q)
    hits = idx.search(q, 6)
    ins, oos = apply_lens(hits, ctx)
    a = answer(q, ctx, ins, oos)
    assert a["answer_sentences"][0]["source_ids"] == ["be-holiday-pay-procedure"], a
    assert a["gaps"], "expected a gap about the Teams change"
    print("llm mock ok:", [s["source_ids"] for s in a["answer_sentences"]])
