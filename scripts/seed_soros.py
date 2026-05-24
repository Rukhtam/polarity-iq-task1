"""Seed the SQLite DB with the Soros pilot record.

Every fact has a primary-source URL. This script is the bridge between
hand-curation (candidates.csv) and automated enrichment (src/enrich.py).
It's deliberately small — once enrich.py is built, the SEC fetcher will
re-derive most of these signals automatically and we can cross-check.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running as a script from repo root: `python scripts/seed_soros.py`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import init_db, upsert_fo
from src.provenance import Signal, record_signals


SOROS_FO_ID = "soros_fund_management"

# All values below were verified against primary sources on 2026-05-24.
# Method = "manual_curation_from_primary_source" means: I personally
# pulled the value from the cited URL and pasted it here.
SEC_EDGAR_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK0001029160.json"
PROPUBLICA_OSF_URL = "https://projects.propublica.org/nonprofits/organizations/263753801"
EXTRACTED_AT = "2026-05-24T12:00:00+00:00"


SIGNALS = [
    Signal(
        fo_id=SOROS_FO_ID,
        field="legal_name",
        domain="identity",
        value="SOROS FUND MANAGEMENT LLC",
        source_url=SEC_EDGAR_SUBMISSIONS_URL,
        method="manual_curation_from_primary_source",
        confidence=1.0,
        extracted_at=EXTRACTED_AT,
        notes="Exact registrant name from SEC EDGAR submissions JSON.",
    ),
    Signal(
        fo_id=SOROS_FO_ID,
        field="cik",
        domain="identity",
        value="0001029160",
        source_url=SEC_EDGAR_SUBMISSIONS_URL,
        method="manual_curation_from_primary_source",
        confidence=1.0,
        extracted_at=EXTRACTED_AT,
    ),
    Signal(
        fo_id=SOROS_FO_ID,
        field="hq_address",
        domain="identity",
        value="250 West 55th Street, Floor 29, New York, NY 10019",
        source_url=SEC_EDGAR_SUBMISSIONS_URL,
        method="manual_curation_from_primary_source",
        confidence=1.0,
        extracted_at=EXTRACTED_AT,
        notes="Business address per most recent EDGAR filing.",
    ),
    Signal(
        fo_id=SOROS_FO_ID,
        field="files_form_13f",
        domain="equities",
        value="true",
        source_url=SEC_EDGAR_SUBMISSIONS_URL,
        method="manual_curation_from_primary_source",
        confidence=1.0,
        extracted_at=EXTRACTED_AT,
        notes="EDGAR shows 13F-HR filings 2024-Q3 through 2026-Q1.",
    ),
    Signal(
        fo_id=SOROS_FO_ID,
        field="latest_13f_filing_date",
        domain="equities",
        value="2026-05-15",
        source_url=SEC_EDGAR_SUBMISSIONS_URL,
        method="manual_curation_from_primary_source",
        confidence=1.0,
        extracted_at=EXTRACTED_AT,
        notes="Accession 0000902664-26-002529 (13F-HR).",
    ),
    Signal(
        fo_id=SOROS_FO_ID,
        field="linked_foundation",
        domain="soft_power",
        value="Foundation To Promote Open Society",
        source_url=PROPUBLICA_OSF_URL,
        method="manual_curation_from_primary_source",
        confidence=0.85,
        extracted_at=EXTRACTED_AT,
        notes=(
            "EIN 26-3753801. Linkage to SFM is by public attribution (Soros "
            "Open Society network), not by document — confidence reduced "
            "accordingly. Direct legal-linkage proof would lift to 1.0."
        ),
    ),
    Signal(
        fo_id=SOROS_FO_ID,
        field="foundation_990pf_latest_year",
        domain="soft_power",
        value="2023",
        source_url=PROPUBLICA_OSF_URL,
        method="manual_curation_from_primary_source",
        confidence=1.0,
        extracted_at=EXTRACTED_AT,
        notes="ProPublica Nonprofit Explorer shows 2023, 2022, 2021 990-PF filings on file.",
    ),
    Signal(
        fo_id=SOROS_FO_ID,
        field="foundation_990pf_2023_revenue_usd",
        domain="soft_power",
        value="842821637",
        source_url=PROPUBLICA_OSF_URL,
        method="manual_curation_from_primary_source",
        confidence=1.0,
        extracted_at=EXTRACTED_AT,
        notes="Total revenue 2023 990-PF (Foundation To Promote Open Society).",
    ),
]


def main() -> None:
    conn = init_db()
    upsert_fo(
        conn,
        fo_id=SOROS_FO_ID,
        canonical_name="Soros Fund Management LLC",
        type="MFO",
        hq_address="250 West 55th Street, Floor 29",
        hq_city="New York, NY",
        hq_country="US",
        sec_crd=None,
        ein=None,
        foundation_ein="26-3753801",
        notes="Pilot canary record. CIK 0001029160.",
    )
    # Replace existing pilot signals so the script is idempotent.
    conn.execute("DELETE FROM signals WHERE fo_id = ?", (SOROS_FO_ID,))
    n = record_signals(conn, SIGNALS)
    print(f"Seeded {n} signals for {SOROS_FO_ID}")
    rows = conn.execute(
        "SELECT field, value, confidence FROM signals WHERE fo_id = ? ORDER BY signal_id",
        (SOROS_FO_ID,),
    ).fetchall()
    for r in rows:
        print(f"  {r[0]:30s} = {r[1]!r:50s}  conf={r[2]}")
    conn.close()


if __name__ == "__main__":
    main()
