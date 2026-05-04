"""
ScraperDaemon — background job that keeps PGOU data fresh.

Runs as a daemon thread (no external scheduler needed).
Every `interval_hours` it scans indexed municipalities and re-scrapes
any whose data is older than `max_age_days`.

Usage:
    daemon = ScraperDaemon(pgou_store=store, scraper=scraper)
    daemon.start()          # non-blocking, daemon thread
    ...
    daemon.stop()           # signal stop; thread exits after current cycle
"""
from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class ScrapeJob:
    municipality: str
    scheduled_at: str
    status: str = "pending"    # "pending" | "running" | "done" | "error"
    error: str = ""
    completed_at: str = ""


@dataclass
class DaemonStats:
    cycles_run: int = 0
    municipalities_refreshed: int = 0
    municipalities_failed: int = 0
    last_cycle_at: str = ""
    next_cycle_at: str = ""
    running: bool = False


class ScraperDaemon:
    """
    Autonomous background agent that periodically refreshes stale PGOU normativa.

    Agent behaviour (each cycle):
    1. scan   — list all indexed municipalities
    2. filter — identify those older than max_age_days
    3. scrape — re-fetch and re-index each stale entry
    4. report — log results; update stats
    5. sleep  — wait interval_hours before next cycle
    """

    def __init__(
        self,
        *,
        pgou_store: Any,
        scraper: Any,
        interval_hours: float = 24.0,
        max_age_days: int = 30,
        on_refresh: Callable[[str, bool], None] | None = None,
    ) -> None:
        self._store          = pgou_store
        self._scraper        = scraper
        self._interval       = interval_hours * 3600
        self._max_age        = timedelta(days=max_age_days)
        self._on_refresh     = on_refresh   # callback(municipality, ok)
        self._stop_event     = threading.Event()
        self._thread: threading.Thread | None = None
        self._stats          = DaemonStats()
        self._lock           = threading.Lock()

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the daemon thread. Safe to call multiple times."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name="ScraperDaemon",
            daemon=True,   # exits when main process exits
        )
        self._thread.start()
        log.info("ScraperDaemon started (interval=%.0fh)", self._interval / 3600)

    def stop(self) -> None:
        """Signal the daemon to stop after the current cycle."""
        self._stop_event.set()
        log.info("ScraperDaemon stop requested")

    def trigger_now(self) -> None:
        """Force an immediate cycle (useful for testing or admin CLI)."""
        threading.Thread(target=self._cycle, daemon=True).start()

    @property
    def stats(self) -> DaemonStats:
        with self._lock:
            import copy
            return copy.copy(self._stats)

    # ── Internal loop ─────────────────────────────────────────────────────────

    def _loop(self) -> None:
        with self._lock:
            self._stats.running = True

        # Run first cycle immediately on startup
        self._cycle()

        while not self._stop_event.wait(timeout=self._interval):
            self._cycle()

        with self._lock:
            self._stats.running = False
        log.info("ScraperDaemon stopped")

    def _cycle(self) -> None:
        now = datetime.now(UTC)
        log.info("ScraperDaemon cycle started at %s", now.isoformat())

        with self._lock:
            self._stats.cycles_run += 1
            self._stats.last_cycle_at = now.isoformat()
            next_dt = now + timedelta(seconds=self._interval)
            self._stats.next_cycle_at = next_dt.isoformat()

        # Step 1 — scan
        try:
            municipalities = self._store.list_municipalities()
        except Exception as exc:
            log.error("ScraperDaemon: failed to list municipalities: %s", exc)
            return

        # Step 2 — filter stale
        stale = [m for m in municipalities if self._is_stale(m)]
        if not stale:
            log.info("ScraperDaemon: all %d municipalities are fresh", len(municipalities))
            return

        log.info(
            "ScraperDaemon: %d/%d municipalities are stale — refreshing",
            len(stale), len(municipalities),
        )

        # Step 3 — scrape each stale entry
        refreshed = 0
        failed = 0
        for muni in stale:
            if self._stop_event.is_set():
                log.info("ScraperDaemon: stop requested mid-cycle — aborting")
                break
            ok = self._refresh(muni.name)
            if ok:
                refreshed += 1
            else:
                failed += 1

        # Step 4 — report
        with self._lock:
            self._stats.municipalities_refreshed += refreshed
            self._stats.municipalities_failed    += failed

        log.info(
            "ScraperDaemon cycle done: refreshed=%d failed=%d",
            refreshed, failed,
        )

    def _is_stale(self, muni: Any) -> bool:
        try:
            indexed_at = datetime.fromisoformat(muni.indexed_at)
            if indexed_at.tzinfo is None:
                indexed_at = indexed_at.replace(tzinfo=UTC)
            return datetime.now(UTC) - indexed_at > self._max_age
        except Exception:
            return True   # treat unparseable dates as stale

    def _refresh(self, municipality: str) -> bool:
        log.info("ScraperDaemon: refreshing '%s'…", municipality)
        try:
            result = self._scraper.scrape_and_index(municipality)
            ok = bool(result.get("ok"))
            if self._on_refresh is not None:
                self._on_refresh(municipality, ok)
            if ok:
                log.info("ScraperDaemon: '%s' refreshed OK", municipality)
            else:
                log.warning(
                    "ScraperDaemon: '%s' refresh failed: %s",
                    municipality, result.get("error", "unknown"),
                )
            return ok
        except Exception as exc:
            log.error("ScraperDaemon: error refreshing '%s': %s", municipality, exc)
            if self._on_refresh is not None:
                self._on_refresh(municipality, False)
            return False
