"""Account endpoints: credit balance, usage history."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from adv_archon.api.deps import AuthKey, get_api_store
from adv_archon.api.models import AccountResponse, UsageEntry, UsageResponse
from adv_archon.api.store import ApiStore

router = APIRouter(prefix="/v1/account", tags=["account"])


@router.get("/me", response_model=AccountResponse)
def account_info(
    key: AuthKey,
) -> AccountResponse:
    """Return the authenticated key's owner and credit balance."""
    return AccountResponse(
        owner=key.owner,
        prefix=key.prefix,
        credits=key.credits,
        created_at=key.created_at,
        last_used_at=key.last_used_at,
    )


@router.get("/usage", response_model=UsageResponse)
def usage_history(
    key: AuthKey,
    store: ApiStore = Depends(get_api_store),
    limit: int = 50,
) -> UsageResponse:
    """Return the last N usage records for this key."""
    limit = max(1, min(limit, 200))
    records = store.usage_for_key(key.prefix, limit=limit)
    return UsageResponse(
        key_prefix=key.prefix,
        records=[
            UsageEntry(
                endpoint=r.endpoint,
                municipality=r.municipality,
                credits_used=r.credits_used,
                created_at=r.created_at,
            )
            for r in records
        ],
    )
