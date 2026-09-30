"""Vercel serverless entrypoint. Vercel's Python runtime serves the WSGI `app`."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app as _flask_app  # noqa: E402


def app(environ, start_response):
    # ponytail: Vercel's rewrite forwards PATH_INFO="/api/index"; map it back to the real route.
    path = environ.get("PATH_INFO", "")
    if path.startswith("/api/index"):
        environ["PATH_INFO"] = path[len("/api/index"):] or "/"
    return _flask_app(environ, start_response)
