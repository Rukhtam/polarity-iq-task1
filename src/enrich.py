"""Per-domain enrichment functions.

Each function takes an FO context (canonical name, identifiers we have so
far) and returns a list of Signal records. The functions are pure with
respect to the DB — the orchestrator decides whether to persist.

Tier-1 (run on all 50): SEC EDGAR metadata, ProPublica 990-PF metadata,
identity cross-checks. Cheap, deterministic, no LLM.

Tier-2 (run on 3 deep-dives): SEC 13F holdings parsing, 990-PF grant
extraction from PDF, OpenCorporates shell-entity search, state UCC-1
search. Slower, sometimes LLM-assisted.

This file deliberately keeps all enrichment in ONE module — the brutal
review flagged the 5-subdirectory layout as over-engineered for a 48-hour
build. One file, function dispatch by domain, is easier to debug.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass

import requests
from dotenv import load_dotenv

from .provenance import Signal

load_dotenv()

SEC_USER_AGENT = os.environ.get(
    "SEC_USER_AGENT",
    "polarity-iq-task1 contact@example.com",
)


@dataclass
class FOContext:
    """Minimal context the enrichment functions need.

    Populated from the candidates.csv seed + whatever earlier enrichment
    steps have already discovered for this FO.
    """

    fo_id: str
    canonical_name: str
    cik: str | None = None             # SEC EDGAR CIK (10-digit zero-padded string)
    foundation_ein: str | None = None  # 9-digit IRS EIN without dash, or None
    hq_address: str | None = None
    aliases: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# SEC EDGAR — equities & private market filings via the submissions JSON API
# ---------------------------------------------------------------------------

EDGAR_BASE = "https://data.sec.gov"
EDGAR_THROTTLE_SEC = 0.15  # SEC asks for <=10 req/sec; this is 6.6/sec safe


def _edgar_get(path: str, params: dict | None = None) -> dict:
    """GET against data.sec.gov with the required User-Agent.

    SEC requires a contact email in the UA string; without it, requests get
    403'd. See https://www.sec.gov/os/accessing-edgar-data.
    """
    url = f"{EDGAR_BASE}{path}"
    headers = {"User-Agent": SEC_USER_AGENT, "Accept": "application/json"}
    resp = requests.get(url, headers=headers, params=params, timeout=15)
    resp.raise_for_status()
    time.sleep(EDGAR_THROTTLE_SEC)
    return resp.json()


def _cik_zero_pad(cik: str | int) -> str:
    """EDGAR submission URLs require 10-digit zero-padded CIK."""
    return str(cik).lstrip("0").zfill(10) or "0000000000"


def fetch_sec_edgar(ctx: FOContext) -> list[Signal]:
    """Tier-1 SEC enrichment: filer status, recent filings metadata.

    Returns Signal records for: legal_name (as registered with SEC),
    hq_address (per EDGAR), files_form_13f (bool), latest_13f_filing_date,
    files_schedule_13gd (bool), latest_form_d_date.

    No holdings parsing here — that's Tier-2.
    """
    if not ctx.cik:
        return []

    cik = _cik_zero_pad(ctx.cik)
    submissions_url = f"https://data.sec.gov/submissions/CIK{cik}.json"

    try:
        d = _edgar_get(f"/submissions/CIK{cik}.json")
    except requests.HTTPError as e:
        # 404 = no such CIK; not a bug, just an absent filer.
        if e.response is not None and e.response.status_code == 404:
            return []
        raise

    sigs: list[Signal] = []

    name = d.get("name")
    if name:
        sigs.append(Signal(
            fo_id=ctx.fo_id, field="legal_name", domain="identity",
            value=name, source_url=submissions_url,
            method="sec_edgar_submissions",
            confidence=1.0,
            notes="Exact registrant name from SEC EDGAR.",
        ))

    addr = (d.get("addresses") or {}).get("business") or {}
    addr_str = ", ".join(
        v for v in (
            addr.get("street1"), addr.get("street2"),
            addr.get("city"), addr.get("stateOrCountry"),
            addr.get("zipCode"),
        )
        if v
    )
    if addr_str:
        sigs.append(Signal(
            fo_id=ctx.fo_id, field="hq_address", domain="identity",
            value=addr_str, source_url=submissions_url,
            method="sec_edgar_submissions",
            confidence=1.0,
        ))

    recent = (d.get("filings") or {}).get("recent") or {}
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accs = recent.get("accessionNumber", [])

    def _latest(form_match) -> tuple[str, str] | None:
        for i, f in enumerate(forms):
            if form_match(f):
                return dates[i], accs[i]
        return None

    f13f = _latest(lambda f: f == "13F-HR")
    sigs.append(Signal(
        fo_id=ctx.fo_id, field="files_form_13f", domain="equities",
        value="true" if f13f else "false",
        source_url=submissions_url,
        method="sec_edgar_submissions",
        confidence=1.0,
    ))
    if f13f:
        date, acc = f13f
        sigs.append(Signal(
            fo_id=ctx.fo_id, field="latest_13f_filing_date", domain="equities",
            value=date, source_url=submissions_url,
            method="sec_edgar_submissions",
            confidence=1.0,
            notes=f"Accession {acc}.",
        ))

    f13gd = _latest(lambda f: f in ("SCHEDULE 13G", "SCHEDULE 13D", "SC 13G", "SC 13D"))
    sigs.append(Signal(
        fo_id=ctx.fo_id, field="files_schedule_13gd", domain="equities",
        value="true" if f13gd else "false",
        source_url=submissions_url,
        method="sec_edgar_submissions",
        confidence=1.0,
    ))

    formd = _latest(lambda f: f == "D" or f.startswith("D/A"))
    if formd:
        date, acc = formd
        sigs.append(Signal(
            fo_id=ctx.fo_id, field="latest_form_d_date", domain="private",
            value=date, source_url=submissions_url,
            method="sec_edgar_submissions",
            confidence=1.0,
            notes=f"Form D accession {acc}.",
        ))

    return sigs


# ---------------------------------------------------------------------------
# ProPublica Nonprofit Explorer — 990-PF metadata for linked foundations
# ---------------------------------------------------------------------------

PROPUBLICA_BASE = "https://projects.propublica.org/nonprofits/api/v2"


def fetch_propublica_990pf(ctx: FOContext) -> list[Signal]:
    """Tier-1 990-PF enrichment: foundation metadata + latest filing year.

    Requires ctx.foundation_ein. If absent, returns empty list — linkage
    research is a separate (and not always answerable) step.

    No PDF grant extraction here — that's Tier-2.
    """
    if not ctx.foundation_ein:
        return []

    ein = ctx.foundation_ein.replace("-", "")
    url = f"{PROPUBLICA_BASE}/organizations/{ein}.json"
    page_url = f"https://projects.propublica.org/nonprofits/organizations/{ein}"
    resp = requests.get(url, timeout=15, headers={"User-Agent": SEC_USER_AGENT})
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    d = resp.json()

    org = d.get("organization") or {}
    filings = d.get("filings_with_data") or []
    sigs: list[Signal] = []

    name = org.get("name")
    if name:
        sigs.append(Signal(
            fo_id=ctx.fo_id, field="linked_foundation", domain="soft_power",
            value=name, source_url=page_url,
            method="propublica_np_explorer",
            confidence=0.85,
            notes=(
                "Confidence < 1.0 because the FO↔foundation linkage is "
                "by attribution. Promote to 1.0 if a primary document "
                "(990-PF schedule, FO website disclosure) confirms control."
            ),
        ))

    if filings:
        latest = max(filings, key=lambda f: f.get("tax_prd_yr") or 0)
        sigs.append(Signal(
            fo_id=ctx.fo_id, field="foundation_990pf_latest_year",
            domain="soft_power",
            value=str(latest.get("tax_prd_yr")),
            source_url=page_url,
            method="propublica_np_explorer",
            confidence=1.0,
        ))
        rev = latest.get("totrevenue")
        if rev is not None:
            sigs.append(Signal(
                fo_id=ctx.fo_id,
                field=f"foundation_990pf_{latest.get('tax_prd_yr')}_revenue_usd",
                domain="soft_power",
                value=str(rev), source_url=page_url,
                method="propublica_np_explorer",
                confidence=1.0,
            ))
        pdf = latest.get("pdf_url")
        if pdf:
            sigs.append(Signal(
                fo_id=ctx.fo_id, field="latest_990pf_pdf_url",
                domain="soft_power",
                value=pdf, source_url=page_url,
                method="propublica_np_explorer",
                confidence=1.0,
            ))

    return sigs


# ---------------------------------------------------------------------------
# Tier-1 dispatch
# ---------------------------------------------------------------------------

def run_tier1(ctx: FOContext) -> list[Signal]:
    """Run all Tier-1 enrichment for one FO.

    Order matters only for cost / failure isolation: cheap deterministic
    sources first, paid LLM sources last.
    """
    sigs: list[Signal] = []
    sigs += fetch_sec_edgar(ctx)
    sigs += fetch_propublica_990pf(ctx)
    return sigs


if __name__ == "__main__":
    # Smoke-test on Soros
    ctx = FOContext(
        fo_id="soros_fund_management",
        canonical_name="Soros Fund Management LLC",
        cik="0001029160",
        foundation_ein="263753801",
    )
    sigs = run_tier1(ctx)
    print(f"Got {len(sigs)} signals for {ctx.fo_id}")
    for s in sigs:
        v = str(s.value)
        v_disp = v if len(v) < 60 else v[:57] + "..."
        print(f"  [{s.domain:10s}] {s.field:30s} = {v_disp!r}  (conf={s.confidence})")
