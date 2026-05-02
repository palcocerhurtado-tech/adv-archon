"""Pydantic request/response models for the compliance API."""
from __future__ import annotations

from pydantic import BaseModel, Field


# ── Parcel / site enrichment ──────────────────────────────────────────────────

class ParcelDetail(BaseModel):
    """Real parcel attributes from Catastro Consulta_DNPRC."""

    ref: str = ""
    surface_m2: int | None = None
    construction_year: int | None = None
    use_detail: str = ""
    floors_above: int | None = None
    floors_below: int | None = None
    address: str = ""
    municipality: str = ""


class FloodZoneDetail(BaseModel):
    """SNCZI flood-zone query result for a coordinate point."""

    queried: bool = False
    in_flood_zone: bool | None = None  # None → service unavailable
    periods: list[str] = Field(default_factory=list)
    source: str = "SNCZI/CNIG"
    error: str = ""


class Natura2000Detail(BaseModel):
    """Red Natura 2000 (ZEC/ZEPA) query result for a coordinate point."""

    queried: bool = False
    in_protected_area: bool | None = None  # None → service unavailable
    zones: list[str] = Field(default_factory=list)  # e.g. ["ZEC (hábitats)"]
    source: str = "Red Natura 2000 / CNIG"
    error: str = ""


# ── Compliance ────────────────────────────────────────────────────────────────

class ComplianceAnnotation(BaseModel):
    article_ref: str
    status: str   # "ok" | "warning" | "violation" | "info"
    description: str
    recommendation: str


class LegalCheckEntry(BaseModel):
    code: str
    title: str
    status: str
    authority: str
    detail: str
    recommended_action: str
    confidence: str


class SiteContextSummary(BaseModel):
    latitude: float | None = None
    longitude: float | None = None
    municipality: str
    province: str
    autonomous_community: str
    display_location: str
    cadastral_ref: str = ""
    cadastral_address: str = ""
    cadastral_use: str = ""
    resolution: str = ""
    confidence: str = ""
    pgou_indexed: bool | None = None
    next_step: str | None = None
    legal_readiness: str = ""
    legal_summary: str = ""
    legal_checks: list[LegalCheckEntry] = Field(default_factory=list)
    parcel_detail: ParcelDetail = Field(default_factory=ParcelDetail)
    flood_zone: FloodZoneDetail = Field(default_factory=FloodZoneDetail)
    natura2000: Natura2000Detail = Field(default_factory=Natura2000Detail)


class ComplianceCheckResponse(BaseModel):
    ok: bool
    plan: str
    municipality: str
    generated_at: str
    summary: str
    annotations: list[ComplianceAnnotation]
    full_analysis: str
    credits_used: int = 1
    credits_remaining: int
    site_context: SiteContextSummary | None = None
    pgou_auto_fetched: bool = False


class ComplianceReportResponse(BaseModel):
    ok: bool
    plan: str
    municipality: str
    summary: str
    annotations_count: int
    credits_used: int = 2
    credits_remaining: int
    # PDF is returned as binary (application/pdf), not in this model


# ── Municipalities ────────────────────────────────────────────────────────────

class MunicipalityEntry(BaseModel):
    name: str
    indexed: bool
    chunks: int | None = None
    indexed_at: str | None = None
    source: str | None = None


class MunicipalitiesResponse(BaseModel):
    total: int
    indexed: int
    municipalities: list[MunicipalityEntry]


# ── Account ───────────────────────────────────────────────────────────────────

class AccountResponse(BaseModel):
    owner: str
    prefix: str
    credits: int   # -1 = unlimited
    created_at: str
    last_used_at: str | None


class UsageEntry(BaseModel):
    endpoint: str
    municipality: str
    credits_used: int
    created_at: str


class UsageResponse(BaseModel):
    key_prefix: str
    records: list[UsageEntry]


# ── Admin ─────────────────────────────────────────────────────────────────────

class CreateKeyRequest(BaseModel):
    owner: str = Field(..., min_length=1, max_length=100)
    credits: int = Field(default=10, ge=-1)


class CreateKeyResponse(BaseModel):
    owner: str
    prefix: str
    api_key: str   # raw — shown only once
    credits: int


class AddCreditsRequest(BaseModel):
    amount: int = Field(..., ge=1, le=100_000)


class AddCreditsResponse(BaseModel):
    prefix: str
    new_balance: int


class KeyListEntry(BaseModel):
    owner: str
    prefix: str
    credits: int
    active: bool
    created_at: str
    last_used_at: str | None


class AdminStatusResponse(BaseModel):
    municipalities_indexed: int
    total_api_keys: int
    active_api_keys: int
    total_credits_issued: int
    total_analyses: int


class FetchMunicipalityRequest(BaseModel):
    municipality: str = Field(..., min_length=1)
    skip_if_indexed: bool = True


class FetchMunicipalityResponse(BaseModel):
    ok: bool
    municipality: str
    source_url: str | None = None
    chunks: int | None = None
    pages_extracted: int | None = None
    strategy: str | None = None
    error: str | None = None


class AddMunicipalityRequest(BaseModel):
    municipality: str = Field(..., min_length=1)
    text: str = Field(..., min_length=50)
    source: str = ""


class AddMunicipalityResponse(BaseModel):
    ok: bool
    municipality: str
    chunks_indexed: int


# ── Generic ───────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    ok: bool = False
    detail: str
