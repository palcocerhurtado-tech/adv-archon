"""Account endpoints: self-service register, credit balance, usage history."""
from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, field_validator

from adv_archon.api.deps import ApiStoreDep, AuthKey
from adv_archon.api.models import AccountResponse, UsageEntry, UsageResponse

router = APIRouter(prefix="/v1/account", tags=["account"])

_FREE_CREDITS = 10   # analyses included in free tier
_EMAIL_RE = re.compile(r"[^@]+@[^@]+\.[^@]+")


class RegisterRequest(BaseModel):
    name: str
    email: str

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El nombre no puede estar vacío.")
        return v[:80]

    @field_validator("email")
    @classmethod
    def valid_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("Email inválido.")
        return v[:120]


class RegisterResponse(BaseModel):
    api_key: str
    owner: str
    credits: int
    message: str


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear cuenta gratuita",
    description=(
        "Crea una API key gratuita con 10 créditos de análisis. "
        "No requiere tarjeta de crédito. Guarda la clave — sólo se muestra una vez."
    ),
)
def register(
    body: RegisterRequest,
    store: ApiStoreDep,
) -> RegisterResponse:
    """
    Free self-service registration. One key per email (enforced by prefix lookup).
    No payment required — 10 free analyses included.
    """
    # Prevent trivially duplicate registrations by checking existing owners
    existing = [k for k in store.list_keys() if k.owner == f"{body.name} <{body.email}>"]
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Ya existe una cuenta para este email. "
                "Contacta con soporte si necesitas recuperar tu clave."
            ),
        )
    owner = f"{body.name} <{body.email}>"
    raw_key = store.create_key(owner, credits=_FREE_CREDITS)
    return RegisterResponse(
        api_key=raw_key,
        owner=owner,
        credits=_FREE_CREDITS,
        message=(
            f"Bienvenido, {body.name}. Tienes {_FREE_CREDITS} análisis gratuitos. "
            "Guarda esta clave — no se puede recuperar. "
            "Para más créditos escribe a soporte."
        ),
    )


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
    store: ApiStoreDep,
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
