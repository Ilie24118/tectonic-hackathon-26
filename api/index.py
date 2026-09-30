"""Vercel serverless entrypoint. @vercel/python serves the WSGI `app`.

Legacy `routes` (see vercel.json) pass the original request path through as PATH_INFO,
so Flask matches its routes directly — no prefix rewriting needed.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402,F401
