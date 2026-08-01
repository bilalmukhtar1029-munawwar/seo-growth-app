"""
SEO & Social Growth Engine — Backend API
FastAPI app entrypoint. Run with:
    uvicorn main:app --reload --port 8000
"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import content_gen, audit, google_auth, meta_auth, linkedin_auth, feed, internal

app = FastAPI(
    title="SEO & Social Growth Engine API",
    description="AI-powered SEO audit and content generation backend (Module 1 MVP).",
    version="0.1.0",
)

# Reads FRONTEND_URL from the environment so the same code works for local
# dev (defaults to localhost:3000) and production (set FRONTEND_URL to your
# Vercel URL) without editing this file.
allowed_origins = ["http://localhost:3000"]
if os.environ.get("FRONTEND_URL"):
    allowed_origins.append(os.environ["FRONTEND_URL"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(content_gen.router, prefix="/generate", tags=["Content Generation"])
app.include_router(audit.router, prefix="/audit", tags=["SEO Audit"])
app.include_router(google_auth.router, prefix="/auth", tags=["Google OAuth"])
app.include_router(meta_auth.router, prefix="/auth", tags=["Meta OAuth (needs App Review)"])
app.include_router(linkedin_auth.router, prefix="/auth", tags=["LinkedIn OAuth"])
app.include_router(feed.router, prefix="/feed", tags=["Auto-Suggested Content Feed"])
app.include_router(internal.router, prefix="/internal", tags=["Internal — free weekly scan trigger"])


@app.get("/")
def health_check():
    return {"status": "ok", "service": "seo-growth-engine-api"}
