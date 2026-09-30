"""Deterministic trust signals + plain-language verdicts.

The LLM never touches this. Every signal here is computed from metadata so it is
transparent and explainable. No opaque confidence score.
"""
from datetime import date

# All freshness thresholds live here, in one place.
FRESHNESS = {
    "green_max_months": 6,    # verified within 6 months
    "amber_max_months": 18,   # verified 6-18 months ago
    # older than amber, or never verified -> red
}


def _parse(d):
    if not d:
        return None
    return date.fromisoformat(str(d))


def _months_ago(d):
    today = date.today()
    return (today.year - d.year) * 12 + (today.month - d.month) - (1 if today.day < d.day else 0)


def _human_age(d):
    days = (date.today() - d).days
    if days < 14:
        return f"{max(days, 1)} days ago"
    if days < 60:
        return f"{days // 7} weeks ago"
    if days < 365:
        return f"{days // 30} months ago"
    years = days / 365
    return f"{years:.0f} year{'s' if years >= 2 else ''} ago"


def _effective(item, state):
    """Apply owner-confirmation overrides from state.json onto a copy of the item."""
    ov = (state or {}).get("overrides", {}).get(item["id"])
    if not ov:
        return item
    merged = dict(item)
    if ov.get("last_verified"):
        merged["last_verified"] = ov["last_verified"]
    if ov.get("version") is not None:
        merged["version"] = ov["version"]
    if ov.get("appended_text"):
        merged["body"] = item.get("body", "") + "\n\n" + ov["appended_text"]
    merged["superseded"] = ov.get("superseded", False)
    return merged


def verification_signal(item):
    if item.get("kind") == "teams":
        return {"level": "amber", "icon": "💬", "label": "Expert remark, unverified",
                "detail": f"Posted by {item.get('author', 'unknown')} {_human_age(_parse(item['last_updated']))}"}
    lv = _parse(item.get("last_verified"))
    if lv is None:
        lu = _parse(item.get("last_updated"))
        upd = f"Updated {_human_age(lu)}" if lu else "Unknown date"
        return {"level": "red", "icon": "❌", "label": "Never verified",
                "detail": f"{upd}, never confirmed by an owner"}
    m = _months_ago(lv)
    if m <= FRESHNESS["green_max_months"]:
        level, icon = "green", "✅"
    elif m <= FRESHNESS["amber_max_months"]:
        level, icon = "amber", "⚠️"
    else:
        level, icon = "red", "❌"
    return {"level": level, "icon": icon, "label": f"Verified by owner {_human_age(lv)}",
            "detail": f"Owner last confirmed content on {lv.isoformat()}"}


def owner_signal(item):
    owner = item.get("owner")
    if owner:
        return {"level": "green", "icon": "👤", "label": owner,
                "detail": item.get("owner_team") or ""}
    return {"level": "red", "icon": "👤", "label": "No owner",
            "detail": "Nobody is accountable for this document"}


def scope_matches(scope, ctx):
    countries = scope.get("countries") or []
    clients = scope.get("clients") or []
    country_ok = (not ctx.get("country")) or (not countries) or (ctx["country"] in countries)
    client_ok = (not clients) or ("all" in clients) or (not ctx.get("client")) or (ctx["client"] in clients)
    return country_ok and client_ok


def scope_signal(item, ctx):
    scope = item.get("scope") or {}
    countries = scope.get("countries") or []
    if item.get("kind") == "teams":
        return {"level": "amber", "icon": "🌍", "label": "Scope not declared",
                "detail": "Teams message — applies where the author intended", "matches": True}
    parts = []
    parts.append("/".join(countries) if countries else "country unclear")
    clients = scope.get("clients") or []
    parts.append("all clients" if "all" in clients else ("/".join(clients) if clients else "clients unclear"))
    products = scope.get("products") or []
    if products:
        parts.append("/".join(products))
    label = ", ".join(parts)
    matches = scope_matches(scope, ctx)
    if not matches:
        return {"level": "red", "icon": "🌍", "label": label,
                "detail": f"Does not match current context ({ctx.get('country') or '—'}"
                          f"{'/' + ctx['client'] if ctx.get('client') else ''})", "matches": False}
    level = "green" if countries else "amber"
    return {"level": level, "icon": "🌍", "label": label,
            "detail": "Matches current context" if countries else "Scope is unclear — matches by default",
            "matches": True}


def verdict(item, verification, owner, scope):
    if item.get("superseded"):
        return {"label": "Superseded", "level": "red",
                "reason": "Replaced after owner review — do not use"}
    if not scope["matches"]:
        return {"label": "Doesn't apply here", "level": "red",
                "reason": f"Out of scope: {scope['label']}"}
    if item.get("kind") == "teams":
        return {"label": "Use with care", "level": "amber",
                "reason": "Expert remark from Teams — not a verified source"}
    if verification["level"] == "green" and owner["level"] == "green":
        return {"label": "Reliable", "level": "green",
                "reason": "Owned and recently verified, in scope"}
    if owner["level"] == "red" or verification["level"] == "red":
        return {"label": "Use with care", "level": "red" if verification["level"] == "red" else "amber",
                "reason": "No accountable owner" if owner["level"] == "red" else "Not verified recently"}
    return {"label": "Use with care", "level": "amber",
            "reason": "Getting stale — verify before relying on it"}


def build_receipt(item, ctx, state=None):
    it = _effective(item, state)
    v = verification_signal(it)
    o = owner_signal(it)
    s = scope_signal(it, ctx)
    return {
        "id": it["id"],
        "title": it.get("title", it["id"]),
        "kind": it.get("kind", "doc"),
        "source_type": it.get("source_type", "doc"),
        "version": it.get("version"),
        "body": it.get("body", ""),
        "superseded": it.get("superseded", False),
        "verification": v,
        "owner": o,
        "scope": s,
        "verdict": verdict(it, v, o, s),
    }


if __name__ == "__main__":
    from datetime import date, timedelta
    recent = (date.today() - timedelta(days=21)).isoformat()
    ctx = {"country": "BE", "client": None}
    proc = build_receipt({"id": "proc", "title": "Procedure", "owner": "An Peeters",
        "owner_team": "Payroll BE", "last_verified": recent, "last_updated": recent,
        "scope": {"countries": ["BE"], "clients": ["all"], "products": ["payroll"]}}, ctx)
    faq = build_receipt({"id": "faq", "title": "Old FAQ", "owner": None,
        "last_updated": "2022-03-14", "last_verified": None, "scope": {}}, ctx)
    nl = build_receipt({"id": "nl", "title": "NL Guide", "owner": "S", "last_verified": recent,
        "scope": {"countries": ["NL"], "clients": ["all"]}}, ctx)
    assert proc["verdict"]["label"] == "Reliable", proc["verdict"]
    assert faq["owner"]["label"] == "No owner"
    assert faq["verdict"]["label"] == "Use with care", faq["verdict"]
    assert nl["verdict"]["label"] == "Doesn't apply here", nl["verdict"]
    faq2 = build_receipt({"id": "faq", "title": "Old FAQ", "owner": None, "scope": {}}, ctx,
                         {"overrides": {"faq": {"superseded": True}}})
    assert faq2["verdict"]["label"] == "Superseded", faq2["verdict"]
    print("signals ok:", proc["verdict"], "|", faq["verdict"], "|", nl["verdict"])
