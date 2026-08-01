"""
LinkedIn OAuth flow.

Same shape as `google_auth.py` and `meta_auth.py`. Two tiers of access:

  1. "Sign In with LinkedIn using OpenID Connect" — self-serve, no review,
     scopes `openid profile email`. Gets you the user's identity only, not
     posting history or engagement data.
  2. Real social data (org posts, follower stats, engagement) requires
     LinkedIn's Marketing Developer Platform, which needs your app to be
     reviewed and usually requires being a legitimate registered business —
     apply at https://www.linkedin.com/developers/apps, this is a manual
     step only you can do.

This module implements tier 1 (works today) with scopes structured so you
can extend to `r_organization_social` etc. once Marketing API access is
approved.
"""
import os

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from core.auth import get_admin_client

router = APIRouter()

# Extend with "r_organization_social,r_ads" etc. once Marketing API access
# is approved — those scopes will fail silently in the consent screen until then.
SCOPES = "openid profile email"


@router.get("/linkedin/login")
def linkedin_login(user_id: str | None = None):
    client_id = os.environ.get("LINKEDIN_CLIENT_ID")
    redirect_uri = os.environ.get(
        "LINKEDIN_OAUTH_REDIRECT_URI", "http://localhost:8000/auth/linkedin/callback"
    )
    if not client_id:
        raise HTTPException(
            status_code=500,
            detail="LINKEDIN_CLIENT_ID is not set. Create an app at linkedin.com/developers/apps.",
        )
    auth_url = (
        "https://www.linkedin.com/oauth/v2/authorization"
        f"?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}"
        f"&scope={SCOPES}&state={user_id or ''}"
    )
    return RedirectResponse(auth_url)


@router.get("/linkedin/callback")
def linkedin_callback(code: str, state: str | None = None):
    client_id = os.environ.get("LINKEDIN_CLIENT_ID")
    client_secret = os.environ.get("LINKEDIN_CLIENT_SECRET")
    redirect_uri = os.environ.get(
        "LINKEDIN_OAUTH_REDIRECT_URI", "http://localhost:8000/auth/linkedin/callback"
    )
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=500, detail="LINKEDIN_CLIENT_ID / LINKEDIN_CLIENT_SECRET are not set."
        )

    try:
        resp = httpx.post(
            "https://www.linkedin.com/oauth/v2/accessToken",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        access_token = resp.json()["access_token"]
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Token exchange failed: {e}")

    if not state:
        return {"status": "connected (not saved — no user_id in state)", "access_token": access_token}

    try:
        get_admin_client().table("connected_accounts").upsert(
            {
                "user_id": state,
                "platform": "linkedin",
                "access_token": access_token,
                "refresh_token": None,
            },
            on_conflict="user_id,platform",
        ).execute()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to save connected account: {e}")

    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
    return RedirectResponse(f"{frontend_url}?connected=linkedin")
