"""
Verifies the Supabase-issued JWT sent by the frontend and extracts the user id.

The frontend sends `Authorization: Bearer <supabase access token>` on every
request once a user is logged in. We validate it against Supabase itself
(rather than decoding the JWT locally) — simpler to get right, one extra
network call per request.
"""
import os

from fastapi import Header, HTTPException
from supabase import create_client, Client

_admin_client: Client | None = None


def get_admin_client() -> Client:
    """Service-role client — bypasses RLS, used for server-side writes."""
    global _admin_client
    if _admin_client is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are not set in backend/.env"
            )
        _admin_client = create_client(url, key)
    return _admin_client


async def get_current_user_id(authorization: str = Header(default=None)) -> str:
    """
    FastAPI dependency. Use as: `user_id: str = Depends(get_current_user_id)`.
    Raises 401 if the token is missing or invalid.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    client = get_admin_client()
    try:
        user_response = client.auth.get_user(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return user_response.user.id


async def get_optional_user_id(authorization: str = Header(default=None)) -> str | None:
    """Same as above, but returns None instead of raising — for endpoints that
    work with or without login (e.g. the generator works logged-out, just
    doesn't save)."""
    if not authorization:
        return None
    try:
        return await get_current_user_id(authorization)
    except HTTPException:
        return None
