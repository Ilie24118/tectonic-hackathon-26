"""Vercel serverless entrypoint. Vercel's Python runtime serves the WSGI `app`."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402  (exposed as the WSGI callable Vercel invokes)
