"""FastAPI application factory."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from adv_archon.api.deps import set_globals
from adv_archon.api.routes.account import router as account_router
from adv_archon.api.routes.admin import router as admin_router
from adv_archon.api.routes.compliance import router as compliance_router
from adv_archon.api.store import ApiStore
from adv_archon.tools.urban_compliance import UrbanComplianceTools


def create_app(
    *,
    api_store: ApiStore,
    compliance_tools: UrbanComplianceTools,
    admin_key_prefix: str,
    cors_origins: list[str] | None = None,
) -> FastAPI:
    app = FastAPI(
        title="ADV ARCHON — API de Cumplimiento Urbanístico",
        description=(
            "Analiza planos arquitectónicos contra la normativa PGOU de municipios españoles. "
            "Autenticación: cabecera `X-API-Key`."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    set_globals(api_store, compliance_tools, admin_key_prefix)

    app.include_router(compliance_router)
    app.include_router(account_router)
    app.include_router(admin_router)

    @app.get("/health", tags=["meta"], include_in_schema=False)
    def health() -> JSONResponse:
        return JSONResponse({"status": "ok", "service": "adv-archon-api"})

    @app.get("/", tags=["meta"], include_in_schema=False)
    def root() -> JSONResponse:
        return JSONResponse({
            "service": "ADV ARCHON API",
            "docs": "/docs",
            "version": "1.0.0",
        })

    return app
