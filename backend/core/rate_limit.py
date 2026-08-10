"""
Simple in-memory per-IP rate limiter for the public AI endpoints.

The /generate/* endpoints call Groq on every request and are open to
logged-out users, so without a limit anyone could spam them and burn
through the free-tier quota. This keeps it to a sane number per minute.

Note: in-memory state is per-process. Fine for a single-instance MVP
(FastAPI Cloud Hobby = 1 instance). If you ever scale to multiple
instances, swap this for a Redis-backed limiter.
"""
import time
from collections import defaultdict

from fastapi import HTTPException, Request

_hits: dict[str, list[float]] = defaultdict(list)

LIMIT = 20      # max requests per IP per window
WINDOW = 60     # seconds


def rate_limit(request: Request):
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    _hits[ip] = [t for t in _hits[ip] if now - t < WINDOW]
    if len(_hits[ip]) >= LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Too many requests — slow down and try again in a minute.",
        )
    _hits[ip].append(now)
