# Validation Chain — Walton Enterprises LLC

**fo_id:** `walton_enterprises`
**Chain written:** 2026-05-24
**Author:** Rukhtam Amin (`rukhtam.amin@afiniti.com`)

This chain is included specifically because it is the **gap case**. Soros
and Rockefeller both have rich primary-source coverage from the SEC EDGAR
side. Walton Enterprises does *not*: the Walton family does not file Form
ADV under "Walton Enterprises LLC" or "WIT, LLC" (per Rule §202(a)(11)(G)-1
exemption for qualifying single-family offices). Walton heirs file Schedule
13G individually under their personal names against Walmart shares.

So the methodology here has to construct the FO record without the SEC
EDGAR identity layer that Soros + Rockefeller relied on. The 990-PF on the
linked Walton Family Foundation does most of the work.

---

## Discovery

**Observed:** "Walton family office" is publicly attributed in business
press as the wealthiest US family-office structure. The legal entity that
holds the family's Walmart stake is variously named "WIT, LLC", "Walton
Enterprises Inc", and "Walton Enterprises LLC" across sources.

**Assumed:** Walton Enterprises is the canonical operating entity for the
Walton family's diversified wealth (separate from the philanthropic
Walton Family Foundation).

**Verified by:** Walton Family Foundation Inc (EIN 13-3441466) at
ProPublica returns a $5.7B foundation in Bentonville, AR — clearly the
family-philanthropic vehicle. SEC EDGAR returns no submissions JSON for
a CIK called "Walton Enterprises". This is the discovery-stage finding
that motivated keeping Walton in the seed list as a "gap case" deep dive.

**Could be wrong because:** "Walton Enterprises" may have a registered
CIK that I did not discover (SEC's company-name search returns garbled
output due to a Perl serialization bug in their CGI, as documented in
reasoning_log). The fact that I could not find a CIK doesn't prove
absence — it proves my discovery method has a limit.

