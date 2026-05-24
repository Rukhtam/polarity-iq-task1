# Validation Chain — Rockefeller Capital Management LP

**fo_id:** `rockefeller_capital_management`
**Chain written:** 2026-05-24
**Author:** Rukhtam Amin (`rukhtam.amin@afiniti.com`)

This chain validates a record where the FO is a registered SEC adviser with
substantial primary-source coverage and a linked private foundation. It is
the second of three deep-dive chains, complementing the Soros chain (similar
structure, different family) and the Walton chain (where the primary SEC
source is silent for the FO entity).

---

## Discovery

**Observed:** Rockefeller Capital Management appeared in two of my seed
sources: Wikipedia ("Rockefeller Capital Management" article) and the SEC
EDGAR full-text search where the firm appears as a 13F-HR filer + 13G
filer against Beachbody and other holdings.

**Assumed:** The current legal entity "Rockefeller Capital Management LP"
is the continuation of the historical Rockefeller Family Office, not a
separately-branded successor.

**Verified by:** Wikipedia article states RCM was spun out of Rockefeller
& Co. in 2018 with Greg Fleming (ex-Merrill Lynch President) as CEO,
financed by Viking Global Investors. SEC EDGAR `addresses.business` for
CIK 1739439 confirms a Rockefeller-branded entity. ProPublica returns
"Rockefeller Foundation" at EIN 13-1659629 as a $6.2B foundation, a
plausible philanthropic counterpart.

**Could be wrong because:** RCM is a *multi-family* office that manages
money for many families, not exclusively for the Rockefeller family. The
"family office" framing applies to its origin and ongoing service to
the Rockefeller heirs, but the AUM number includes external clients.

**Seed citations:**
- Wikipedia — Rockefeller Capital Management
  (https://en.wikipedia.org/wiki/Rockefeller_Capital_Management)
- SEC EDGAR (Rockefeller Capital Management LP)
  (https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001739439)

---

## Identity layer

### Legal name

- **Observed:** SEC returns `name = "Rockefeller Capital Management L.P."`
  (note the trailing periods).
- **Verified by:** Primary source. Seed had `"Rockefeller Capital
  Management LP"` (no periods). Fuzzy match scored 97.1 — well above
  threshold 70.
- **Could be wrong because:** Punctuation differences could be a sign of a
  related but distinct entity. In this case the CIK pins down the exact
  registrant.
- **Decision:** SEC value wins. Confidence 1.0.

### HQ address

- **Observed:** SEC EDGAR business address (city: New York, NY).
- **Verified by:** Primary source.
- **Decision:** Confidence 1.0.

### Type

- **Observed:** Seed file classifies as `MFO`.
- **Verified by:** RCM publicly markets itself as serving multiple families
  + institutional clients; the entity is a *family-office-style*
  multi-client wealth manager. Distinct from a pure SFO.
- **Decision:** Confidence 0.7 (seed-derived classification).

### Principal family

- **Observed:** Rockefeller family.
- **Verified by:** Wikipedia article confirms RCM was the spinoff from the
  original Rockefeller Family Office. The Rockefeller family retains
  involvement on the board.
- **Could be wrong because:** "Principal family" is misleading for a
  multi-family office where the named family is one of many clients. A
  more precise field would be `founding_family` or `namesake_family`.
  Keeping the seed classification but acknowledging the limitation.
- **Decision:** Confidence 0.7.

---

## Per-domain enrichment

### Domain 1: Equities

#### Files Form 13F-HR

- **Observed:** RCM files 13F-HR quarterly.
- **Verified by:** SEC EDGAR submissions JSON.
- **Confidence:** 1.0.

#### Most recent 13F-HR

- **Observed:** Accession `0001739439-26-000005`, filed 2026-05-14,
  reporting period 2026-03-31.
- **Verified by:** Same.

#### Reported portfolio value

- **Observed:** `tableValueTotal = 56,396,064,511` (≈$56.4B).
- **Assumed:** Actual-dollar convention.
- **Verified by:** Apple position: 5,598,564 shares × ~$254/share ≈
  $1.42B which matches reported value $1,420,859,571. Convention
  confirmed.
- **Important note on interpretation:** This $56.4B is **assets under
  13F-reportable management for RCM's combined client book**, not
  Rockefeller-family-owned capital. A reader interpreting this as "the
  Rockefeller family's net worth" would be wrong by an order of magnitude.
  The 13F shows discretionary management positions across all RCM
  clients. The family's actual ownership share is a fraction of this.
- **Confidence:** 1.0 on the reported figure; *the data point requires
  this caveat to avoid being misread*.

#### Position count

- **Observed:** `tableEntryTotal = 11,499`.
- **Verified by:** Same primary source.
- **Note:** This is dramatically higher than typical FO portfolios — RCM
  is operating at institutional-investment-manager scale, not pure FO
  scale. Comparison: Soros has 263 positions, RCM has 11,499. The 50x
  multiple is itself a useful signal that RCM's profile is different.

#### Top 10 holdings (Q1 2026)

| # | Issuer | Value (USD) | Shares |
|---|--------|-------------|--------|
| 1 | STATE STR SPDR S&P 500 ETF (SPY) | $1,706,840,855 | 2,624,536 |
| 2 | APPLE INC (AAPL) | $1,420,859,571 | 5,598,564 |
| 3 | NVIDIA CORPORATION (NVDA) | $1,343,466,395 | 7,703,362 |
| 4 | AMAZON COM INC (AMZN) | $979,610,260 | 4,703,559 |
| 5 | MICROSOFT CORP (MSFT) | $974,194,992 | 2,631,750 |
| 6–10 | (in signals.csv `top_10_13f_holdings`) | | |

- **Observed:** Top 5 are all mega-cap tech + S&P ETF. Concentrated in
  the largest public companies. Combined top 5 = ~$6.4B = 11% of $56B
  total.
- **Inference (not a fact):** Profile consistent with a wealth manager
  running diversified-index-plus strategies — not a directional family
  office hedge fund.
- **Confidence on each position value:** 1.0.

#### Schedule 13G filings

- **Observed:** SEC EDGAR returns 13G filings for RCM.
- **Verified by:** EDGAR shows recent SC 13G filings (specific
  accession dates in signals.csv).
- **Confidence:** 1.0 on the boolean fact.

### Domain 2: Private Markets

- **Observed:** No Form D filings under CIK 1739439 in the recent window.
- **Decision:** Honest absence. RCM does not appear to be a primary issuer
  of private placements; it allocates client capital to PE/VC managed by
  others, in which case those issuers file the Form Ds.

### Domain 3: Real Assets

- **Status:** Not run for this record (same as Soros — out of Tier-2 scope).
- **Documented gap.**

### Domain 4: Soft Power

#### Linked foundation

- **Observed:** Rockefeller Foundation (EIN 13-1659629).
- **Assumed:** The historical Rockefeller Foundation is appropriately
  linked to RCM via the Rockefeller family.
- **Verified by:** ProPublica returns the entity. Family ties documented
  in Wikipedia.
- **Could be wrong because:** Rockefeller Foundation is a fully
  independent 501(c)(3) public charity, not under RCM's control. Linking
  it to RCM is by *origin* (the Rockefellers founded both), not by
  *current governance*. The Rockefeller family's other vehicles
  (Rockefeller Brothers Fund EIN 13-6404919, David Rockefeller Fund
  EIN 13-6213106, etc.) are also legitimately Rockefeller-linked. The
  choice of Rockefeller Foundation as *the* linked foundation is the
  most public one but not the most operationally-linked.
- **Decision:** Confidence 0.85 (linkage is by origin, not control).
  Note this in the methodology — for FOs with multiple related
  foundations, the framework currently picks one; a future iteration
  should expose all.

#### Foundation financials (2023)

| Field | Value (USD) |
|-------|-------------|
| Total assets | $6,225,179,743 |
| Total liabilities | $839,507,528 |
| Total revenue | $238,147,048 |
| Total functional expenses | $460,190,655 |
| Grants & contributions paid | $273,583,314 |
| Dividends & interest income | $16,251,844 |
| Net investment income | $177,015,304 |

- **Observed:** Foundation paid out $274M in grants in 2023. Significantly
  lower deployment rate than Soros's foundation (~33% of total revenue
  vs ~99%). Also has a notable liability balance ($839M) — likely
  related to investment leverage or commitments.
