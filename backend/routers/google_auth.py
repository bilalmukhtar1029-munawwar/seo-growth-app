"""
Google Search Console OAuth flow.

This is the one integration that doesn't need a platform "app review" —
Search Console API access works as soon as you register an OAuth client
in Google Cloud Console (see README "Getting your API keys from zero").

Flow:
  1. Frontend links to GET /auth/google/login?user_id=<supabase user id>
     -> redirects to Google's consent screen (user_id is threaded through
     as the OAuth `state` param).
  2. Google redirects back to GET /auth/google/callback with a `code` and
     the same `state`.
  3. We exchange the code for tokens and upsert them into the
     `connected_accounts` table for that user.
"""
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow

from core.auth import get_admin_client

router = APIRouter()

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


def _build_flow() -> Flow:
    client_id = os.environ.get("GOOGLE_SEARCH_CONSOLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_SEARCH_CONSOLE_CLIENT_SECRET")
    redirect_uri = os.environ.get(
        "GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8000/auth/google/callback"
    )
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=500,
            detail=(
                "GOOGLE_SEARCH_CONSOLE_CLIENT_ID / _SECRET are not set. "
                "See README 'Getting your API keys from zero'."
            ),
        )
    client_config = {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri],
        }
    }
    return Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=redirect_uri)


@router.get("/google/login")
def google_login(user_id: str | None = None):
    flow = _build_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=user_id or "",
    )
    return RedirectResponse(auth_url)


@router.get("/google/callback")
def google_callback(code: str, state: str | None = None):
    flow = _build_flow()
    flow.fetch_token(code=code)
    creds = flow.credentials

    if not state:
        # No logged-in user was threaded through — return tokens directly
        # so the flow is still testable without auth set up yet.
        return {
            "status": "connected (not saved — no user_id in state)",
            "access_token": creds.token,
            "refresh_token": creds.refresh_token,
        }

    try:
        get_admin_client().table("connected_accounts").upsert(
            {
                "user_id": state,
                "platform": "google_search_console",
                "access_token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_uri": creds.token_uri,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scopes": " ".join(creds.scopes) if creds.scopes else None,
            },
            on_conflict="user_id,platform",
        ).execute()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to save connected account: {e}")

    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
    return RedirectResponse(f"{frontend_url}?connected=google_search_console")


@router.post("/google/set-site")
def set_site_url(user_id: str, site_url: str):
    """
    Search Console OAuth doesn't tell us which property to monitor — the user
    picks it after connecting (e.g. "https://example.com/" or
    "sc-domain:example.com", must already be verified in their Search Console).
    Called by the frontend right after a successful connect.
    """
    try:
        get_admin_client().table("connected_accounts").update({"account_label": site_url}).eq(
            "user_id", user_id
        ).eq("platform", "google_search_console").execute()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to save site URL: {e}")
    return {"status": "saved", "site_url": site_url}
