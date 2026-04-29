"""API key and credit store backed by SQLite."""
from __future__ import annotations

import hashlib
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(slots=True)
class ApiKey:
    id: int
    owner: str
    prefix: str        # first 8 chars, shown to user
    credits: int       # -1 = unlimited (admin)
    created_at: str
    last_used_at: str | None
    active: bool


@dataclass(slots=True)
class UsageRecord:
    id: int
    key_prefix: str
    endpoint: str
    municipality: str
    credits_used: int
    created_at: str


class ApiStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._conn = self._connect()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        self._migrate(conn)
        return conn

    def _migrate(self, conn: sqlite3.Connection) -> None:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                owner       TEXT NOT NULL,
                prefix      TEXT NOT NULL,
                key_hash    TEXT NOT NULL UNIQUE,
                credits     INTEGER NOT NULL DEFAULT 10,
                created_at  TEXT NOT NULL,
                last_used_at TEXT,
                active      INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS usage_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                key_prefix  TEXT NOT NULL,
                endpoint    TEXT NOT NULL,
                municipality TEXT NOT NULL DEFAULT '',
                credits_used INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_usage_key ON usage_log(key_prefix);
        """)
        conn.commit()

    # ------------------------------------------------------------------ #
    # Key management                                                        #
    # ------------------------------------------------------------------ #

    def create_key(self, owner: str, *, credits: int = 10) -> str:
        """Create a new API key; returns the raw key (only shown once)."""
        raw = f"archon_{secrets.token_urlsafe(32)}"
        prefix = raw[:12]
        key_hash = _hash(raw)
        now = datetime.now(UTC).isoformat()
        self._conn.execute(
            "INSERT INTO api_keys (owner, prefix, key_hash, credits, created_at, active) "
            "VALUES (?, ?, ?, ?, ?, 1)",
            (owner, prefix, key_hash, credits, now),
        )
        self._conn.commit()
        return raw

    def verify_key(self, raw: str) -> ApiKey | None:
        """Look up key by hash; returns None if not found or inactive."""
        key_hash = _hash(raw)
        row = self._conn.execute(
            "SELECT * FROM api_keys WHERE key_hash = ? AND active = 1",
            (key_hash,),
        ).fetchone()
        if row is None:
            return None
        now = datetime.now(UTC).isoformat()
        self._conn.execute(
            "UPDATE api_keys SET last_used_at = ? WHERE id = ?", (now, row["id"])
        )
        self._conn.commit()
        return _row_to_key(row)

    def list_keys(self) -> list[ApiKey]:
        rows = self._conn.execute(
            "SELECT * FROM api_keys ORDER BY created_at DESC"
        ).fetchall()
        return [_row_to_key(r) for r in rows]

    def deactivate_key(self, prefix: str) -> bool:
        cur = self._conn.execute(
            "UPDATE api_keys SET active = 0 WHERE prefix = ?", (prefix,)
        )
        self._conn.commit()
        return cur.rowcount > 0

    def set_credits(self, prefix: str, credits: int) -> bool:
        cur = self._conn.execute(
            "UPDATE api_keys SET credits = ? WHERE prefix = ?", (credits, prefix)
        )
        self._conn.commit()
        return cur.rowcount > 0

    def add_credits(self, prefix: str, amount: int) -> int | None:
        """Add credits; returns new balance or None if key not found."""
        row = self._conn.execute(
            "SELECT credits FROM api_keys WHERE prefix = ?", (prefix,)
        ).fetchone()
        if row is None:
            return None
        current = row["credits"]
        if current < 0:   # unlimited admin key
            return current
        new_balance = current + amount
        self._conn.execute(
            "UPDATE api_keys SET credits = ? WHERE prefix = ?", (new_balance, prefix)
        )
        self._conn.commit()
        return new_balance

    # ------------------------------------------------------------------ #
    # Credit operations                                                     #
    # ------------------------------------------------------------------ #

    def has_credits(self, key: ApiKey, amount: int = 1) -> bool:
        """Unlimited keys (credits == -1) always pass."""
        return key.credits < 0 or key.credits >= amount

    def deduct_credits(self, key: ApiKey, amount: int, *, endpoint: str, municipality: str = "") -> None:
        if key.credits >= 0:
            self._conn.execute(
                "UPDATE api_keys SET credits = credits - ? WHERE prefix = ?",
                (amount, key.prefix),
            )
        now = datetime.now(UTC).isoformat()
        self._conn.execute(
            "INSERT INTO usage_log (key_prefix, endpoint, municipality, credits_used, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (key.prefix, endpoint, municipality, amount, now),
        )
        self._conn.commit()

    # ------------------------------------------------------------------ #
    # Usage queries                                                         #
    # ------------------------------------------------------------------ #

    def usage_for_key(self, prefix: str, *, limit: int = 50) -> list[UsageRecord]:
        rows = self._conn.execute(
            "SELECT * FROM usage_log WHERE key_prefix = ? ORDER BY created_at DESC LIMIT ?",
            (prefix, limit),
        ).fetchall()
        return [_row_to_usage(r) for r in rows]

    def total_usage(self, *, limit: int = 200) -> list[UsageRecord]:
        rows = self._conn.execute(
            "SELECT * FROM usage_log ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_row_to_usage(r) for r in rows]


# ── helpers ──────────────────────────────────────────────────────────────────

def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _row_to_key(row: sqlite3.Row) -> ApiKey:
    return ApiKey(
        id=row["id"],
        owner=row["owner"],
        prefix=row["prefix"],
        credits=row["credits"],
        created_at=row["created_at"],
        last_used_at=row["last_used_at"],
        active=bool(row["active"]),
    )


def _row_to_usage(row: sqlite3.Row) -> UsageRecord:
    return UsageRecord(
        id=row["id"],
        key_prefix=row["key_prefix"],
        endpoint=row["endpoint"],
        municipality=row["municipality"],
        credits_used=row["credits_used"],
        created_at=row["created_at"],
    )
