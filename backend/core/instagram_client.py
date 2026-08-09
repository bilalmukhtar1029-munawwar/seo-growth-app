"""
Pulls Instagram post data (media, engagement, insights) via the Meta Graph
API for a connected Instagram Professional (Business/Creator) account.

Setup, one-time, per Meta App:
  1. Meta App -> Use cases -> add "Manage messaging & content on Instagram"
  2. Add permissions: instagram_basic, instagram_manage_insights,
     pages_show_list, pages_read_engagement
  3. App roles -> Roles -> Instagram Testers -> invite the IG account,
     then accept the invite inside Instagram (Settings -> Apps and
     websites -> Tester invites) — required until the app passes App
     Review, after which any user can connect via OAuth normally.
  4. The connected_accounts row for platform='instagram' needs:
       account_label   -> the Instagram Business Account ID (numeric string,
                           e.g. "17841477358635456" — NOT the Page ID)
       access_token    -> a long-lived User or Page access token
                           (60-day expiry; see refresh notes below)

Token refresh: long-lived tokens last ~60 days and can be refreshed any
time before they expire by calling the same fb_exchange_token flow again.
This module does not auto-refresh — that's a small addition to
core/auth.py's token-refresh routine (same place the Google OAuth refresh
presumably lives) once you're ready to wire it up. Until then, re-generate
manually via Graph API Explorer if a token expires during development.
"""
from datetime import datetime, timezone

import httpx

GRAPH_API_VERSION = "v21.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def fetch_ig_media(ig_business_account_id: str, access_token: str, limit: int = 25) -> list[dict]:
    """
    Returns the account's most recent posts with basic engagement counts
    (likes, comments come free on this call — no extra request needed).
    """
    resp = httpx.get(
        f"{GRAPH_API_BASE}/{ig_business_account_id}/media",
        params={
            "fields": "id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count",
            "limit": limit,
            "access_token": access_token,
        },
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json().get("data", [])


def fetch_ig_media_insights(media_id: str, media_type: str, access_token: str) -> dict:
    """
    Reach/impressions/saves need a separate call per post. Insights can
    fail on some older or unsupported media types (e.g. certain carousels)
    — that's expected, not a bug, so we degrade to an empty dict rather
    than raising.
    """
    metrics = "impressions,reach,saved"
    if media_type == "VIDEO":
        metrics += ",video_views"

    resp = httpx.get(
        f"{GRAPH_API_BASE}/{media_id}/insights",
        params={"metric": metrics, "access_token": access_token},
        timeout=20,
    )
    if resp.status_code != 200:
        return {}
    return {m["name"]: m["values"][0]["value"] for m in resp.json().get("data", [])}


def compute_posting_stats(posts: list[dict]) -> dict:
    """
    Pure logic on already-fetched data — no API calls. Mirrors the kind of
    summary numbers the SEO Snapshot card shows (posts_per_week feeds the
    "Infrequent Instagram posting" finding directly).
    """
    if not posts:
        return {"posts_per_week": 0, "avg_engagement": 0, "last_post_days_ago": None}

    timestamps = [datetime.fromisoformat(p["timestamp"]) for p in posts]
    now = datetime.now(timezone.utc)
    span_days = max((timestamps[0] - timestamps[-1]).days, 1)
    posts_per_week = round(len(posts) / span_days * 7, 1)

    engagement = [p.get("like_count", 0) + p.get("comments_count", 0) for p in posts]
    avg_engagement = round(sum(engagement) / len(engagement), 1)
    last_post_days_ago = (now - timestamps[0]).days

    return {
        "posts_per_week": posts_per_week,
        "avg_engagement": avg_engagement,
        "last_post_days_ago": last_post_days_ago,
    }
