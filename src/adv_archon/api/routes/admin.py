"""Admin endpoints: key management, municipality indexing, system status."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from adv_archon.api.deps import AdminKey, get_api_store, get_compliance_tools
from adv_archon.api.models import (
    AddCreditsRequest,
    AddCreditsResponse,
    AddMunicipalityRequest,
    AddMunicipalityResponse,
    AdminStatusResponse,
    CreateKeyRequest,
    CreateKeyResponse,
    FetchMunicipalityRequest,
    FetchMunicipalityResponse,
    KeyListEntry,
)
from adv_archon.api.store import ApiStore
from adv_archon.tools.urban_compliance import UrbanComplianceTools

router = APIRouter(prefix="/v1/admin", tags=["admin"])


@router.get("/status", response_model=AdminStatusResponse)
def admin_status(
    _key: AdminKey,
    store: ApiStore = Depends(get_api_store),
    tools: UrbanComplianceTools = Depends(get_compliance_tools),
) -> AdminStatusResponse:
    """System-wide stats: municipalities, keys, usage."""
    munis = tools._store.list_municipalities()
    all_keys = store.list_keys()
    active_keys = [k for k in all_keys if k.active]
    usage = store.total_usage(limit=10_000)
    total_credits_issued = sum(
        k.credits for k in all_keys if k.credits > 0
    )
    return AdminStatusResponse(
        municipalities_indexed=len(munis),
        total_api_keys=len(all_keys),
        active_api_keys=len(active_keys),
        total_credits_issued=total_credits_issued,
        total_analyses=len(usage),
    )


# ── API key management ────────────────────────────────────────────────────────

@router.post("/keys", response_model=CreateKeyResponse, status_code=status.HTTP_201_CREATED)
def create_key(
    req: CreateKeyRequest,
    _key: AdminKey,
    store: ApiStore = Depends(get_api_store),
) -> CreateKeyResponse:
    """Create a new API key. The raw key is returned once — store it safely."""
    raw = store.create_key(req.owner, credits=req.credits)
    prefix = raw[:12]
    return CreateKeyResponse(
        owner=req.owner,
        prefix=prefix,
        api_key=raw,
        credits=req.credits,
    )


@router.get("/keys", response_model=list[KeyListEntry])
def list_keys(
    _key: AdminKey,
    store: ApiStore = Depends(get_api_store),
) -> list[KeyListEntry]:
    """List all API keys (hashes not exposed)."""
    return [
        KeyListEntry(
            owner=k.owner,
            prefix=k.prefix,
            credits=k.credits,
            active=k.active,
            created_at=k.created_at,
            last_used_at=k.last_used_at,
        )
        for k in store.list_keys()
    ]


@router.delete("/keys/{prefix}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_key(
    prefix: str,
    _key: AdminKey,
    store: ApiStore = Depends(get_api_store),
) -> None:
    """Revoke an API key."""
    if not store.deactivate_key(prefix):
        raise HTTPException(status_code=404, detail=f"Clave '{prefix}' no encontrada.")


@router.post("/keys/{prefix}/credits", response_model=AddCreditsResponse)
def add_credits(
    prefix: str,
    req: AddCreditsRequest,
    _key: AdminKey,
    store: ApiStore = Depends(get_api_store),
) -> AddCreditsResponse:
    """Add credits to an existing key."""
    new_balance = store.add_credits(prefix, req.amount)
    if new_balance is None:
        raise HTTPException(status_code=404, detail=f"Clave '{prefix}' no encontrada.")
    return AddCreditsResponse(prefix=prefix, new_balance=new_balance)


# ── Municipality management ───────────────────────────────────────────────────

@router.post("/municipalities/fetch", response_model=FetchMunicipalityResponse)
def fetch_municipality(
    req: FetchMunicipalityRequest,
    _key: AdminKey,
    tools: UrbanComplianceTools = Depends(get_compliance_tools),
) -> FetchMunicipalityResponse:
    """Auto-download and index PGOU for a municipality from the catalogue."""
    if req.skip_if_indexed and tools._store.get_municipality(req.municipality) is not None:
        return FetchMunicipalityResponse(
            ok=True,
            municipality=req.municipality,
            strategy="skipped_already_indexed",
        )

    log_lines: list[str] = []
    result = tools.pgou_fetch(req.municipality, progress_cb=log_lines.append)
    p = result.payload
    return FetchMunicipalityResponse(
        ok=p.get("ok", False),
        municipality=p.get("municipality", req.municipality),
        source_url=p.get("source_url"),
        chunks=p.get("chunks"),
        pages_extracted=p.get("pages_extracted"),
        strategy=p.get("strategy"),
        error=p.get("error"),
    )


@router.post("/municipalities", response_model=AddMunicipalityResponse, status_code=status.HTTP_201_CREATED)
def add_municipality(
    req: AddMunicipalityRequest,
    _key: AdminKey,
    tools: UrbanComplianceTools = Depends(get_compliance_tools),
) -> AddMunicipalityResponse:
    """Manually index PGOU text for a municipality."""
    result = tools.pgou_add(req.municipality, req.text, req.source)
    p = result.payload
    if not p.get("ok"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=p.get("error", "Error indexando normativa"),
        )
    return AddMunicipalityResponse(
        ok=True,
        municipality=p["municipality"],
        chunks_indexed=p["chunks_indexed"],
    )


@router.delete("/municipalities/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_municipality(
    name: str,
    _key: AdminKey,
    tools: UrbanComplianceTools = Depends(get_compliance_tools),
) -> None:
    """Remove indexed PGOU for a municipality."""
    if not tools._store.delete_municipality(name):
        raise HTTPException(status_code=404, detail=f"Municipio '{name}' no indexado.")
