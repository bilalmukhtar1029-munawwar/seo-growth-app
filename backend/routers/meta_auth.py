"""
Meta (Instagram/Facebook) OAuth flow.

STRUCTURE IS READY, but this cannot go live until you complete Meta's App
Review — this is a manual step only you can do, on Meta's own developer
dashboard, and typically takes days to weeks:
  1. Create an app at https://developers.facebook.com/apps
  2. Add the "Instagram Graph API" and/or "Facebook Login" products
  3. Submit for App Review requesting the scopes below — Meta requires a
     screencast demo of your app using each permission before approving
  4. Until approved, this flow only works for accounts added as "Testers"
     under Roles in your app dashboard (fine for your own development)

Once approved, the OAuth mechanics below are the same shape as
`google_auth.py` — login redirects to Meta's consent screen, callback
exchanges the code for a token and upserts it into `connected_accounts`.
"""
import os

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from core.auth import get_admin_client

router = APIRouter()

# instagram_basic + instagram_manage_insights cover reading posts/engagement;
# pages_show_list is required to find the Instagram Business account behind a Page.
SCOPES = "instagram_basic,instagram_manage_insights,pages_show_list"
# Keep in sync with core/instagram_client.py — Meta deprecates old versions.
GRAPH_VERSION = "v21.0"


@router.get("/meta/login")
def meta_login(user_id: str | None = None):
    app_id = os.environ.get("META_APP_ID")
    redirect_uri = os.environ.get(
        "META_OAUTH_REDIRECT_URI", "http://localhost:8000/auth/meta/callback"
    )
    if not app_id:
        raise HTTPException(
            status_code=500,
            detail="META_APP_ID is not set. Create an app at developers.facebook.com/apps first.",
        )
    auth_url = (
        f"https://www.facebook.com/{GRAPH_VERSION}/dialog/oauth"
        f"?client_id={app_id}&redirect_uri={redirect_uri}&scope={SCOPES}"
        f"&state={user_id or ''}"
    )
    return RedirectResponse(auth_url)


@router.get("/meta/callback")
def meta_callback(code: str, state: str | None = None):
    app_id = os.environ.get("META_APP_ID")
    app_secret = os.environ.get("META_APP_SECRET")
    redirect_uri = os.environ.get(
        "META_OAUTH_REDIRECT_URI", "http://localhost:8000/auth/meta/callback"
    )
    if not app_id or not app_secret:
        raise HTTPException(status_code=500, detail="META_APP_ID / META_APP_SECRET are not set.")

    token_url = f"https://graph.facebook.com/{GRAPH_VERSION}/oauth/access_token"
    try:
        resp = httpx.get(
            token_url,
            params={
                "client_id": app_id,
                "client_secret": app_secret,
                "redirect_uri": redirect_uri,
                "code": code,
            },
        )
        resp.raise_for_status()
        access_token = resp.json()["access_token"]
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Token exchange failed: {e}. If your app hasn't passed App Review yet, "
                "make sure this Facebook account is added as a Tester in your app's Roles."
            ),
        )

    if not state:
        return {"status": "connected (not saved — no user_id in state)", "access_token": access_token}

    try:
        get_admin_client().table("connected_accounts").upsert(
            {
                "user_id": state,
                "platform": "instagram",
                "access_token": access_token,
                "refresh_token": None,
            },
            on_conflict="user_id,platform",
        ).execute()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to save connected account: {e}")

    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
    return RedirectResponse(f"{frontend_url}?connected=instagram")
