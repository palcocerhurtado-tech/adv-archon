"""Site context data types: result of resolving coordinates to a location."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Resolution = Literal["nominatim", "catastro", "cache", "manual", "unknown"]

ConfidenceLevel = Literal["high", "medium", "low"]
LegalCheckStatus = Literal["ready", "pending_review", "conditional", "missing"]


@dataclass(slots=True)
class LegalCheck:
    """Structured legal/sectorial verification item for a parcel or site."""

    code: str
    title: str
    status: LegalCheckStatus
    authority: str
    detail: str
    recommended_action: str
    confidence: ConfidenceLevel = "medium"

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "title": self.title,
            "status": self.status,
            "authority": self.authority,
            "detail": self.detail,
            "recommended_action": self.recommended_action,
            "confidence": self.confidence,
        }


@dataclass(slots=True)
class SiteContext:
    """Fully resolved location context for a pair of coordinates."""

    # Raw input
    latitude: float
    longitude: float

    # Geographic resolution
    municipality: str
    province: str
    autonomous_community: str
    country: str = "España"

    # Cadastral data (optional, Catastro API)
    cadastral_ref: str = ""       # e.g. "7537903VK4873N0001OU"
    cadastral_address: str = ""   # human-readable cadastral address
    cadastral_use: str = ""       # e.g. "Residencial", "Industrial"

    # Meta
    resolution: Resolution = "unknown"
    confidence: ConfidenceLevel = "medium"
    reasons: list[str] = field(default_factory=list)
    raw_nominatim: dict[str, Any] = field(default_factory=dict)
    raw_catastro: str = ""        # raw XML from Catastro

    @property
    def display_location(self) -> str:
        parts = [self.municipality]
        if self.province and self.province != self.municipality:
            parts.append(self.province)
        if self.autonomous_community and self.autonomous_community not in parts:
            parts.append(self.autonomous_community)
        return ", ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "municipality": self.municipality,
            "province": self.province,
            "autonomous_community": self.autonomous_community,
            "country": self.country,
            "cadastral_ref": self.cadastral_ref,
            "cadastral_address": self.cadastral_address,
            "cadastral_use": self.cadastral_use,
            "resolution": self.resolution,
            "confidence": self.confidence,
            "reasons": self.reasons,
            "display_location": self.display_location,
        }