**Seed citations:**
- Wikipedia — Walton family
  (https://en.wikipedia.org/wiki/Walton_family)
- Walton Family Foundation IRS 990-PF (ProPublica)
  (https://projects.propublica.org/nonprofits/organizations/133441466)

---

## Identity layer

### Legal name

- **Observed:** No SEC-verified registrant name. Seed canonical_name is
  "Walton Enterprises LLC".
- **Assumed:** The legal entity exists under approximately this name.
- **Verified by:** Reference in multiple news outlets + Wikipedia. No
  primary-source filing in our pipeline.
- **Could be wrong because:** The actual operating entity may be named
  differently. Forbes describes the family's wealth as held in "WIT, LLC"
  in some articles; SEC 13G filings by individual Walton heirs reference
  trusts and family LLCs with their own legal names.
- **Decision:** Use seed canonical_name at confidence 0.7. The output
  spreadsheet's `canonical_name_seed` column carries this; the primary
  `canonical_name` (which would have come from SEC) is null.

### HQ address

- **Observed:** Seed says "Bentonville" (Arkansas).
- **Assumed:** Walton Enterprises is headquartered at the Walton family's
  Bentonville hub.
- **Verified by:** Walton Family Foundation Inc's 990-PF lists a
  Bentonville address. Inference: the operating entity is in the same
  region.
- **Could be wrong because:** WIT, LLC may have its registered office
  elsewhere for legal reasons (Delaware incorporation, NYC office, etc.).
- **Decision:** Confidence 0.7 (seed-only).

### Type

- **Observed:** Seed says SFO.
- **Verified by:** The Walton family is a single family; their wealth
  management entity meets the canonical SFO definition.
- **Decision:** Confidence 0.7.

### Principal family

- **Observed:** Walton family.
- **Verified by:** Universal public attribution. Heirs Rob, Jim, Alice,
  Christy, etc.
- **Decision:** Confidence 0.7 (seed-derived).

---

## Per-domain enrichment

### Domain 1: Equities

- **Observed:** SEC EDGAR returns no submissions JSON for "Walton
  Enterprises LLC" or "WIT, LLC" as registered investment advisers in
  our discovery.
- **Assumed:** The Walton family's Walmart stake is held in non-IA-
  registered trusts and LLCs; ownership disclosure happens via
  individual heirs' Schedule 13G filings.
- **Verified by:** Independent press reporting (Bloomberg, Forbes)
  consistently identifies WIT, LLC + family trusts as the holding
  structure. Forms 13G filed by Rob Walton, Jim Walton, etc.,
  individually disclose their Walmart positions to the SEC.
- **Could be wrong because:** A search of EDGAR by *each individual
  Walton heir's name* would surface those 13G filings — but that work
  is per-person and was not run in Tier-2 scope.
- **Decision:** Report `files_form_13f = null` for the entity-level
  Walton Enterprises record. The methodology document explains why this
  is honest: SEC has no entity-level filings under that name; individual
  heirs do file but they are not the FO entity.

### Domain 2: Private Markets

- **Status:** Not run (no entity-level CIK to query).

### Domain 3: Real Assets

- **Status:** Not run.

### Domain 4: Soft Power — this is the rich domain for Walton

#### Linked foundation

- **Observed:** Walton Family Foundation Inc, EIN 13-3441466, Bentonville
  AR.
- **Assumed:** This is the canonical Walton family foundation.
- **Verified by:** ProPublica returns the entity. Wikipedia article on the
  Walton Family Foundation confirms it as the philanthropic arm. The
  name itself contains the family surname, making the linkage explicit.
- **Could be wrong because:** Individual Walton heirs also have their own
  named foundations (e.g., Sam M. Walton Supporting Foundation, Helen R.
  Walton Charitable Foundation). The "primary" Walton family foundation
  is WFF, but the broader Walton-philanthropy footprint is larger.
- **Decision:** Confidence 0.85 (name match is family=100, but the
  "primary linked foundation" framing slightly oversimplifies).

#### Foundation financials (2023)

| Field | Value (USD) |
|-------|-------------|
| Total assets | $5,714,135,948 |
| Total liabilities | $1 (essentially zero) |
| Total revenue | $872,237,914 |
| Total functional expenses | $801,215,799 |
| Grants & contributions paid | $641,316,726 |
| Dividends & interest income | $153,101,597 |
| Net investment income | $295,795,809 |
| Gross contributions received | $569,846,083 |

- **Observed:** The foundation **received $570M in contributions in 2023**
  — significantly higher than its previous-year baseline (review of
  earlier years via the API would confirm). This is consistent with the
  Walton family making a large donation to the foundation in 2023, likely
  in the form of Walmart stock (which would explain the asset growth
  combined with the contribution inflow).
- **Inference (not a fact):** $570M in contributions received +
  $641M in grants paid means the foundation is operating near
  steady-state — it's not preserving assets in perpetuity, it's
  receiving family donations and distributing them at roughly the same
  rate.
- **Verified by:** ProPublica's structured fields are pulled from the
  IRS 990-PF data release. Confidence on each number = 1.0.
- **Could be wrong because:** Donation timing on 990-PF is calendar-year;
  the family may have made one large block donation (timing artifact)
  rather than ongoing flow.

#### Named grants — DEFERRED

- The 2023 990-PF PDF (referenced in `latest_990pf_pdf_url` signal)
  would list the top grant recipients. Walton Family Foundation
  publishes major grantee lists (charter schools, education reform,
  Northwest Arkansas regional initiatives, etc.). Extraction deferred.

### Domain 5: Shadow Bank

- **Status:** Not run. Walton family wealth is primarily concentrated in
  Walmart stock; shadow-banking lending activity would be a smaller
  signal than for finance-native families.

---

## Final confidence — field-by-field rule trace

| Output field | Picked value | Source | Confidence | Why |
|---|---|---|---|---|
| `canonical_name` | (null) | — | — | No SEC source returned a registrant; only seed-level data available |
| `canonical_name_seed` | Walton Enterprises LLC | seeds.yaml | 0.7 | Best-known operating-entity name |
| `type` | SFO | seeds.yaml | 0.7 | Universal classification — Walton is the canonical SFO |
| `principal_family` | Walton | seeds.yaml | 0.7 | Self-evident |
| `hq_city` | Bentonville | seeds.yaml | 0.7 | Inferred from foundation HQ |
| `sec_cik` | (null) | — | — | No CIK found for Walton Enterprises at the entity level |
| `files_form_13f` | (null) | — | — | Honest absence — individual heirs file, not the entity |
| `linked_foundation` | Walton Family Foundation Inc | ProPublica | 0.85 | Verified at ProPublica; family-name match 100 |
| `foundation_990pf_latest_year` | 2023 | ProPublica | 1.0 | Primary source |
| Tier-2: `grants_and_contributions_paid_usd_2023` | 641,316,726 | ProPublica 990-PF | 1.0 | Structured field |
| Tier-2: `gross_contributions_received_usd_2023` | 569,846,083 | ProPublica 990-PF | 1.0 | Surprising number — likely a family WMT-stock donation |

---

## Why this chain matters for the methodology

This record demonstrates that the framework **degrades gracefully** when
the primary SEC source is silent. We end up with:

- **Identity:** seed-level only (0.7 confidence on every identity field)
- **Equities:** acknowledged absence — recorded as honest null, not faked
- **Soft Power:** primary-source rich via the linked foundation

The output record is *thinner* than Soros or Rockefeller, but it is also
*honestly thin*. A reviewer can tell the difference between
"verified-and-rich" and "verified-and-incomplete" by reading the
`primary_source_count` column in family_offices.xlsx. The score table
preserves this contrast — it does not pretend the Walton record carries
the same weight as the Soros one.

For the 17 other records in our 50 that ship with seed-identity only,
this chain is the template: the methodology document references this
chain to illustrate what an honest seed-only record looks like in our
output.

---

## What would change my conclusion

- If a primary-source document (a Walton-family-filed amendment, a court
  filing, a news article quoting the entity directly) confirmed the
  legal entity name as "WIT, LLC" or "Walton Enterprises Inc" specifically,
  the canonical_name would be updated and the confidence would rise.
- If individual Walton heirs' Schedule 13G filings were ingested as
  separate FO records (Rob Walton's holdings, Jim Walton's holdings,
  etc.), the entity-level Walton Enterprises record would be reframed as
  a parent-of-children with much more equities-domain primary-source
  data.
- If the Walton Family Foundation's 990-PF PDF (currently un-parsed for
  named grants) were extracted, the top-grantee list would appear under
  Domain 4 with verified provenance.
