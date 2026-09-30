"""Load imported PDFs + Teams messages and run BM25 retrieval over them.

Docs are PDFs the user drops in data/docs/. On load we extract the text (pypdf) and, once
per PDF, extract metadata with the LLM into a cached sidecar `<name>.meta.json`. Edit that
sidecar by hand to fix anything the LLM could not know (owner, verified date, scope).
"""
import glob
import json
import os
import re

from pypdf import PdfReader
from rank_bm25 import BM25Okapi

from trust.config import DOCS, TEAMS


def _empty_scope():
    return {"countries": [], "clients": [], "products": []}


def pdf_text(path):
    try:
        return "\n".join((p.extract_text() or "") for p in PdfReader(path).pages).strip()
    except Exception as e:  # unreadable/encrypted PDF — don't crash the whole corpus
        return f"(could not read PDF: {e})"


def _sidecar(pdf_path):
    return os.path.splitext(pdf_path)[0] + ".meta.json"


def ingest_pdf(pdf_path, force=False):
    """Return metadata dict for a PDF, extracting + caching a sidecar if needed."""
    from trust import llm
    side = _sidecar(pdf_path)
    text = pdf_text(pdf_path)
    fresh = os.path.exists(side) and os.path.getmtime(side) >= os.path.getmtime(pdf_path)
    if fresh and not force:
        meta = json.load(open(side, encoding="utf-8"))
    else:
        meta = llm.extract_metadata(text, os.path.basename(pdf_path))
        json.dump(meta, open(side, "w", encoding="utf-8"), indent=2)
    scope = meta.get("scope") or {}
    meta["scope"] = {"countries": scope.get("countries") or [],
                     "clients": scope.get("clients") or [],
                     "products": scope.get("products") or []}
    meta["id"] = os.path.splitext(os.path.basename(pdf_path))[0]
    meta["kind"] = "doc"
    meta["body"] = text
    meta.setdefault("title", meta["id"])
    meta.setdefault("source_type", "document")
    for k in ("owner", "owner_team", "last_updated", "last_verified", "version"):
        meta.setdefault(k, None)
    return meta


def _load_docs():
    return [ingest_pdf(p) for p in sorted(glob.glob(os.path.join(DOCS, "*.pdf")))]


def _load_teams():
    msgs = []
    for path in sorted(glob.glob(os.path.join(TEAMS, "*.json"))):
        for m in json.load(open(path, encoding="utf-8")):
            msgs.append({
                "id": m["id"], "title": f"Teams {m['channel']} — {m['author']}",
                "kind": "teams", "source_type": "teams",
                "channel": m["channel"], "author": m["author"],
                "owner": None, "owner_team": None,
                "last_updated": m["timestamp"][:10], "last_verified": None, "version": None,
                "scope": _empty_scope(), "body": m["text"], "reactions": m.get("reactions", []),
            })
    return msgs


def _tokenize(text):
    return re.findall(r"[a-z0-9]+", text.lower())


class Index:
    def __init__(self):
        self.items = _load_docs() + _load_teams()
        corpus = [_tokenize((it.get("title", "") + " ") * 2 + it.get("body", ""))
                  for it in self.items] or [[""]]
        self.bm25 = BM25Okapi(corpus)

    def by_id(self, doc_id):
        return next((it for it in self.items if it["id"] == doc_id), None)

    def search(self, query, n_docs=4, n_teams=2):
        if not self.items:
            return []
        scores = self.bm25.get_scores(_tokenize(query))
        ranked = [it for score, it in
                  sorted(zip(scores, self.items), key=lambda x: x[0], reverse=True) if score > 0]
        docs = [it for it in ranked if it["kind"] == "doc"][:n_docs]
        teams = [it for it in ranked if it["kind"] == "teams"][:n_teams]
        keep = {it["id"] for it in docs + teams}
        return [it for it in ranked if it["id"] in keep]


def get_index():
    return Index()


if __name__ == "__main__":
    idx = get_index()
    print(f"loaded {len([i for i in idx.items if i['kind']=='doc'])} PDF docs,",
          f"{len([i for i in idx.items if i['kind']=='teams'])} teams messages")
    if idx.items:
        print("sample:", idx.items[0]["id"], "-", idx.items[0].get("title"))
