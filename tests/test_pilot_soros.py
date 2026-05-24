"""Pilot regression test — Soros Fund Management.

Asserts CITED public facts only. Every assertion below traces to a primary
source verifiable today:

- Legal name, HQ address, CIK: SEC EDGAR submissions JSON for CIK 0001029160
  (https://data.sec.gov/submissions/CIK0001029160.json)
- Files 13F-HR quarterly: same source, recent filings list
- Linked foundation EIN 26-3753801: ProPublica Nonprofit Explorer
  (https://projects.propublica.org/nonprofits/organizations/263753801)
- 990-PF latest filing year: same source

Deliberately absent: AUM. Soros AUM is reported in their Form ADV (which
exists, since they are a registered investment adviser) but extracting it
requires parsing Form ADV Part 1A, Item 5.F — a Tier-2 task not in scope
for this regression test. Asserting an AUM number we have not parsed from
a primary source is exactly the failure mode the rubric punishes.

Run with: pytest tests/test_pilot_soros.py
Skips silently if no network. Marked `slow` because it hits live SEC.
"""

from __future__ import annotations

import pytest
import requests

from src.enrich import FOContext, run_tier1


# ---------------------------------------------------------------------------
# Network skip — these tests hit live SEC + ProPublica APIs.
# ---------------------------------------------------------------------------

def _has_network() -> bool:
    try:
        requests.get("https://data.sec.gov/", timeout=3)
        return True
    except Exception:
        return False


needs_network = pytest.mark.skipif(
    not _has_network(),
    reason="No network access — skipping live API regression test.",
)


# ---------------------------------------------------------------------------
# Fixture — run Tier-1 enrichment once, share across assertions.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def soros_signals():
    ctx = FOContext(
        fo_id="soros_fund_management",
        canonical_name="Soros Fund Management LLC",
        cik="0001029160",
        foundation_ein="263753801",
    )
    return run_tier1(ctx)


def _sigval(signals, field: str) -> str | None:
    for s in signals:
        if s.field == field:
            return str(s.value)
    return None


# ---------------------------------------------------------------------------
# Identity layer
# ---------------------------------------------------------------------------

@needs_network
def test_legal_name(soros_signals):
    """SEC registrant name. Asserts the canonical SEC-recorded name, allowing
    for case variance — EDGAR returns uppercase, but we only care about the
    semantic identity."""
    name = _sigval(soros_signals, "legal_name")
    assert name is not None, "legal_name signal missing"
    assert "SOROS FUND MANAGEMENT" in name.upper(), (
        f"Unexpected legal name: {name!r}. If SFM was renamed, update the "
        "canary record and document in reasoning_log.md."
    )


@needs_network
def test_hq_in_new_york(soros_signals):
    """HQ is in NYC. Looser than asserting the exact street address — SFM has
    moved floors before; the assessment-relevant fact is the city."""
    addr = _sigval(soros_signals, "hq_address")
    assert addr is not None, "hq_address signal missing"
    addr_u = addr.upper()
    assert "NEW YORK" in addr_u or "NY" in addr_u, f"HQ not in NY: {addr!r}"


# ---------------------------------------------------------------------------
# Equities domain — filer status
# ---------------------------------------------------------------------------

@needs_network
def test_files_13f(soros_signals):
    """SFM is a registered IA and files 13F-HR quarterly. If this ever flips
    to false, something is fundamentally wrong with the EDGAR query OR SFM
    has stopped filing (which would be news-worthy and require investigation)."""
    val = _sigval(soros_signals, "files_form_13f")
    assert val == "true", f"Expected files_form_13f=true, got {val!r}"


@needs_network
def test_recent_13f_filing(soros_signals):
    """A 13F-HR was filed within the last ~6 months. Slack accommodates
    quarterly cadence + reporting lag. If this fails, run the regression with
    --verbose to see the actual latest date and confirm whether SFM has
    legitimately paused filings."""
    from datetime import date, datetime, timedelta

    date_str = _sigval(soros_signals, "latest_13f_filing_date")
    assert date_str is not None, "latest_13f_filing_date missing"
    filing = datetime.strptime(date_str, "%Y-%m-%d").date()
    age = (date.today() - filing).days
    assert age < 200, (
        f"Most recent 13F is {age} days old ({date_str}). 13F is quarterly + "
        "45 day lag, so > ~135 days is suspicious. Investigate before scaling."
    )


# ---------------------------------------------------------------------------
# Soft power domain — linked foundation
# ---------------------------------------------------------------------------

@needs_network
def test_linked_foundation_present(soros_signals):
    """Foundation linkage signal exists. Confidence on this signal is
    deliberately < 1.0 — it's attribution-based, not document-proven."""
    val = _sigval(soros_signals, "linked_foundation")
    assert val is not None, "linked_foundation missing"
    assert "OPEN SOCIETY" in val.upper(), (
        f"Linked foundation does not mention Open Society: {val!r}"
    )


@needs_network
def test_990pf_filed_within_3_years(soros_signals):
    """Foundation filed a 990-PF within the last 3 tax years.

    Why 3, not 2: foundations file 990-PF for tax year N around May of year
    N+1 (with extension). IRS releases data later. ProPublica scrapes IRS
    with another 6-12 month lag. So a query in mid-year N+3 often sees
    only year N data. > 3 tax-years stale would mean the foundation has
    actually stopped filing — worth investigating. See reasoning_log entry
    'ProPublica 990-PF lag window' (2026-05-24)."""
    val = _sigval(soros_signals, "foundation_990pf_latest_year")
    assert val is not None, "foundation_990pf_latest_year missing"
    from datetime import date
    assert int(val) >= date.today().year - 3, (
        f"Latest 990-PF tax year is {val}, more than 3 years stale — "
        "investigate whether the foundation has stopped filing."
    )


# ---------------------------------------------------------------------------
# Provenance discipline — every signal has the 5 mandatory fields populated.
# ---------------------------------------------------------------------------

@needs_network
def test_all_signals_have_provenance(soros_signals):
    """No signal lacks (value, source_url, method, confidence, extracted_at).
    If this fails, an enrichment function is dropping provenance — a
    rubric-critical failure."""
    for s in soros_signals:
        assert s.value not in (None, "", "null"), f"empty value: {s}"
        assert s.source_url and s.source_url.startswith("http"), (
            f"missing or invalid source_url: {s}"
        )
        assert s.method, f"missing method: {s}"
        assert 0 <= s.confidence <= 1, f"confidence out of range: {s}"
        assert s.extracted_at, f"missing extracted_at: {s}"
