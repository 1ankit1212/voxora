"""
DubKaro — Auth Middleware
Supports two auth modes:
1. Supabase JWT (Flutter app users)
2. API Key (Developer API access)
"""

import time
import hashlib
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY, API_KEY_PLANS

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
security = HTTPBearer(auto_error=False)


def hash_api_key(key: str) -> str:
    """API key ka SHA-256 hash banao."""
    return hashlib.sha256(key.encode()).hexdigest()


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Auth check — either Supabase JWT or API key.
    Returns dict with user info.
    """

    # ── Check for API Key in header ──
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return await _validate_api_key(api_key, request)

    # ── Check for Supabase JWT ──
    if credentials:
        return await _validate_jwt(credentials.credentials)

    raise HTTPException(
        status_code=401,
        detail="Authentication required. Provide Supabase JWT or X-API-Key header.",
    )


async def _validate_jwt(token: str) -> dict:
    """Supabase JWT validate karo."""
    try:
        user_response = supabase.auth.get_user(token)
        if not user_response or not user_response.user:
            raise HTTPException(401, "Invalid or expired token")

        user = user_response.user

        # Profile fetch karo
        profile = supabase.table("users").select("*").eq(
            "id", user.id
        ).maybe_single().execute()

        return {
            "auth_type": "jwt",
            "user_id": user.id,
            "email": user.email,
            "plan": profile.data.get("plan", "free") if profile.data else "free",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(401, f"Token validation failed: {str(e)}")


async def _validate_api_key(api_key: str, request: Request) -> dict:
    """API key validate karo with rate limiting + token check."""

    key_hash = hash_api_key(api_key)

    # DB se key fetch karo
    result = supabase.table("api_keys").select("*").eq(
        "secret_hash", key_hash
    ).eq("is_active", True).maybe_single().execute()

    if not result.data:
        raise HTTPException(401, "Invalid or inactive API key")

    key_data = result.data

    # ── Token limit check ──
    if key_data["tokens_used"] >= key_data["tokens_total"]:
        raise HTTPException(
            429,
            f"Token limit exhausted. Used {key_data['tokens_used']}/{key_data['tokens_total']}. "
            f"Upgrade your plan for more tokens.",
        )

    # ── Rate limit check ──
    plan_config = API_KEY_PLANS.get(key_data["plan"], API_KEY_PLANS["free"])
    rate_limit = plan_config["rate_limit_per_min"]

    one_min_ago = time.time() - 60
    recent_usage = supabase.table("api_usage_logs").select(
        "id", count="exact"
    ).eq(
        "api_key_id", key_data["id"]
    ).gte(
        "created_at", _timestamp_to_iso(one_min_ago)
    ).execute()

    if recent_usage.count and recent_usage.count >= rate_limit:
        raise HTTPException(
            429,
            f"Rate limit exceeded. Max {rate_limit} requests/minute on {key_data['plan']} plan.",
        )

    # Update last used
    supabase.table("api_keys").update({
        "last_used_at": _now_iso()
    }).eq("id", key_data["id"]).execute()

    return {
        "auth_type": "api_key",
        "user_id": key_data["user_id"],
        "api_key_id": key_data["id"],
        "plan": key_data["plan"],
        "tokens_remaining": key_data["tokens_total"] - key_data["tokens_used"],
        "rate_limit": rate_limit,
    }


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _timestamp_to_iso(ts: float) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()