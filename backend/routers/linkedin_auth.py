"""
LinkedIn OAuth flow.

Same shape as `google_auth.py` and `meta_auth.py`. Two tiers of access:

  1. "Sign In with LinkedIn using OpenID Connect" — self-serve, no review,
     scopes `openid profile email r_refresh_token`. Gets you the user's
     identity (name, email, picture) plus a refreshable access token.
     No posting history or engagement data.
  2. Real social data (org posts, follower stats, engagement) requires
     LinkedIn's Marketing Developer Platform, which needs your app to be
     reviewed and usually requires being a legitimate registered business —
     apply at https://www.linkedin.com/developers/apps, this is a manual
     step only you can do.

This module implements tier 1 (works today) with scopes structured so you
can extend to `r_organization_social` etc. once Marketing API access is
approved. Beyond the basic connect, it:

  - fetches the member's profile (name + email) and stores it as
    `account_label` so the UI can show *who* is connected,
  - stores the refresh token and exposes POST /linkedin/refresh so the
    short-lived access token can be renewed without re-consent,
  - exposes GET /linkedin/status (for the header UI) and
    DELETE /linkedin/disconnect,
  - redirects back to the frontend with ?connected=linkedin or
    ?error=<reason> instead of dumping raw JSON on failure.
"""
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from core.auth import get_admin_client, get_current_user_id

router = APIRouter()

# r_refresh_token keeps the access token renewable without asking the user
# to re-consent every ~60 days. Extend with "r_organization_social,r_ads"
# etc. once Marketing API access is approved — those scopes will fail
# silently in the consent screen until then.
SCOPES = "openid profile email r_refresh_token"

FRONTEND_ERROR_PARAM = "error"


def _frontend_url() -> str:
    return os.environ.get("FRONTEND_URL", "http://localhost:3000")


def _env_creds():
    client_id = os.environ.get("LINKEDIN_CLIENT_ID")
    client_secret = os.environ.get("LINKEDIN_CLIENT_SECRET")
    redirect_uri = os.environ.get(
        "LINKEDIN_OAUTH_REDIRECT_URI", "http://localhost:8000/auth/linkedin/callback"
    )
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=500,
            detail=(
                "LINKEDIN_CLIENT_ID / LINKEDIN_CLIENT_SECRET are not set. "
                "Create an app at linkedin.com/developers/apps (see README)."
            ),
        )
    return client_id, client_secret, redirect_uri


@router.get("/linkedin/login")
def linkedin_login(user_id: str | None = None):
    try:
        client_id, _, redirect_uri = _env_creds()
    except HTTPException:
        # Keys not added yet — send the user back to the app with a clear
        # banner instead of a raw JSON 500 in their browser.
        return RedirectResponse(
            f"{_frontend_url()}?{FRONTEND_ERROR_PARAM}=linkedin_not_configured"
        )
    auth_url = (
        "https://www.linkedin.com/oauth/v2/authorization"
        f"?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}"
        f"&scope={SCOPES}&state={user_id or ''}"
    )
    return RedirectResponse(auth_url)


def _fetch_member_profile(access_token: str) -> dict:
    """Name/email/picture via LinkedIn's OpenID Connect userinfo endpoint."""
    resp = httpx.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def _format_account_label(profile: dict) -> str:
    """'Jane Doe (jane@example.com)' — or whichever parts we actually got."""
    name = profile.get("name") or " ".join(
        filter(None, [profile.get("given_name"), profile.get("family_name")])
    )
    email = profile.get("email")
    if name and email:
        return f"{name} ({email})"
    return name or email or "LinkedIn member"


