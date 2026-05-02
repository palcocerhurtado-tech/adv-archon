"""SQLite cache for resolved geographic coordinates."""
from __future__ import annotations

import json
import math
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from adv_archon.core.site_context import ConfidenceLevel, Resolution, SiteContext

_CACHE_RADIUS_KM = 0.1   # 100 m — same coords are considered identical


class GeoStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._conn = self._connect()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        self._migrate(conn)
        return conn

    def _migrate(self, conn: sqlite3.Connection) -> None:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS geo_cache (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                latitude        REAL NOT NULL,
                longitude       REAL NOT NULL,
                municipality    TEXT NOT NULL,
                province        TEXT NOT NULL,
                autonomous_community TEXT NOT NULL,
                cadastral_ref   TEXT NOT NULL DEFAULT '',
                cadastral_address TEXT NOT NULL DEFAULT '',
                cadastral_use   TEXT NOT NULL DEFAULT '',
                resolution      TEXT NOT NULL,
                confidence      TEXT NOT NULL,
                reasons_json    TEXT NOT NULL DEFAULT '[]',
                raw_nominatim_json TEXT NOT NULL DEFAULT '{}',
                raw_catastro    TEXT NOT NULL DEFAULT '',
                created_at      TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_geo_coords
                ON geo_cache(latitude, longitude);
        """)
        conn.commit()

    def get_cached(self, lat: float, lon: float) -> SiteContext | None:
        """Return cached result if one exists within _CACHE_RADIUS_KM."""
        # Simple bounding-box pre-filter, then exact distance check
        deg_lat = _CACHE_RADIUS_KM / 111.0
        deg_lon = _CACHE_RADIUS_KM / (111.0 * math.cos(math.radians(lat)))
        rows = self._conn.execute(
            "SELECT * FROM geo_cache "
            "WHERE latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?",
            (lat - deg_lat, lat + deg_lat, lon - deg_lon, lon + deg_lon),
        ).fetchall()
        for row in rows:
            dist = _haversine(lat, lon, row["latitude"], row["longitude"])
            if dist <= _CACHE_RADIUS_KM:
                return _row_to_context(row)
        return None

    def store(self, ctx: SiteContext) -> None:
        now = datetime.now(UTC).isoformat()
        self._conn.execute(
            "INSERT OR REPLACE INTO geo_cache "
            "(latitude, longitude, municipality, province, autonomous_community, "
            "cadastral_ref, cadastral_address, cadastral_use, resolution, confidence, "
            "reasons_json, raw_nominatim_json, raw_catastro, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                ctx.latitude, ctx.longitude,
                ctx.municipality, ctx.province, ctx.autonomous_community,
                ctx.cadastral_ref, ctx.cadastral_address, ctx.cadastral_use,
                ctx.resolution, ctx.confidence,
                json.dumps(ctx.reasons),
                json.dumps(ctx.raw_nominatim),
                ctx.raw_catastro,
                now,
            ),
        )
        self._conn.commit()


def _row_to_context(row: sqlite3.Row) -> SiteContext:
    return SiteContext(
        latitude=row["latitude"],
        longitude=row["longitude"],
        municipality=row["municipality"],
        province=row["province"],
        autonomous_community=row["autonomous_community"],
        cadastral_ref=row["cadastral_ref"],
        cadastral_address=row["cadastral_address"],
        cadastral_use=row["cadastral_use"],
        resolution=cast(Resolution, row["resolution"]),
        confidence=cast(ConfidenceLevel, row["confidence"]),
        reasons=json.loads(row["reasons_json"]),
        raw_nominatim=json.loads(row["raw_nominatim_json"]),
        raw_catastro=row["raw_catastro"],
    )


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))
