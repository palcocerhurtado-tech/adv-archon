"""Location resolution endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from adv_archon.api.deps import AuthKey, get_compliance_tools
from adv_archon.api.models import FloodZoneDetail, ParcelDetail
from adv_archon.core.geo_store import GeoStore
from adv_archon.tools.geo_tools import GeoTools
from adv_archon.tools.urban_compliance import UrbanComplianceTools

router = APIRouter(prefix="/v1/location", tags=["location"])

# Geo store is initialised lazily from the compliance tools' pgou_store path
_geo_tools: GeoTools | None = None


def _get_geo_tools(tools: UrbanComplianceTools = Depends(get_compliance_tools)) -> GeoTools:  # noqa: B008
    global _geo_tools
    if _geo_tools is None:
        import os
        from pathlib import Path
        data_dir = Path(os.getenv("ADV_ARCHON_HOME", Path.home() / ".adv-archon"))
        geo_db = data_dir / "geo.db"
        _geo_tools = GeoTools(GeoStore(geo_db), tools._store)
    return _geo_tools


class ResolveRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    refresh: bool = False


class SiteContextResponse(BaseModel):
    ok: bool
    latitude: float
    longitude: float
    municipality: str
    province: str
    autonomous_community: str
    cadastral_ref: str
    cadastral_address: str
    cadastral_use: str
    resolution: str
    confidence: str
    reasons: list[str]
    display_location: str
    pgou_indexed: bool | None = None
    parcel_detail: ParcelDetail = Field(default_factory=ParcelDetail)
    flood_zone: FloodZoneDetail = Field(default_factory=FloodZoneDetail)
    next_step: str | None = None
    legal_readiness: str = ""
    legal_summary: str = ""
    legal_checks: list[dict[str, str]] = Field(default_factory=list)
    from_cache: bool = False
    error: str | None = None


@router.post("/resolve", response_model=SiteContextResponse)
def resolve_location(
    req: ResolveRequest,
    _key: AuthKey,
    geo: GeoTools = Depends(_get_geo_tools),  # noqa: B008
) -> SiteContextResponse:
    """
    Resolve GPS coordinates to a Spanish municipality, province,
    autonomous community, and cadastral reference.
    No credits charged — free lookup.
    """
    result = geo.resolve_coordinates(
        req.latitude,
        req.longitude,
        refresh=req.refresh,
    )
    p = result.payload
    if not p.get("ok"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=p.get("error", "No se pudo resolver la ubicación"),
        )
    p.pop("parcel_detail", None)   # resolve endpoint doesn't run parcel/SNCZI fetch
    p.pop("flood_zone", None)
    return SiteContextResponse(**p)


@router.post("/site-context", response_model=SiteContextResponse)
def site_compliance_context(
    req: ResolveRequest,
    _key: AuthKey,
    geo: GeoTools = Depends(_get_geo_tools),  # noqa: B008
) -> SiteContextResponse:
    """
    Full site context: municipality + cadastral reference + PGOU index status.
    Returns next_step and a preliminary legal checklist for parcel-level review.
    No credits charged.
    """
    result = geo.site_compliance_context(req.latitude, req.longitude)
    p = result.payload
    if not p.get("ok"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=p.get("error", "No se pudo resolver la ubicación"),
        )
    return SiteContextResponse(**p)
