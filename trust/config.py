"""Where mutable data lives.

Locally this is the repo's data/ dir. On a read-only serverless filesystem (Vercel) we seed a
writable copy under /tmp on first use — ephemeral, wiped on cold starts, which is acceptable for a
demo (there's a /reset anyway). Override explicitly with DATA_DIR.
"""
import os
import shutil

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BUNDLED = os.path.join(_REPO, "data")

if os.environ.get("DATA_DIR"):
    DATA = os.environ["DATA_DIR"]
elif os.environ.get("VERCEL"):            # set automatically in the Vercel runtime
    DATA = "/tmp/trust-data"
else:
    DATA = _BUNDLED

# Seed a writable copy from the bundled (read-only) data on first use.
if DATA != _BUNDLED and not os.path.exists(DATA):
    shutil.copytree(_BUNDLED, DATA)

DOCS = os.path.join(DATA, "docs")
TEAMS = os.path.join(DATA, "teams")
os.makedirs(DOCS, exist_ok=True)
os.makedirs(TEAMS, exist_ok=True)
