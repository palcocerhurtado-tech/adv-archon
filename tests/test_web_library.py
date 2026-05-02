from pathlib import Path

import numpy as np
import pytest

from adv_archon.core.web_library import WebLibraryStore
from adv_archon.tools.web_library_tools import WebLibraryTools


class FakeEncoder:
    def encode_texts(self, texts: list[str]) -> np.ndarray:
        rows = []
        for text in texts:
            lowered = text.lower()
            vector = np.array(
                [
                    1.0 if "acme" in lowered else 0.0,
                    1.0 if "python" in lowered else 0.0,
                    float((len(lowered) % 7) + 1),
                ],
                dtype=np.float32,
            )
            norm = np.linalg.norm(vector)
            rows.append(vector if norm == 0 else vector / norm)
        return np.vstack(rows)


def test_web_library_store_upserts_and_searches(tmp_path: Path) -> None:
    store = WebLibraryStore(tmp_path / "web-library.db", encoder=FakeEncoder())

    store.upsert_entry(
        url="https://example.com/acme-report",
        title="Acme report",
        text="Acme is using Python agents in production.",
        tags=["ai", "acme"],
    )
    results = store.search("acme python", limit=3)

    assert len(results) == 1
    assert results[0].title == "Acme report"
    assert results[0].freshness_state == "fresh"


def test_web_library_store_ingests_search_results(tmp_path: Path) -> None:
    store = WebLibraryStore(tmp_path / "web-library.db", encoder=FakeEncoder())

    result = store.ingest_search_results(
        "acme agents",
        [
            {
                "title": "Acme and agents",
                "url": "https://example.com/acme",
                "snippet": "Acme scales agents.",
            }
        ],
        tags=["market"],
    )

    assert result.added == 1
    assert result.records[0].domain == "example.com"
    assert "market" in result.records[0].tags


def test_web_library_tools_save_search_and_url(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store = WebLibraryStore(tmp_path / "web-library.db", encoder=FakeEncoder())
    tools = WebLibraryTools(store)

    monkeypatch.setattr(
        "adv_archon.tools.web_library_tools.web_search",
        lambda query, n=5: type(
            "SearchResult",
            (),
            {
                "payload": {
                    "results": [
                        {
                            "title": "Acme market",
                            "url": "https://example.com/acme-market",
                            "snippet": "Acme market overview",
                        }
                    ]
                }
            },
        )(),
    )
    monkeypatch.setattr(
        "adv_archon.tools.web_library_tools.web_fetch",
        lambda url: type(
            "FetchResult",
            (),
            {"payload": {"text": f"Fetched content for {url} with Python and Acme."}},
        )(),
    )

    saved_search = tools.web_library_save_search("acme market", n=1)
    saved_url = tools.web_library_save_url("https://example.com/acme-market")

    assert saved_search.payload["added"] == 1
    assert saved_url.payload["record"]["canonical_url"] == "https://example.com/acme-market"


def test_web_library_store_uses_sqlite_wal_mode_for_persistent_db(tmp_path: Path) -> None:
    store = WebLibraryStore(tmp_path / "web-library.db", encoder=FakeEncoder())

    journal_mode = store._conn.execute("PRAGMA journal_mode").fetchone()[0]
    busy_timeout = store._conn.execute("PRAGMA busy_timeout").fetchone()[0]

    assert str(journal_mode).lower() == "wal"
    assert int(busy_timeout) == 30000
