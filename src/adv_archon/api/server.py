"""CLI entry point for the ADV ARCHON compliance API server."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import TYPE_CHECKING

from adv_archon.api.store import ApiStore

if TYPE_CHECKING:
    from adv_archon.core.llm import LLMRouter


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="adv-archon-api",
        description="ADV ARCHON — REST API de cumplimiento urbanístico",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Dirección de escucha (default: 0.0.0.0)",
    )
    parser.add_argument("--port", type=int, default=8000, help="Puerto (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Activar auto-reload (desarrollo)")
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Directorio de datos (default: ~/.adv-archon)",
    )
    parser.add_argument(
        "--admin-key",
        default=None,
        help="Clave de administrador (raw). Si no se especifica, se genera una nueva.",
    )
    parser.add_argument(
        "--cors-origins",
        default="*",
        help="Orígenes CORS separados por coma (default: *)",
    )
    args = parser.parse_args()

    data_dir = (
        Path(args.data_dir).expanduser()
        if args.data_dir
        else Path.home() / ".adv-archon"
    )
    data_dir.mkdir(parents=True, exist_ok=True)

    _boot(
        data_dir=data_dir,
        admin_key_raw=args.admin_key,
        host=args.host,
        port=args.port,
        reload=args.reload,
        cors_origins=[o.strip() for o in args.cors_origins.split(",")],
    )


def _boot(
    *,
    data_dir: Path,
    admin_key_raw: str | None,
    host: str,
    port: int,
    reload: bool,
    cors_origins: list[str],
) -> None:
    import uvicorn

    from adv_archon.api.app import create_app
    from adv_archon.api.store import ApiStore
    from adv_archon.core.pgou_store import PGOUStore
    from adv_archon.tools.urban_compliance import UrbanComplianceTools

    # ── Storage ──────────────────────────────────────────────────────────
    pgou_db = data_dir / "pgou.db"
    api_db = data_dir / "api.db"

    pgou_store = PGOUStore(pgou_db)
    api_store = ApiStore(api_db)

    # ── Admin key ────────────────────────────────────────────────────────
    admin_prefix, admin_key_raw = _ensure_admin_key(api_store, admin_key_raw)

    # ── LLM + compliance tools ───────────────────────────────────────────
    llm_router = _build_llm_router(data_dir)
    compliance_tools = UrbanComplianceTools(pgou_store, llm_router)

    # ── App ──────────────────────────────────────────────────────────────
    app = create_app(
        api_store=api_store,
        compliance_tools=compliance_tools,
        admin_key_prefix=admin_prefix,
        cors_origins=cors_origins,
    )

    print("=" * 60)
    print("  ADV ARCHON — API de Cumplimiento Urbanístico")
    print(f"  http://{host}:{port}")
    print(f"  Docs:   http://{host}:{port}/docs")
    print(f"  Admin:  X-API-Key: {admin_key_raw}")
    print("=" * 60)

    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


def _ensure_admin_key(api_store: ApiStore, raw: str | None) -> tuple[str, str]:
    """Return (prefix, raw_key). Creates a new admin key if none exists."""
    existing = [k for k in api_store.list_keys() if k.credits < 0 and k.active]

    if raw:
        # Verify the provided key works
        key = api_store.verify_key(raw)
        if key and key.credits < 0:
            return key.prefix, raw
        # If not recognised, register it as a new admin key
        # (Can't re-use raw key since we only store hash — create new)
        print("[WARN] La clave admin proporcionada no se reconoció. Creando nueva clave admin.")

    if existing:
        # Reuse existing admin key prefix, but we can't recover the raw key
        # Create a new one and inform the operator
        raw_new = api_store.create_key("admin", credits=-1)
        prefix = raw_new[:12]
        print(f"[INFO] Nueva clave admin creada (prefix: {prefix})")
        return prefix, raw_new

    raw_new = api_store.create_key("admin", credits=-1)
    prefix = raw_new[:12]
    return prefix, raw_new


def _build_llm_router(data_dir: Path) -> LLMRouter:
    """Build an LLMRouter from env + config.toml if available."""
    from adv_archon.core.config import LLMConfig, load_app_config
    from adv_archon.core.llm import LLMRouter

    # Point ADV_ARCHON_HOME at data_dir so load_app_config picks up the right config.toml
    os.environ.setdefault("ADV_ARCHON_HOME", str(data_dir))
    try:
        config = load_app_config()
        llm_cfg = config.llm
    except Exception:
        llm_cfg = LLMConfig()

    if not llm_cfg.gemini_api_key:
        object.__setattr__(
            llm_cfg,
            "gemini_api_key",
            os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
        )
    return LLMRouter(llm_cfg)
