"""
DubKaro — API Key Management Router
Developers can create API keys, check usage, manage tokens.
"""

import secrets
import hashlib
from fastapi import APIRouter, HTTPException, Depends
from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY, API_KEY_PLANS
from middleware.auth import get_current_user, hash_api_key
from models.api_keys import CreateApiKeyRequest
from datetime import datetime, timezone

router = APIRouter(prefix="/api/keys", tags=["API Keys"])
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def _generate_api_key() -> str:
    """Generate a unique API key: dk_live_xxxxxxxxxx"""
    random_part = secrets.token_hex(24)
    return f"dk_live_{random_part}"


@router.post("/create")
async def create_api_key(
    req: CreateApiKeyRequest,
    user: dict = Depends(get_current_user),
):
    """
    New API key generate karo.
    Free plan pe max 2 keys, Pro pe 5, Unlimited pe 10.
    """
    user_id = user["user_id"]

    # Check existing keys count
    existing = supabase.table("api_keys").select(
        "id", count="exact"
    ).eq("user_id", user_id).eq("is_active", True).execute()

    max_keys = {"free": 2, "starter": 3, "pro": 5, "unlimited": 10}
    user_plan = user.get("plan", "free")
    limit = max_keys.get(user_plan, 2)

    if existing.count and existing.count >= limit:
        raise HTTPException(
            400,
            f"Maximum {limit} active API keys allowed on {user_plan} plan.",
        )

    # Generate key
    raw_key = _generate_api_key()
    key_hash = hash_api_key(raw_key)

    # Plan config
    plan_config = API_KEY_PLANS.get(user_plan, API_KEY_PLANS["free"])

    # Save to DB
    key_data = {
        "user_id": user_id,
        "key_name": req.key_name,
        "api_key": raw_key[:12] + "..." + raw_key[-4:],  # Masked version stored
        "secret_hash": key_hash,
        "plan": user_plan,
        "tokens_total": plan_config["tokens_total"],
        "tokens_used": 0,
        "rate_limit_per_min": plan_config["rate_limit_per_min"],
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    result = supabase.table("api_keys").insert(key_data).execute()

    return {
        "message": "API key created successfully. Save it — it won't be shown again!",
        "api_key": raw_key,  # ⚠️ Only shown ONCE
        "key_name": req.key_name,
        "plan": user_plan,
        "tokens_total": plan_config["tokens_total"],
        "rate_limit_per_min": plan_config["rate_limit_per_min"],
    }


@router.get("/list")
async def list_api_keys(user: dict = Depends(get_current_user)):
    """User ke saare API keys list karo."""
    result = supabase.table("api_keys").select("*").eq(
        "user_id", user["user_id"]
    ).order("created_at", desc=True).execute()

    keys = []
    for k in result.data:
        keys.append({
            "id": k["id"],
            "key_name": k["key_name"],
            "api_key_preview": k["api_key"],  # Already masked in DB
            "plan": k["plan"],
            "tokens_total": k["tokens_total"],
            "tokens_used": k["tokens_used"],
            "tokens_remaining": k["tokens_total"] - k["tokens_used"],
            "rate_limit_per_min": k["rate_limit_per_min"],
            "is_active": k["is_active"],
            "last_used_at": k.get("last_used_at"),
            "created_at": k["created_at"],
        })

    return {"api_keys": keys}


@router.get("/usage/{key_id}")
async def get_key_usage(
    key_id: str,
    user: dict = Depends(get_current_user),
):
    """Specific API key ka usage history."""
    # Verify ownership
    key = supabase.table("api_keys").select("*").eq(
        "id", key_id
    ).eq("user_id", user["user_id"]).maybe_single().execute()

    if not key.data:
        raise HTTPException(404, "API key not found")

    # Fetch usage logs
    logs = supabase.table("api_usage_logs").select("*").eq(
        "api_key_id", key_id
    ).order("created_at", desc=True).limit(100).execute()

    return {
        "key_info": {
            "key_name": key.data["key_name"],
            "plan": key.data["plan"],
            "tokens_total": key.data["tokens_total"],
            "tokens_used": key.data["tokens_used"],
            "tokens_remaining": key.data["tokens_total"] - key.data["tokens_used"],
        },
        "usage_logs": logs.data,
    }


@router.delete("/revoke/{key_id}")
async def revoke_api_key(
    key_id: str,
    user: dict = Depends(get_current_user),
):
    """API key deactivate karo."""
    result = supabase.table("api_keys").update(
        {"is_active": False}
    ).eq("id", key_id).eq("user_id", user["user_id"]).execute()

    if not result.data:
        raise HTTPException(404, "API key not found")

    return {"message": "API key revoked successfully"}


@router.get("/plans")
async def get_plans():
    """Available API plans with pricing."""
    return {"plans": API_KEY_PLANS}