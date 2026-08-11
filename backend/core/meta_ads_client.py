"""
Meta Ads (Facebook/Instagram) client — reads ad account + campaign data
through the Meta Marketing API (Graph API).

Everything degrades gracefully: if the token lacks ads_read, the account
isn't linked, or the API errors, functions return empty/None instead of
raising, so the router can fall back to the mock report.

Keep GRAPH_VERSION in sync with routers/meta_auth.py — Meta deprecates
old versions every few months.
"""
import httpx

GRAPH_API_BASE = "https://graph.facebook.com"
GRAPH_VERSION = "v21.0"

TIMEOUT = 20


def fetch_ad_accounts(access_token: str) -> list[dict]:
    """Ad accounts the token can see: /me/adaccounts."""
    try:
        resp = httpx.get(
            f"{GRAPH_API_BASE}/{GRAPH_VERSION}/me/adaccounts",
            params={
                "fields": "account_id,name,account_status,currency,amount_spent",
                "access_token": access_token,
                "limit": 25,
            },
            timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            return []
        return resp.json().get("data", [])
    except Exception:
        return []


def fetch_campaigns(ad_account_id: str, access_token: str) -> list[dict]:
    """Campaigns for an ad account, with statuses."""
    try:
        resp = httpx.get(
            f"{GRAPH_API_BASE}/{GRAPH_VERSION}/act_{ad_account_id}/campaigns",
            params={
                "fields": "id,name,status,effective_status,objective,daily_budget,lifetime_budget",
                "access_token": access_token,
                "limit": 100,
            },
            timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            return []
        return resp.json().get("data", [])
    except Exception:
        return []


def fetch_campaign_insights(ad_account_id: str, access_token: str) -> list[dict]:
    """
    Aggregate performance for the last 30 days, per campaign:
    spend, impressions, clicks, CTR, CPC, CPM, frequency, reach, actions.
    """
    try:
        resp = httpx.get(
            f"{GRAPH_API_BASE}/{GRAPH_VERSION}/act_{ad_account_id}/insights",
            params={
                "fields": (
                    "campaign_name,spend,impressions,clicks,ctr,cpc,cpm,"
                    "reach,frequency,actions,date_start,date_stop"
                ),
                "access_token": access_token,
                "date_preset": "last_30d",
                "level": "campaign",
                "limit": 100,
            },
            timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            return []
        return resp.json().get("data", [])
    except Exception:
        return []


def _num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def count_action(insight: dict, action_types: tuple[str, ...]) -> float:
    """Sum a specific action type (e.g. lead, offsite_conversion.purchase)."""
    total = 0.0
    for action in insight.get("actions", []) or []:
        if action.get("action_type") in action_types:
            total += _num(action.get("value"))
    return total


def summarize(insights: list[dict]) -> dict:
    """Roll campaign insights up into one comparable snapshot."""
    total_spend = sum(_num(i.get("spend")) for i in insights)
    total_impressions = sum(_num(i.get("impressions")) for i in insights)
    total_clicks = sum(_num(i.get("clicks")) for i in insights)
    total_leads = sum(
        count_action(i, ("lead", "leadgen_grouped", "offsite_conversion.fb_pixel_lead"))
        for i in insights
    )
    total_purchases = sum(
        count_action(i, ("offsite_conversion.purchase", "purchase"))
        for i in insights
    )
    total_reach = sum(_num(i.get("reach")) for i in insights)

    ctr = (total_clicks / total_impressions * 100) if total_impressions else 0.0
    cpc = (total_spend / total_clicks) if total_clicks else 0.0
    cpm = (total_spend / total_impressions * 1000) if total_impressions else 0.0
    cost_per_lead = (total_spend / total_leads) if total_leads else 0.0
    frequency = (total_impressions / total_reach) if total_reach else 0.0

    return {
        "spend": round(total_spend, 2),
        "impressions": int(total_impressions),
        "clicks": int(total_clicks),
        "ctr": round(ctr, 2),
        "cpc": round(cpc, 2),
        "cpm": round(cpm, 2),
        "reach": int(total_reach),
        "frequency": round(frequency, 2),
        "leads": int(total_leads),
        "purchases": int(total_purchases),
        "cost_per_lead": round(cost_per_lead, 2),
    }
