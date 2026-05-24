"""SQLite schema + connection helpers.

Four tables:
  family_offices  — one row per canonical FO
  signals         — one row per (fo_id, field, source) — provenance lives here
  sources         — discovery-layer record of where each FO was first found
  aliases         — alternate names the same FO appears under across sources
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "polarity_iq.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS family_offices (
    fo_id          TEXT PRIMARY KEY,         -- slug, e.g. "soros_fund_management"
    canonical_name TEXT NOT NULL,
    type           TEXT,                     -- SFO | MFO | Trust | Holdco | Unknown
    hq_address     TEXT,
    hq_city        TEXT,
    hq_country     TEXT,
    sec_crd        TEXT,
    ein            TEXT,
    foundation_ein TEXT,                     -- linked 990-PF entity if any
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    notes          TEXT
);

CREATE TABLE IF NOT EXISTS signals (
    signal_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    fo_id         TEXT NOT NULL,
    field         TEXT NOT NULL,            -- e.g. legal_name, hq_address, recent_investment
    domain        TEXT NOT NULL,            -- identity | equities | private | real_assets | soft_power | shadow_bank
    value         TEXT NOT NULL,            -- string or JSON-serialised
    source_url    TEXT NOT NULL,
    method        TEXT NOT NULL,
    confidence    REAL NOT NULL,
    extracted_at  TEXT NOT NULL,
    notes         TEXT,
    FOREIGN KEY (fo_id) REFERENCES family_offices(fo_id)
);

CREATE INDEX IF NOT EXISTS idx_signals_fo_field ON signals(fo_id, field);
CREATE INDEX IF NOT EXISTS idx_signals_domain   ON signals(domain);

CREATE TABLE IF NOT EXISTS sources (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    fo_id         TEXT NOT NULL,
    list_name     TEXT NOT NULL,            -- "FamilyCapital Top 100 SFOs 2024", "EisnerAmper FO Survey 2024", ...
    url           TEXT NOT NULL,
    extracted_at  TEXT NOT NULL,
    FOREIGN KEY (fo_id) REFERENCES family_offices(fo_id)
);

CREATE TABLE IF NOT EXISTS aliases (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    fo_id    TEXT NOT NULL,
    alias    TEXT NOT NULL,
    seen_in  TEXT,                          -- source where this alias appeared
    FOREIGN KEY (fo_id) REFERENCES family_offices(fo_id),
    UNIQUE(fo_id, alias)
);
"""


def connect(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    """Open (and create if absent) the SQLite DB."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    """Initialise schema (idempotent)."""
    conn = connect(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def upsert_fo(
    conn: sqlite3.Connection,
    fo_id: str,
    canonical_name: str,
    **kwargs,
) -> None:
    """Insert or update a family_offices row by fo_id."""
    cols = ["fo_id", "canonical_name", *kwargs.keys()]
    vals = [fo_id, canonical_name, *kwargs.values()]
    placeholders = ", ".join("?" * len(cols))
    update_clause = ", ".join(f"{c}=excluded.{c}" for c in cols if c != "fo_id")
    conn.execute(
        f"""
        INSERT INTO family_offices ({", ".join(cols)})
        VALUES ({placeholders})
        ON CONFLICT(fo_id) DO UPDATE SET {update_clause}
        """,
        vals,
    )
    conn.commit()


if __name__ == "__main__":
    conn = init_db()
    print(f"Initialised DB at {DB_PATH}")
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    print("Tables:", [t[0] for t in tables])
    conn.close()
