#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

echo "== ADV ARCHON QA full =="
echo "Repo: ${ROOT}"
echo

echo "== Sync dev + desktop extras =="
rtk uv sync --extra dev --extra desktop
/usr/bin/chflags -R nohidden .venv 2>/dev/null || true

echo
echo "== Lint =="
rtk uv run ruff check src tests

echo
echo "== Unit + integration tests =="
rtk uv run pytest --no-header -q

echo
echo "== Python compile check =="
rtk uv run python -m compileall -q src tests

echo
echo "== Type check =="
rtk uv run mypy src/adv_archon

echo
echo "== CLI smoke tests =="
rtk uv run adv-archon --help >/dev/null
rtk uv run adv --help >/dev/null
rtk uv run adv-archon-api --help >/dev/null

echo
echo "== API smoke test =="
rtk uv run python - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from fastapi.testclient import TestClient

from adv_archon.api.app import create_app
from adv_archon.api.store import ApiStore

with TemporaryDirectory() as data_dir:
    store = ApiStore(Path(data_dir) / "api.db")
    tools = SimpleNamespace(
        _store=SimpleNamespace(list_municipalities=lambda: []),
    )
    app = create_app(
        api_store=store,
        compliance_tools=tools,
        admin_key_prefix="admin",
        cors_origins=["*"],
    )
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200, health.text
    assert health.json()["status"] == "ok"

    register = client.post(
        "/v1/account/register",
        json={"name": "QA", "email": "qa@example.com"},
    )
    assert register.status_code == 201, register.text
    api_key = register.json()["api_key"]

    account = client.get("/v1/account/me", headers={"X-API-Key": api_key})
    assert account.status_code == 200, account.text

    municipalities = client.get(
        "/v1/compliance/municipalities",
        headers={"X-API-Key": api_key},
    )
    assert municipalities.status_code == 200, municipalities.text

print("api-smoke-ok")
PY

echo
echo "== Desktop bundle smoke =="
bundle_dir="/private/tmp/adv-archon-qa-bundle"
rm -rf "${bundle_dir}"
rtk uv run adv-archon desktop-bundle "${bundle_dir}" >/dev/null
test -x "${bundle_dir}/ADV ARCHON.app/Contents/Resources/launch-adv-archon.sh"

echo
echo "== Beta package smoke =="
rtk bash -n scripts/build_beta_package.sh
rtk bash scripts/build_beta_package.sh >/dev/null
zip_list="/private/tmp/adv-archon-beta-zip-list.txt"
if command -v zipinfo >/dev/null 2>&1; then
    zipinfo -1 dist/ADV_ARCHON_BETA.zip > "${zip_list}"
else
    unzip -Z1 dist/ADV_ARCHON_BETA.zip > "${zip_list}"
fi
if grep -E '(^|/)\.env($|\.)' "${zip_list}" | grep -v '/\.env\.example$'; then
    echo "ERROR: beta zip contains .env files"
    exit 1
fi
if grep -E '(^|/)(\.git|\.venv|__pycache__|\.pytest_cache|\.ruff_cache|\.mypy_cache)(/|$)' "${zip_list}"; then
    echo "ERROR: beta zip contains internal cache directories"
    exit 1
fi
if grep -F '/normativa_arquitectura_es/' "${zip_list}"; then
    echo "ERROR: beta zip contains normativa_arquitectura_es"
    exit 1
fi
rm -f "${zip_list}"

echo
echo "QA full OK"
