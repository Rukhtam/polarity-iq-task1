"""Provenance primitives.

Every enrichment function returns Signal records. Score reads them. The
defensibility of the dataset lives in the (value, source_url, extracted_at,
confidence, method) tuple — never store a value without all five.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


# Confidence is a float in [0, 1]. We resist mapping to discrete buckets at
# this layer — score_and_export.py is allowed to colour-code at export time.
Confidence = float


@dataclass
class Signal:
    fo_id: str            # canonical FO identifier (slug)
    field: str            # e.g. "legal_name", "hq_address", "recent_investment"
    domain: str           # one of: identity, equities, private, real_assets, soft_power, shadow_bank
    value: Any            # primitive or JSON-serialisable structure
    source_url: str       # the *primary* source URL — not a homepage
    method: str           # how it was obtained: "sec_edgar", "propublica_990pf", "manual_linkedin", ...
    confidence: Confidence
    extracted_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    notes: str | None = None

    def as_row(self) -> tuple:
        """Map to the schema in db.py:signals table."""
        return (
            self.fo_id,
            self.field,
            self.domain,
            json.dumps(self.value) if not isinstance(self.value, (str, int, float)) else str(self.value),
            self.source_url,
            self.method,
            self.confidence,
            self.extracted_at,
            self.notes,
        )


def record_signal(conn: sqlite3.Connection, sig: Signal) -> int:
    """Insert a Signal, return its rowid."""
    cur = conn.execute(
        """
        INSERT INTO signals (
            fo_id, field, domain, value, source_url, method,
            confidence, extracted_at, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        sig.as_row(),
    )
    conn.commit()
    return cur.lastrowid


def record_signals(conn: sqlite3.Connection, signals: list[Signal]) -> int:
    """Bulk insert. Returns count inserted."""
    rows = [s.as_row() for s in signals]
    conn.executemany(
        """
        INSERT INTO signals (
            fo_id, field, domain, value, source_url, method,
            confidence, extracted_at, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    return len(rows)