@router.get("/linkedin/callback")
def linkedin_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
):
    """
    LinkedIn redirects here after the user logs in. On success we get
    `code`; on any failure (cancelled, denied, bad scope...) we get
    `error` instead — handle both and bounce back to the frontend with
    a friendly `?error=` slug instead of a raw JSON 422.
    """
    client_id, client_secret, redirect_uri = _env_creds()
    frontend_url = _frontend_url()

    if error or not code:
        if error in ("invalid_scope_error", "unauthorized_scope_error"):
            reason = "linkedin_invalid_scope"
        elif error in ("user_cancelled_authorize", "access_denied"):
            reason = "linkedin_cancelled"
        else:
            reason = "linkedin_denied"
        # error_description is often "Unknown" from LinkedIn; log it for
        # debugging but don't surface raw text to the user.
        if error_description:
            print(f"LinkedIn callback error: {error} - {error_description}")
        return RedirectResponse(f"{frontend_url}?error={reason}")

    if not state:
        # No logged-in user was threaded through — nothing to attach the
        # connection to, so fail cleanly back to the frontend.
        return RedirectResponse(f"{frontend_url}?error=linkedin_no_user")

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
            timeout=15,
        )
        resp.raise_for_status()
        token_data = resp.json()
        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token")

        profile = _fetch_member_profile(access_token)

        get_admin_client().table("connected_accounts").upsert(
            {
                "user_id": state,
                "platform": "linkedin",
                "access_token": access_token,
                "refresh_token": refresh_token,
                "account_label": _format_account_label(profile),
            },
            on_conflict="user_id,platform",
        ).execute()
    except Exception:
        # Swallow details — the frontend just needs to know it failed and
        # offer to retry. (Details are visible in server logs if needed.)
        return RedirectResponse(f"{frontend_url}?{FRONTEND_ERROR_PARAM}=linkedin_auth_failed")

    return RedirectResponse(f"{frontend_url}?connected=linkedin")


@router.get("/linkedin/config-status")
def linkedin_config_status(user_id: str = Depends(get_current_user_id)):
    """
    True/false flags for what's configured — check this from the app after a
    deploy to confirm the LinkedIn keys made it to the server, without digging
    in server logs. Never reveals the secret values.
    """
    return {
        "client_id_set": bool(os.environ.get("LINKEDIN_CLIENT_ID")),
        "client_secret_set": bool(os.environ.get("LINKEDIN_CLIENT_SECRET")),
        "redirect_uri": os.environ.get(
            "LINKEDIN_OAUTH_REDIRECT_URI",
            "http://localhost:8000/auth/linkedin/callback",
        ),
    }


@router.get("/linkedin/status")
def linkedin_status(user_id: str = Depends(get_current_user_id)):
    """What the header UI shows: is LinkedIn connected, and as whom?"""
    try:
        result = (
            get_admin_client()
            .table("connected_accounts")
            .select("account_label, connected_at")
            .eq("user_id", user_id)
            .eq("platform", "linkedin")
            .execute()
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to load LinkedIn status: {e}")
    if not result.data:
        return {"connected": False}
    row = result.data[0]
    return {
        "connected": True,
        "account_label": row.get("account_label"),
        "connected_at": row.get("connected_at"),
    }


@router.post("/linkedin/refresh")
def linkedin_refresh(user_id: str = Depends(get_current_user_id)):
    """
    LinkedIn access tokens are short-lived (~60 days); the refresh token
    (saved on connect thanks to the r_refresh_token scope) renews it
    without the user redoing consent. Called before any LinkedIn API use.
    """
    client_id, client_secret, _ = _env_creds()
    db = get_admin_client()
    try:
        result = (
            db.table("connected_accounts")
            .select("refresh_token")
            .eq("user_id", user_id)
            .eq("platform", "linkedin")
            .execute()
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to load LinkedIn account: {e}")

    if not result.data:
        raise HTTPException(status_code=404, detail="LinkedIn is not connected.")
    refresh_token = result.data[0].get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=400,
            detail="No refresh token stored — reconnect LinkedIn once.",
        )

    try:
        resp = httpx.post(
            "https://www.linkedin.com/oauth/v2/accessToken",
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        resp.raise_for_status()
        token_data = resp.json()
        new_access = token_data["access_token"]
        new_refresh = token_data.get("refresh_token", refresh_token)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"LinkedIn token refresh failed: {e}")

    try:
        db.table("connected_accounts").update(
            {"access_token": new_access, "refresh_token": new_refresh}
        ).eq("user_id", user_id).eq("platform", "linkedin").execute()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to save refreshed token: {e}")

    return {"status": "refreshed"}


@router.delete("/linkedin/disconnect")
def linkedin_disconnect(user_id: str = Depends(get_current_user_id)):
    try:
        (
            get_admin_client()
            .table("connected_accounts")
            .delete()
            .eq("user_id", user_id)
            .eq("platform", "linkedin")
            .execute()
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to disconnect LinkedIn: {e}")
    return {"status": "disconnected"}
