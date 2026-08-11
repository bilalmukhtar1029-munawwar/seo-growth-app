"""
SEO/Social Audit endpoints.

/mock-report             -> demo flow with placeholder data
/search-console-report   -> REAL: pulls the logged-in user's stored Search
                            Console account, fetches live ranking data,
                            runs it through the AI, and saves the report.

Meta/LinkedIn live data still needs their platform app reviews (see README)
— those pull requests are external approval steps, not code.
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import date, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from core.ai_client import generate_json
from core.auth import get_current_user_id, get_admin_client

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


def _load_gsc_account(db, user_id: str) -> dict:
    """Fetches the user's stored Search Console connection and rebuilds
    Google credentials with the refresh token, so expired access tokens
    auto-refresh instead of 401ing."""
    result = (
        db.table("connected_accounts")
        .select("*")
        .eq("user_id", user_id)
        .eq("platform", "google_search_console")
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="No Search Console account connected. Use 'Connect Search Console' first.",
        )
    account = result.data[0]
    if not account.get("account_label"):
        raise HTTPException(
            status_code=400,
            detail="No Search Console site chosen yet — set it right after connecting.",
        )
    creds = Credentials(
        token=account["access_token"],
        refresh_token=account.get("refresh_token"),
        token_uri=account.get("token_uri"),
        client_id=account.get("client_id"),
        client_secret=account.get("client_secret"),
        scopes=account.get("scopes", "").split(" ") if account.get("scopes") else None,
    )
    return account, creds


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
def search_console_report(user_id: str = Depends(get_current_user_id)):
    """
    Real audit: pulls the logged-in user's stored Search Console account,
    fetches actual page/query ranking data for the last 30 days, runs it
    through the AI, saves the report to seo_reports, and returns it.
    """
    db = get_admin_client()
    account, creds = _load_gsc_account(db, user_id)

    try:
        service = build("searchconsole", "v1", credentials=creds)
        start_date, end_date = _last_30_days()
        response = (
            service.searchanalytics()
            .query(
                siteUrl=account["account_label"],
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
    try:
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
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI analysis failed: {e}")

    # Best-effort save of the report for history (never fails the request).
    try:
        db.table("seo_reports").insert(
            {
                "user_id": user_id,
                "seo_score": data.get("seo_score"),
                "findings": data.get("findings", []),
                "recommended_actions": data.get("recommended_actions", []),
            }
        ).execute()
    except Exception:
        pass

    data["site_url"] = account["account_label"]
    return data