- **Note:** Total expenses ($460M) > total revenue ($238M) → the
  foundation is drawing down assets to fund operations. Combined with
  the lower grant-to-revenue ratio, this suggests a *capital-preservation*
  philanthropic model (perpetuity) rather than a *spend-down* model.
- **Confidence:** 1.0 on each numerical field; the inference about the
  philanthropic model is inference, not fact.

#### Named grants — DEFERRED

- Same status as Soros: Gemini-Pro PDF extraction deferred.

### Domain 5: Shadow Bank

- **Status:** Not run. UCC-1 search not in scope.

---

## Final confidence — field-by-field rule trace

| Output field | Picked value | Source | Confidence | Why |
|---|---|---|---|---|
| `canonical_name` | Rockefeller Capital Management L.P. | SEC EDGAR | 1.0 | Primary source wins |
| `type` | MFO | seeds.yaml | 0.7 | No primary source for type |
| `principal_family` | Rockefeller | seeds.yaml | 0.7 | Seed; needs Form ADV Schedule A for promotion |
| `hq_address` | (NYC) | SEC EDGAR | 1.0 | Primary source |
| `sec_cik` | 0001739439 | manual primary-source curation | 1.0 | Hand-verified |
| `files_form_13f` | true | SEC EDGAR | 1.0 | Primary source |
| `latest_13f_filing_date` | 2026-05-14 | SEC EDGAR | 1.0 | Primary source |
| `linked_foundation` | Rockefeller Foundation | ProPublica | 0.85 | Origin-linked, not control-linked |
| `foundation_990pf_latest_year` | 2023 | ProPublica | 1.0 | Primary source |
| Tier-2: `total_13f_portfolio_value_usd` | 56,396,064,511 | SEC 13F | 1.0 | From primary doc — *combined client AUM, not family ownership* |
| Tier-2: `13f_position_count` | 11,499 | SEC 13F | 1.0 | 50x Soros — institutional-scale, not pure-FO scale |
| Tier-2: `grants_and_contributions_paid_usd_2023` | 273,583,314 | ProPublica 990-PF | 1.0 | Structured field |

---

## What would change my conclusion

- If RCM's *family-owned* AUM (vs. client-managed AUM) were disclosed
  separately, the $56.4B figure would be replaced by a much smaller
  number more representative of the Rockefeller family's actual wealth.
  Currently no such disclosure is in the public record.
- If a primary-source document (RCM website, court filing) named a
  *different* primary linked foundation, the `linked_foundation` value
  would update.
- If Greg Fleming were replaced as CEO, the operational profile of RCM
  could shift meaningfully — this signal would surface in news but not in
  our Tier-1 sources.
