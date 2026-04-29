"""Compliance analysis endpoints."""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from adv_archon.api.deps import AuthKey, get_api_store, get_compliance_tools
from adv_archon.api.models import (
    ComplianceAnnotation,
    ComplianceCheckResponse,
    MunicipalitiesResponse,
    MunicipalityEntry,
)
from adv_archon.api.store import ApiStore
from adv_archon.tools.urban_compliance import UrbanComplianceTools

router = APIRouter(prefix="/v1/compliance", tags=["compliance"])

_CHECK_COST = 1
_REPORT_COST = 2


@router.get("/municipalities", response_model=MunicipalitiesResponse)
def list_municipalities(
    key: AuthKey,
    tools: UrbanComplianceTools = Depends(get_compliance_tools),
) -> MunicipalitiesResponse:
    """List all municipalities available (indexed or in catalogue)."""
    from adv_archon.tools.pgou_scraper import SOURCES

    indexed_map = {m.name: m for m in tools._store.list_municipalities()}
    entries: list[MunicipalityEntry] = []
    for src in SOURCES:
        m = indexed_map.get(src.name)
        entries.append(MunicipalityEntry(
            name=src.name,
            indexed=m is not None,
            chunks=m.chunk_count if m else None,
            indexed_at=m.indexed_at[:10] if m else None,
            source=m.source if m else None,
        ))
    return MunicipalitiesResponse(
        total=len(entries),
        indexed=sum(1 for e in entries if e.indexed),
        municipalities=entries,
    )


@router.post("/check", response_model=ComplianceCheckResponse)
async def compliance_check(
    municipality: str,
    plan: UploadFile,
    key: AuthKey,
    store: ApiStore = Depends(get_api_store),
    tools: UrbanComplianceTools = Depends(get_compliance_tools),
) -> ComplianceCheckResponse:
    """
    Analyze an architectural plan PDF against the indexed PGOU.
    Costs **1 credit**.
    """
    _check_credits(key, store, _CHECK_COST)
    _check_pdf(plan)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(await plan.read())
        tmp_path = tmp.name

    try:
        result = tools.plan_compliance_check(tmp_path, municipality)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if not result.payload.get("ok"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=result.payload.get("error", "Error en el análisis"),
        )

    store.deduct_credits(key, _CHECK_COST, endpoint="compliance_check", municipality=municipality)
    remaining = _refresh_credits(store, key)

    payload = result.payload
    return ComplianceCheckResponse(
        ok=True,
        plan=payload["plan"],
        municipality=payload["municipality"],
        generated_at=payload["generated_at"],
        summary=payload["summary"],
        annotations=[
            ComplianceAnnotation(**a) for a in payload.get("annotations", [])
        ],
        full_analysis=payload["full_analysis"],
        credits_used=_CHECK_COST,
        credits_remaining=remaining,
    )


@router.post("/report")
async def compliance_report(
    municipality: str,
    plan: UploadFile,
    key: AuthKey,
    store: ApiStore = Depends(get_api_store),
    tools: UrbanComplianceTools = Depends(get_compliance_tools),
) -> FileResponse:
    """
    Analyze an architectural plan and return a professional PDF report.
    Costs **2 credits**.
    """
    _check_credits(key, store, _REPORT_COST)
    _check_pdf(plan)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(await plan.read())
        tmp_path = tmp.name

    out_path = Path(tempfile.mktemp(suffix=".pdf"))
    try:
        result = tools.plan_compliance_export(tmp_path, municipality, str(out_path))
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if not result.payload.get("ok"):
        out_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=result.payload.get("error", "Error generando el informe"),
        )

    store.deduct_credits(key, _REPORT_COST, endpoint="compliance_report", municipality=municipality)

    muni_slug = municipality.lower().replace(" ", "_")
    filename = f"informe_{muni_slug}.pdf"
    return FileResponse(
        path=str(out_path),
        media_type="application/pdf",
        filename=filename,
        background=_cleanup_task(out_path),
    )


# ── helpers ───────────────────────────────────────────────────────────────────

def _check_credits(key: AuthKey, store: ApiStore, needed: int) -> None:
    if not store.has_credits(key, needed):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Créditos insuficientes. Necesitas {needed}, tienes {key.credits}.",
        )


def _check_pdf(upload: UploadFile) -> None:
    ct = upload.content_type or ""
    name = upload.filename or ""
    if "pdf" not in ct and not name.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="El archivo debe ser un PDF.",
        )


def _refresh_credits(store: ApiStore, key: AuthKey) -> int:
    refreshed = store.verify_key.__self__ if False else None  # type guard
    row = store._conn.execute(
        "SELECT credits FROM api_keys WHERE prefix = ?", (key.prefix,)
    ).fetchone()
    return row["credits"] if row else key.credits


def _cleanup_task(path: Path):
    from starlette.background import BackgroundTask
    return BackgroundTask(lambda: path.unlink(missing_ok=True))
