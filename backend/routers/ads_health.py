"""
Ads Health endpoints.

/ads/health       -> real data when a Meta ad account is connected,
                     falls back to the mock report otherwise
/ads/mock-report  -> demo report for the panel before Meta is connected

Both return the same shape: { ads_score, label, findings,
recommended_actions, summary } so the frontend renders one component.
"""
from fastapi import APIRouter, Depends

from core.ads_scoring import score_ads, mock_ads_report
from core.ai_client import generate_json
from core.auth import get_admin_client, get_current_user_id
from core.meta_ads_client import (
    fetch_ad_accounts,
    fetch_campaigns,
    fetch_campaign_insights,
    summarize,
)

router = APIRouter()


def _load_meta_account(db, user_id: str) -> dict | None:
    """Finds the user's stored Meta/Instagram connection (ad-capable token)."""
    result = (
        db.table("connected_accounts")
        .select("*")
        .eq("user_id", user_id)
        .in_("platform", ("instagram", "meta_ads"))
        .execute()
    )
    if not result.data:
        return None
    return result.data[0]


def _ai_commentary(result: dict, goal: str) -> dict:
    """Enhances the rule-based report with a short AI-written narrative.

    Best-effort: if Groq fails we return the plain report — the panel
    never breaks because of AI downtime.
    """
    try:
        commentary = generate_json(
            system_prompt=(
                "You are a paid-media strategist. Read the ads health JSON and write "
                "a 2-3 sentence plain-English summary of what the numbers mean for the "
                "business goal. Return JSON with one key: 'commentary' (string)."
            ),
            user_prompt=f"Goal: {goal}\n\nAds health JSON: {result}",
            max_tokens=300,
        )
        if isinstance(commentary, dict) and commentary.get("commentary"):
            result["commentary"] = commentary["commentary"]
    except Exception:
        pass
    return result


@router.get("/health")
def ads_health(user_id: str = Depends(get_current_user_id), goal: str = "sales"):
    """Real ads health from the connected Meta ad account (mock fallback)."""
    db = get_admin_client()
    account = _load_meta_account(db, user_id)
    if not account or not account.get("access_token"):
        result = mock_ads_report()
        return _ai_commentary(result, goal)

    access_token = account["access_token"]
    ad_accounts = fetch_ad_accounts(access_token)
    account_label = account.get("account_label")

    # Prefer the stored ad account id; otherwise use the first the token can see.
    ad_account_id = None
    if account_label and account_label.startswith("act_"):
        ad_account_id = account_label[4:]
    elif ad_accounts:
        ad_account_id = ad_accounts[0].get("account_id")

    if not ad_account_id:
        result = mock_ads_report()
        result["note"] = (
            "Connected, but no ad account found on this token. "
            "Make sure the app has ads_read permission and the user has ad access."
        )
        return _ai_commentary(result, goal)

    campaigns = fetch_campaigns(ad_account_id, access_token)
    insights = fetch_campaign_insights(ad_account_id, access_token)
    snapshot = summarize(insights) if insights else {
        "spend": 0, "impressions": 0, "clicks": 0, "ctr": 0, "cpc": 0,
        "cpm": 0, "reach": 0, "frequency": 0, "leads": 0, "purchases": 0,
        "cost_per_lead": 0,
    }

    result = score_ads(snapshot, campaigns, goal=goal)
    result["is_mock"] = False
    result["ad_account_id"] = ad_account_id
    return _ai_commentary(result, goal)


@router.get("/mock-report")
def ads_mock_report():
    """Demo ads health report — always works, no Meta connection needed."""
    return _ai_commentary(mock_ads_report(), "sales")
