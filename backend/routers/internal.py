"""
Lets a free external cron service (cron-job.org, no card needed) trigger the
weekly content-gap scan by calling this endpoint on a schedule — replacing
the paid Celery worker entirely.

Protected by a shared secret so random visitors can't trigger it and burn
through your Groq free-tier limits. Set INTERNAL_SCAN_SECRET in your backend
env, and configure your cron job to send it as a header.
"""
import os

from fastapi import APIRouter, HTTPException, Header

from core.tasks import scan_all_users_for_content_gaps

router = APIRouter()


@router.post("/run-weekly-scan")
def run_weekly_scan(x_scan_secret: str = Header(default=None)):
    expected = os.environ.get("INTERNAL_SCAN_SECRET")
    if not expected:
        raise HTTPException(
            status_code=500,
            detail="INTERNAL_SCAN_SECRET is not set on the server — set one before enabling this.",
        )
    if x_scan_secret != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Scan-Secret header.")

    results = scan_all_users_for_content_gaps()
    return {"status": "completed", "results": results}
