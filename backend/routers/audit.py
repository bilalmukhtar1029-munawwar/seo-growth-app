"""
SEO/Social Audit endpoints — STUB.

This module is intentionally a stub. A real audit needs live data from:
  - Google Search Console API (search rankings, missing keywords)
  - Meta Graph API (Instagram/Facebook engagement, posting history)
  - LinkedIn Marketing API

Each of those requires the business to grant OAuth access, and Meta/LinkedIn
both require an app review before you can pull real user data in production
(see README "Phase 2" for the process). Wire the real calls in here once
those OAuth flows are in place.
"""
from fastapi import APIRouter, HTTPException
from datetime import date, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from core.ai_client import generate_json

router = APIRouter()


def _last_30_days() -> tuple[str, str]:
    end = date.today() - timedelta(days=3)  # GSC data has a ~2-3 day lag
    start = end - timedelta(days=30)
    return start.isoformat(), end.isoformat()

MOCK_ACCOUNT_DATA = {
    "note": "Replace with real Search Console / Meta Graph / LinkedIn data once connected.",
    "top_pages": [{"url": "/products/leather-shoes", "clicks": 340, "avg_position": 14.2}],
    "instagram_last_post_days_ago": 32,
}


@router.get("/mock-report")
def mock_report():
    """
    Demonstrates the audit → recommendation flow using placeholder data,
    so the frontend dashboard has something real to render before Phase 2
    (live integrations) is built.
    """
    data = generate_json(
        system_prompt=(
            "You are a world-class SEO and social media auditor. Be specific and actionable."
        ),
        user_prompt=(
            f"Here is a business's connected-account data (sample/mock data for demo purposes): "
            f"{MOCK_ACCOUNT_DATA}\n\n"
            "Analyze it and return JSON with keys: "
            '"seo_score" (integer 0-100), '
            '"findings" (array of 3-5 short strings describing specific problems), '
            '"recommended_actions" (array of 3-5 short, specific, actionable strings).'
        ),
    )
    return data


@router.get("/search-console-report")
def search_console_report(site_url: str, access_token: str):
    """
    Real Phase-2 endpoint: pulls actual Search Console data and runs it
    through the same AI analysis as the mock report.

    `site_url` must be a property already verified in the user's Search
    Console (e.g. "https://example.com/" or "sc-domain:example.com").
    `access_token` comes from the /auth/google/login -> /auth/google/callback
    flow (swap this for a lookup from `connected_accounts` once user auth
    and token storage are wired up).
    """
    try:
        creds = Credentials(token=access_token)
        service = build("searchconsole", "v1", credentials=creds)
        start_date, end_date = _last_30_days()
        response = (
            service.searchanalytics()
            .query(
                siteUrl=site_url,
                body={
                    "startDate": start_date,
                    "endDate": end_date,
                    "dimensions": ["page", "query"],
                    "rowLimit": 20,
                },
            )
            .execute()
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Search Console fetch failed: {e}")

    rows = response.get("rows", [])
    data = generate_json(
        system_prompt="You are a world-class SEO auditor. Be specific and actionable.",
        user_prompt=(
            f"Here is real Google Search Console data (page/query, clicks, impressions, "
            f"CTR, position) for the last 30 days: {rows}\n\n"
            "Analyze it and return JSON with keys: "
            '"seo_score" (integer 0-100), '
            '"findings" (array of 3-5 short strings describing specific problems), '
            '"recommended_actions" (array of 3-5 short, specific, actionable strings).'
        ),
    )
    return data
