"""
Lets a free external cron service (cron-job.org, no card needed) trigger the
weekly content-gap scan by calling this endpoint on a schedule — replacing
the paid Celery worker entirely.
Protected by a shared secret so random visitors can't trigger it and burn
through your Groq free-tier limits. Set INTERNAL_SCAN_SECRET in your backend
env, and configure your cron job to send it as a header.

/run-weekly-scan       -> Search Console scan + auto content drafts
/run-instagram-scan    -> Instagram post/engagement scan, updates
                          instagram_snapshots (feeds the SEO Snapshot card)
Both share the same X-Scan-Secret protection.
"""
import os
from fastapi import APIRouter, HTTPException, Header
from core.tasks import (
    scan_all_users_for_content_gaps,
    scan_all_users_linkedin_suggestions,
    scan_all_users_video_ads,
    scan_all_instagram_users,
)

router = APIRouter()


def _check_secret(x_scan_secret: str):
    expected = os.environ.get("INTERNAL_SCAN_SECRET")
    if not expected:
        raise HTTPException(
            status_code=500,
            detail="INTERNAL_SCAN_SECRET is not set on the server — set one before enabling this.",
        )
    if x_scan_secret != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Scan-Secret header.")


@router.post("/run-weekly-scan")
def run_weekly_scan(x_scan_secret: str = Header(default=None)):
    _check_secret(x_scan_secret)
    results = {
        "search_console": scan_all_users_for_content_gaps(),
        "linkedin": scan_all_users_linkedin_suggestions(),
        "video_ads": scan_all_users_video_ads(),
    }
    return {"status": "completed", "results": results}


@router.post("/run-instagram-scan")
def run_instagram_scan(x_scan_secret: str = Header(default=None)):
    _check_secret(x_scan_secret)
    results = scan_all_instagram_users()
    return {"status": "completed", "results": results}
