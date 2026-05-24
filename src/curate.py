"""Discovery + verification pipeline.

Reads data/seeds.yaml (human-curated candidate FOs with public-source
citations) and verifies the identifier hints (SEC CIK, ProPublica EIN)
against live APIs. Writes data/candidates.csv with verification status
per row so the human review step can target what actually needs
re-research.

Run:
    python -m src.curate

Re-running is idempotent: existing rows in candidates.csv are overwritten
with the latest verification status.

Verification model:
  - hint_cik present  → fetch submissions JSON, fuzzy-match registrant name
                        against canonical_name + aliases.
                        Score >= 0.70 → verified. < 0.70 → hint_rejected.
  - hint_cik absent   → marked "skipped" (Tier-2 discovery via name search
                        is future work; doing it well requires LLM-assisted
                        disambiguation that we'll add only if Tier-1 yield
                        is too low).
  - hint_foundation_ein present → ProPublica `/organizations/<ein>.json`,
                                  same fuzzy-match logic vs principal_family
                                  + canonical_name tokens.
  - hint_foundation_ein absent  → "skipped".

The brutal review's point: it's better to ship 50 records where every
hint has been verified than 50 where half are silently wrong.
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv
from rapidfuzz import fuzz

load_dotenv()

SEC_USER_AGENT = os.environ.get(
    "SEC_USER_AGENT",
    "polarity-iq-task1 contact@example.com",
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SEEDS_PATH = REPO_ROOT / "data" / "seeds.yaml"
CANDIDATES_PATH = REPO_ROOT / "data" / "candidates.csv"

# Throttle to comply with SEC's "<=10 req/sec" guidance and ProPublica's
# unstated-but-conservative rate.
THROTTLE_SEC = 0.2

# Match threshold: rapidfuzz token_set_ratio scores out of 100.
NAME_MATCH_THRESHOLD = 70


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Seed:
    fo_id: str
    canonical_name: str
    aliases: list[str]
    type: str
    principal_family: str
    hq_city: str | None
    hq_country: str | None
    hint_cik: str | None
    hint_foundation_ein: str | None
    confidence: str
    seed_citations: list[dict]
    notes: str | None = None


@dataclass
class CandidateRow:
    fo_id: str
    canonical_name: str
    type: str
    principal_family: str
    hq_city: str
    hq_country: str
    a_priori_confidence: str         # seed-level high/medium/low
    verified_cik: str                # empty if not verified
    sec_registrant_name: str         # what SEC actually returned
    sec_status: str                  # verified | hint_rejected | skipped | not_found | error
    verified_foundation_ein: str
    foundation_name: str
    foundation_status: str           # verified | hint_rejected | skipped | not_found | error
    final_status: str                # ready | needs_review | dropped
    seed_citations: str              # joined " | "
    verification_notes: str
    verified_at: str


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_seeds(path: Path = SEEDS_PATH) -> list[Seed]:
    """Parse seeds.yaml into Seed objects. Fail loudly on schema violations."""
    with path.open() as f:
        raw = yaml.safe_load(f)
    seeds = []
    for entry in raw.get("seeds", []):
        # Mandatory fields
        for required in ("fo_id", "canonical_name", "seed_citations", "principal_family"):
            if required not in entry:
                raise ValueError(f"Seed missing {required!r}: {entry}")
        if not entry["seed_citations"]:
            raise ValueError(f"Seed has empty seed_citations: {entry['fo_id']}")
        seeds.append(Seed(
            fo_id=entry["fo_id"],
            canonical_name=entry["canonical_name"],
            aliases=entry.get("aliases") or [],
            type=entry.get("type", "Unknown"),
            principal_family=entry["principal_family"],
            hq_city=entry.get("hq_city"),
            hq_country=entry.get("hq_country"),
            hint_cik=entry.get("hint_cik"),
            hint_foundation_ein=entry.get("hint_foundation_ein"),
            confidence=entry.get("confidence", "medium"),
            seed_citations=entry["seed_citations"],
            notes=entry.get("notes"),
        ))
    return seeds


# ---------------------------------------------------------------------------
# SEC EDGAR verification
# ---------------------------------------------------------------------------

def verify_cik(cik: str, seed: Seed) -> tuple[str, str, str]:
    """Hit SEC EDGAR submissions JSON for the given CIK.

    Returns (sec_status, registrant_name, notes).
    """
    cik_padded = str(cik).lstrip("0").zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": SEC_USER_AGENT, "Accept": "application/json"},
            timeout=15,
        )
    except requests.RequestException as e:
        return "error", "", f"request failed: {e}"
    finally:
        time.sleep(THROTTLE_SEC)

    if resp.status_code == 404:
        return "not_found", "", f"CIK {cik_padded} returns 404"
    if not resp.ok:
        return "error", "", f"HTTP {resp.status_code}"

    d = resp.json()
    registrant = d.get("name", "")
    # Compare against canonical_name AND aliases. token_set_ratio is robust
    # to word-order differences ("Smith Investment LLC" vs "LLC Smith Investment").
    candidates = [seed.canonical_name, *seed.aliases]
    best_score = max(
        (fuzz.token_set_ratio(registrant.upper(), c.upper()) for c in candidates),
        default=0,
    )
    if best_score >= NAME_MATCH_THRESHOLD:
        return "verified", registrant, f"name match score={best_score}"
    return "hint_rejected", registrant, (
        f"SEC returned {registrant!r} but seed canonical is {seed.canonical_name!r} "
        f"(best fuzzy match score={best_score} < {NAME_MATCH_THRESHOLD})"
    )


# ---------------------------------------------------------------------------
# ProPublica foundation verification
# ---------------------------------------------------------------------------

def verify_foundation_ein(ein: str, seed: Seed) -> tuple[str, str, str]:
    """Hit ProPublica for the given EIN. Returns (status, foundation_name, notes)."""
    clean = ein.replace("-", "")
    url = f"https://projects.propublica.org/nonprofits/api/v2/organizations/{clean}.json"
    try:
        resp = requests.get(
            url, headers={"User-Agent": SEC_USER_AGENT}, timeout=15,
        )
    except requests.RequestException as e:
        return "error", "", f"request failed: {e}"
    finally:
        time.sleep(THROTTLE_SEC)

    if resp.status_code == 404:
        return "not_found", "", f"EIN {clean} not in ProPublica index"
    if not resp.ok:
        return "error", "", f"HTTP {resp.status_code}"

    d = resp.json()
    org = (d.get("organization") or {})
    name = org.get("name", "")
    # Foundation names rarely match the FO's canonical_name exactly — they
    # usually carry the family surname plus "Foundation" or "Trust".
    # Match against principal_family with a relaxed threshold.
    family_score = fuzz.partial_ratio(name.upper(), seed.principal_family.upper())
    canon_score = fuzz.token_set_ratio(name.upper(), seed.canonical_name.upper())
    best = max(family_score, canon_score)
    if best >= 60:  # foundation linkage is fuzzier than FO identity
        return "verified", name, f"name match (family={family_score}, canon={canon_score})"
    return "hint_rejected", name, (
        f"ProPublica returned {name!r} for EIN {clean}, family={seed.principal_family!r} "
        f"(scores: family={family_score}, canon={canon_score} < 60)"
    )


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def curate() -> list[CandidateRow]:
    seeds = load_seeds()
    print(f"Loaded {len(seeds)} seeds from {SEEDS_PATH.name}")

    rows: list[CandidateRow] = []
    for s in seeds:
        # --- SEC CIK ---
        if s.hint_cik:
            sec_status, sec_name, sec_notes = verify_cik(s.hint_cik, s)
            verified_cik = s.hint_cik if sec_status == "verified" else ""
        else:
            sec_status, sec_name, sec_notes = "skipped", "", "no hint_cik in seed"
            verified_cik = ""

        # --- Foundation EIN ---
        if s.hint_foundation_ein:
            f_status, f_name, f_notes = verify_foundation_ein(s.hint_foundation_ein, s)
            verified_ein = s.hint_foundation_ein if f_status == "verified" else ""
        else:
            f_status, f_name, f_notes = "skipped", "", "no hint_foundation_ein in seed"
            verified_ein = ""

        # --- Final status ---
        # The brutal review's bar: a record can be ready even without SEC
        # verification (most SFOs are exempt), but it cannot be ready if
        # BOTH the SEC and foundation hints exist AND both were rejected.
        sec_ok = sec_status in ("verified", "skipped")
        f_ok = f_status in ("verified", "skipped")
        if sec_status == "hint_rejected" and f_status == "hint_rejected":
            final = "needs_review"
        elif sec_status == "error" or f_status == "error":
            final = "needs_review"
        elif sec_ok and f_ok:
            final = "ready"
        else:
            final = "needs_review"

        seed_cites = " | ".join(
            f"{c['source']}: {c['url']}" for c in s.seed_citations
        )
        notes_combined = "; ".join(
            n for n in (
                f"SEC: {sec_notes}" if sec_notes else None,
                f"Foundation: {f_notes}" if f_notes else None,
                s.notes,
            ) if n
        )

        rows.append(CandidateRow(
            fo_id=s.fo_id,
            canonical_name=s.canonical_name,
            type=s.type,
            principal_family=s.principal_family,
            hq_city=s.hq_city or "",
            hq_country=s.hq_country or "",
            a_priori_confidence=s.confidence,
            verified_cik=verified_cik,
            sec_registrant_name=sec_name,
            sec_status=sec_status,
            verified_foundation_ein=verified_ein,
            foundation_name=f_name,
            foundation_status=f_status,
            final_status=final,
            seed_citations=seed_cites,
            verification_notes=notes_combined,
            verified_at=datetime.now(timezone.utc).isoformat(),
        ))
        # Console progress
        flag = {"ready": "OK", "needs_review": "??", "dropped": "XX"}.get(final, "  ")
        print(f"  [{flag}] {s.fo_id:35s}  sec={sec_status:13s}  fnd={f_status:13s}")

    return rows


def write_candidates(rows: list[CandidateRow], path: Path = CANDIDATES_PATH) -> None:
    if not rows:
        print("No rows to write.")
        return
    fields = list(asdict(rows[0]).keys())
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(asdict(r))
    print(f"Wrote {len(rows)} rows → {path}")


def summarise(rows: list[CandidateRow]) -> None:
    from collections import Counter
    print()
    print("=" * 60)
    print(f"Total candidates: {len(rows)}")
    print(f"  ready:        {sum(1 for r in rows if r.final_status == 'ready')}")
    print(f"  needs_review: {sum(1 for r in rows if r.final_status == 'needs_review')}")
    print(f"  dropped:      {sum(1 for r in rows if r.final_status == 'dropped')}")
    print()
    print("SEC status breakdown:")
    for status, n in Counter(r.sec_status for r in rows).most_common():
        print(f"  {status:15s} {n}")
    print()
    print("Foundation status breakdown:")
    for status, n in Counter(r.foundation_status for r in rows).most_common():
        print(f"  {status:15s} {n}")
    print()
    rejected = [r for r in rows if r.sec_status == "hint_rejected" or r.foundation_status == "hint_rejected"]
    if rejected:
        print(f"{len(rejected)} entries have rejected hints — review these:")
        for r in rejected:
            print(f"  - {r.fo_id}")
            if r.sec_status == "hint_rejected":
                print(f"      SEC: hint was wrong. {r.verification_notes}")
            if r.foundation_status == "hint_rejected":
                print(f"      Foundation: hint was wrong. {r.verification_notes}")


if __name__ == "__main__":
    rows = curate()
    write_candidates(rows)
    summarise(rows)
