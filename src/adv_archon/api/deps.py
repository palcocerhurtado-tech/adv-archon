"""FastAPI dependency injection: auth, store, compliance tools."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from adv_archon.api.store import ApiKey, ApiStore
from adv_archon.tools.urban_compliance import UrbanComplianceTools

# Singletons populated by app startup
_api_store: ApiStore | None = None
_compliance_tools: UrbanComplianceTools | None = None
_admin_key_prefix: str | None = None


def set_globals(
    api_store: ApiStore,
    compliance_tools: UrbanComplianceTools,
    admin_key_prefix: str,
) -> None:
    global _api_store, _compliance_tools, _admin_key_prefix
    _api_store = api_store
    _compliance_tools = compliance_tools
    _admin_key_prefix = admin_key_prefix


def get_api_store() -> ApiStore:
    assert _api_store is not None
    return _api_store


def get_compliance_tools() -> UrbanComplianceTools:
    assert _compliance_tools is not None
    return _compliance_tools


# ── Auth dependencies ─────────────────────────────────────────────────────────

def _resolve_key(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    store: ApiStore = Depends(get_api_store),
) -> ApiKey:
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta la cabecera X-API-Key.",
        )
    key = store.verify_key(x_api_key)
    if key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key inválida o desactivada.",
        )
    return key


AuthKey = Annotated[ApiKey, Depends(_resolve_key)]


def require_admin(key: AuthKey) -> ApiKey:
    if key.credits >= 0:  # non-unlimited = not admin
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere una clave de administrador.",
        )
    return key


AdminKey = Annotated[ApiKey, Depends(require_admin)]
