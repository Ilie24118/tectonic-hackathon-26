"""Load docs + Teams messages and run BM25 retrieval over them."""
import glob
import json
import os
import re

import yaml
from rank_bm25 import BM25Okapi

DATA = os.path.join(os.path.dirname(__file__), "..", "data")

_FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


def _load_docs():
    docs = []
    for path in sorted(glob.glob(os.path.join(DATA, "docs", "*.md"))):
        raw = open(path, encoding="utf-8").read()
        m = _FRONTMATTER.match(raw)
        if not m:
            continue
        meta = yaml.safe_load(m.group(1)) or {}
        body = m.group(2).strip()
        meta["body"] = body
        meta["kind"] = "doc"
        scope = meta.get("scope") or {}
        meta["scope"] = {
            "countries": scope.get("countries") or [],
            "clients": scope.get("clients") or [],
            "products": scope.get("products") or [],
        }
        docs.append(meta)
    return docs


def _load_teams():
    msgs = []
    for path in sorted(glob.glob(os.path.join(DATA, "teams", "*.json"))):
        for m in json.load(open(path, encoding="utf-8")):
            msgs.append({
                "id": m["id"],
                "title": f"Teams {m['channel']} — {m['author']}",
                "kind": "teams",
                "source_type": "teams",
                "channel": m["channel"],
                "author": m["author"],
                "owner": None,
                "owner_team": None,
                "last_updated": m["timestamp"][:10],
                "last_verified": None,
                "version": None,
                "scope": {"countries": [], "clients": [], "products": []},
                "body": m["text"],
                "reactions": m.get("reactions", []),
            })
    return msgs


def _tokenize(text):
    return re.findall(r"[a-z0-9]+", text.lower())


class Index:
    def __init__(self):
        self.items = _load_docs() + _load_teams()
        corpus = [
            _tokenize((it.get("title", "") + " ") * 2 + it.get("body", ""))
            for it in self.items
        ]
        self.bm25 = BM25Okapi(corpus)

    def by_id(self, doc_id):
        return next((it for it in self.items if it["id"] == doc_id), None)

    def search(self, query, n_docs=4, n_teams=2):
        # Split doc vs teams quotas so short Teams chatter can't crowd out the real docs,
        # and skip archived duplicates (they exist for history/radar, not for answering).
        scores = self.bm25.get_scores(_tokenize(query))
        ranked = [it for score, it in
                  sorted(zip(scores, self.items), key=lambda x: x[0], reverse=True)
                  if score > 0]
        docs = [it for it in ranked if it["kind"] == "doc"
                and not it["id"].endswith("-archive")][:n_docs]
        teams = [it for it in ranked if it["kind"] == "teams"][:n_teams]
        # Preserve overall relevance order for display.
        keep = {it["id"] for it in docs + teams}
        return [it for it in ranked if it["id"] in keep]


# Rebuilt on each request so owner edits (appended text) are re-indexed. Corpus is tiny.
def get_index():
    return Index()


if __name__ == "__main__":
    idx = get_index()
    q = "How is double holiday pay calculated for a part-time employee who leaves mid-year? " \
        "Client: Brouwerij Vandamme (BE)."
    hits = idx.search(q)
    got = {h["id"] for h in hits}
    for needed in ["be-holiday-pay-procedure", "payroll-faq-old-sharepoint",
                   "nl-holiday-allowance-guide", "tm-be-001"]:
        assert needed in got, f"planted source {needed} missing from {got}"
    assert "be-holiday-pay-v3-archive" not in got, "archived duplicate should be excluded"
    print("retrieval ok:", [h["id"] for h in hits])
