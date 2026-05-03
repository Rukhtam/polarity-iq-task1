# Polarity IQ — Task 1 Implementation Plan

## Context

The Polarity IQ Differentiator Assessment (Task 1) requires a validated dataset of 50 real family offices plus a working RAG pipeline that exposes the dataset to natural-language queries. The assessment is graded on the *visibility of human reasoning* — not on the polish of the deliverable. Anything that reads as fully-AI-generated output without uncertainty markers, validation chains, or revision history will not be evaluated.

The user has produced a strong "5-domain data exhaust" research framework (Public Markets, Private Markets, Real Assets, Soft Power, Shadow Bank — see `Documents/Polarity/The Plan.pdf`) but the framework is research-grade, not 48-hour-build-grade. This plan converts that framework into a tiered, executable system: **all 50 records get a Tier-1 enrichment across 3 always-on domains; 3 deep-dive records get the full 5-domain treatment** to satisfy the "full validation chain for 3 records" deliverable.

The plan deliberately overweights the validation/scoring layer (Stages 2 and 3) because that is where the assessment's "thinking is visible" criterion is satisfied.

---

## Architecture Overview

```
                ┌──────────────────────────────────────────────┐
                │  Stage 0: Discovery (one-shot script + LLM)  │
                │  Goal: 100-150 candidate FOs                  │
                └──────────────────────────────────────────────┘
                                    │
                                    ▼
                ┌──────────────────────────────────────────────┐
                │  Stage 1: Domain Enrichment (5 modules)      │
                │  Equities | Private | Real | Soft | Shadow   │
                │  All 50: Equities + Private + Soft           │
                │  Top 3 only: + Real + Shadow                  │
                └──────────────────────────────────────────────┘
                                    │
                                    ▼
                ┌──────────────────────────────────────────────┐
                │  Stage 2: Validator                          │
                │  Entity resolution → dedup → freshness        │
                └──────────────────────────────────────────────┘
                                    │
                                    ▼
                ┌──────────────────────────────────────────────┐
                │  Stage 3: Orchestrator/Scorer                │
                │  Per-field confidence + conflict flagging     │
                └──────────────────────────────────────────────┘
                                    │
                                    ▼
                ┌──────────────────────────────────────────────┐
                │  Stage 4: Human Review (user)                │
                │  Stage 5: Excel Output (.xlsx)               │
                └──────────────────────────────────────────────┘
                                    │
                                    ▼
                ┌──────────────────────────────────────────────┐
                │  Stage 6: RAG Pipeline                       │
                │  Hybrid chunking → ChromaDB → Streamlit demo │
                └──────────────────────────────────────────────┘
```

**Pilot-first execution rule:** every stage is regression-tested on a single FO (recommend **Cascade Investment / Bill Gates** — has every signal type) before scaling to 50.

---

## Repository Structure

```
polarity-iq-task1/
├── README.md                          # Methodology summary (deliverable)
├── requirements.txt
├── .env.example                       # GEMINI_API_KEY, OPENAI_API_KEY
├── data/
│   ├── raw/                           # Raw scraped data per source
│   ├── interim/                       # Per-FO enriched JSON files
│   ├── polarity_iq.db                 # SQLite intermediate store
│   ├── family_offices.xlsx            # Final Excel deliverable
│   └── validation_chains/             # 3 deep-dive markdown files
├── src/
│   ├── stage0_discovery/
│   │   ├── sec_adv_scraper.py         # Form ADV filings via SEC EDGAR
│   │   ├── form_13f_scraper.py        # 13F filers, concentrated holdings filter
│   │   ├── public_directories.py      # FamilyCapital, Highworth scrape
│   │   └── triage_with_gemini.py      # Gemini Pro classifier
│   ├── stage1_domains/
│   │   ├── equities_agent.py          # SEC EDGAR API: 13F, 13D/G, Form 4
│   │   ├── private_markets_agent.py   # Form D + Gemini news parsing
│   │   ├── real_assets_agent.py       # OpenCorporates (top-3 only)
│   │   ├── soft_power_agent.py        # ProPublica 990-PF API + LinkedIn manual
│   │   └── shadow_bank_agent.py       # State UCC search (top-3 only)
│   ├── stage2_validator/
│   │   ├── entity_resolution.py       # Fuzzy match + address + principal
│   │   ├── dedup.py
│   │   └── freshness_checker.py       # Email MX, URL HEAD, filing-date age
│   ├── stage3_orchestrator/
│   │   ├── scoring_rubric.py          # Per-field confidence rules
│   │   ├── conflict_detector.py
│   │   └── excel_writer.py
│   ├── stage6_rag/
│   │   ├── chunking.py                # Hybrid: parent FO + child signal chunks
│   │   ├── embed_and_index.py         # OpenAI text-embedding-3-small → Chroma
│   │   ├── retriever.py
│   │   └── app.py                     # Streamlit demo
│   └── common/
│       ├── db.py                      # SQLite schema + helpers
│       ├── llm_clients.py             # Gemini + OpenAI wrappers
│       └── provenance.py              # (value, source, date, confidence) helper
├── notebooks/
│   ├── 01_pilot_cascade.ipynb         # Pilot run end-to-end
│   └── 02_validation_chains.ipynb     # 3 deep-dive walkthroughs
├── docs/
│   ├── methodology.md                 # How found / enriched / validated / improve
│   ├── rag_notes.md                   # Stack, chunking, embeddings, retrieval
│   ├── time_effort.md                 # Hours, allocation, AI-vs-human split
│   └── reasoning_log.md               # Visible thinking / uncertainty / revisions
└── tests/
    └── test_pilot_cascade.py          # Regression test for the canary FO
```

---

## Stage Specifications

### Stage 0 — Discovery (one-shot script + Gemini triage)

**Inputs:** none. **Outputs:** `data/raw/candidates.csv` with 100-150 entries.

1. `sec_adv_scraper.py` — pull Form ADV filings; filter for the family-office exemption keywords (Rule 202(a)(11)(G)-1). Each match = candidate.
2. `form_13f_scraper.py` — pull 13F filers; flag those with top-10 holdings = >70% of portfolio AND AUM in $100M-$50B range (FO signature).
3. `public_directories.py` — scrape FamilyCapital and Highworth Research listing pages.
4. News-seeded — Gemini-grounded query: *"List family offices publicly named in 2024–2026 funding/investment announcements."*
5. `triage_with_gemini.py` — feed dedup'd candidate list to Gemini Pro: classify each as `definitely-FO / likely-FO / not-FO / unknown`. User spot-checks `definitely` tier and approves the 50.

**Why no LLM agent here:** one-shot operation, deterministic scrapers + a single Gemini classifier call. Agentic loop adds no value.

### Stage 1 — Domain Enrichment Modules

| Module | Tier-1 (all 50) | Tier-2 (top 3) | Free Sources |
|---|---|---|---|
| Equities | ✓ | ✓ | SEC EDGAR API (13F, 13D/G, Form 4) |
| Private Markets | ✓ | ✓ | SEC Form D + Gemini-grounded news |
| Soft Power | ✓ | ✓ | ProPublica Nonprofit Explorer (990-PF) + manual LinkedIn |
| Real Assets | — | ✓ | OpenCorporates API + manual GIS |
| Shadow Bank | — | ✓ | State UCC-1 search portals |

Each module:
- Reads candidate FO from SQLite
- Returns a list of `Signal` records: `(fo_id, domain, signal_type, value, source_url, extraction_date)`
- Writes signals back to SQLite

LinkedIn step is **manual** — the user pastes 50 LinkedIn URLs into a CSV; a small parser reads recent posts/hires from copy-pasted snippets.

### Stage 2 — Validator

**Entity Resolution algorithm:**
1. Group candidates by HQ address (strongest signal — FOs rarely move).
2. Within each address group, fuzzy-match names (Levenshtein + token-set ratio > 0.85).
3. Cross-check principals (control persons from Form ADV Schedule A) against LinkedIn names.
4. Where SEC CRD, EIN, or OpenCorporates ID exists → use as hard key (overrides fuzzy match).
5. Output: each FO gets a canonical `fo_id` + `aliases[]` array.

**Conflict Resolution rule (per user's SEC-as-truth proposal, refined):**
- **Identity & legal facts** (legal name, address, principals, AUM): SEC wins.
- **Operational signals** (recent hires, deals, current contact info): newest source wins.
- **Shell/property facts**: OpenCorporates + county records win.

**Freshness checks:**
- Email: MX lookup + SMTP RCPT TO probe (no actual send).
- URL: HEAD request, expect 200.
- News mention: flag if no public mention in 18+ months.
- Filing: flag if Form ADV last filed > 14 months ago (annual update overdue).
- Each field gets a `last_verified` timestamp; > 6 months → re-check.

### Stage 3 — Orchestrator/Scorer

Pure rules-based Python (no LLM — must be deterministic).

For each `(fo_id, field)`:
```
sources = list of source URLs supporting the value
authority_weight = sum of per-source weights (SEC=1.0, OpenCorporates=0.8,
                   ProPublica=0.8, news=0.5, LinkedIn=0.6)
freshness_factor = exp(-age_days / 180)
conflict_penalty = 0.5 if conflicting values across sources else 1.0
confidence = min(1.0, authority_weight * freshness_factor * conflict_penalty)
```

Confidence buckets: `<0.4 = low (red)`, `0.4-0.7 = medium (yellow)`, `>0.7 = high (green)`. Excel cells colour-coded; the user reviews red/yellow in Stage 4.

### Stage 5 — Excel Schema

One row per FO. Every cell that is a fact (not metadata) carries a comment with: source URL, extraction date, confidence. Sheet 2: full signals log (one row per signal). Sheet 3: validation chain index for the 3 deep-dive records.

### Stage 6 — RAG Pipeline

**Stack:** LangChain + ChromaDB (local persisted) + OpenAI `text-embedding-3-small` + GPT-4o-mini for synthesis + Streamlit deployed to Streamlit Cloud.

**Hybrid chunking:**
- **Parent doc per FO** (~500-800 tokens): structured profile of the FO including key facts, principals, summary.
- **Child docs per signal** (~100-200 tokens each): one chunk per investment, hire, filing, grant — each child carries the parent FO name in the chunk text so retrieval surfaces the link.

Both indexed in the same Chroma collection with `metadata.type = "fo_profile" | "signal"` so the retriever can do typed queries.

**Retrieval:** top-k=8 with type-balanced sampling (4 profile chunks + 4 signal chunks), then re-rank by metadata recency for time-sensitive queries.

**Demo queries to showcase:**
1. Entity question: *"Tell me about Cascade Investment."*
2. Pattern question: *"Which family offices invested in AI infrastructure in 2025–2026?"*
3. Cross-domain: *"Which FOs have both 13F holdings in tech AND 990-PF grants to AI safety research?"*

---

## Pilot-First Execution

Before scaling to 50, run the entire pipeline on **Cascade Investment** end-to-end:
- Validates every domain module returns plausible data
- Validates entity resolution catches "Cascade Investment LLC" / "Cascade LLC" / "Bill & Melinda Gates Foundation Trust"
- Validates the scorer assigns sensible confidences
- Validates RAG returns the right chunks for both query types

Regression test: `tests/test_pilot_cascade.py` asserts known facts (Bill Gates as principal, Kirkland WA HQ, > $150B AUM) come back from the final pipeline. Re-run after any change.

---

## 48-Hour Timeline (rough)

| Phase | Hours | Deliverable |
|---|---|---|
| Repo scaffold + SQLite schema + LLM clients | 2 | Skeleton |
| Stage 0 + pilot Cascade through it | 4 | 100+ candidates |
| Stage 1 modules (Equities, Private, Soft) | 8 | Tier-1 signals for all 50 |
| Stage 1 deep modules (Real, Shadow) for 3 | 3 | Tier-2 signals |
| Stage 2 + 3 (validator + scorer) | 5 | Excel with confidence |
| Manual review (Stage 4) + 3 validation chains writeup | 4 | 3 markdown files |
| Stage 6 RAG pipeline + Streamlit deploy | 8 | Live demo URL |
| Methodology writeup, reasoning log, time/effort report | 4 | All docs |
| Buffer | 10 | — |

---

## Reasoning Log Discipline (assessment-critical)

`docs/reasoning_log.md` is updated continuously, **not** at the end. Every non-trivial decision gets:
- **Observed:** what triggered the decision
- **Assumed:** what we took on faith
- **Verified:** what we checked
- **Could be wrong because:** falsification condition
- **Decision + revision history**

Examples to log up front:
- Why we chose tiered scope (50 surface + 3 deep) over uniform depth
- Why SEC is authoritative for identity but not for freshness
- Why hybrid chunking despite the 2x storage cost
- Why we excluded paid sources (FINTRX, Sales Navigator, Crunchbase API) and what that costs us
- Every FO that fails entity resolution and why

This file is the primary signal that our submission is not "polished AI output" — it is the visible thinking layer the rubric asks for.

---

## Critical Files / Reused Components

- `src/common/provenance.py` — single helper that wraps every stored value as `{value, source_url, extraction_date, confidence, verified_by}`. Every Stage 1 module uses it; Stage 3 reads it for scoring.
- `src/common/db.py` — SQLite schema with tables: `family_offices`, `signals`, `sources`, `aliases`. Every stage reads/writes here.
- `src/common/llm_clients.py` — wraps Gemini Pro + OpenAI with retry/cost-logging. All LLM calls go through here.

---

## Verification

End-to-end smoke test:

```bash
# 1. Pilot regression
pytest tests/test_pilot_cascade.py

# 2. Full pipeline on the 50
python -m src.stage0_discovery.run_all
python -m src.stage1_domains.run_tier1   # all 50
python -m src.stage1_domains.run_tier2   # top 3 only
python -m src.stage2_validator.run
python -m src.stage3_orchestrator.run    # writes data/family_offices.xlsx

# 3. RAG build + demo
python -m src.stage6_rag.embed_and_index
streamlit run src/stage6_rag/app.py

# 4. Test the 3 demo queries against the live UI
```

Manual checks before submission:
- Open `family_offices.xlsx`, confirm every row has a confidence colour and source comments on key cells
- Read all 3 validation chain markdown files end-to-end
- Run all 3 demo queries on the deployed Streamlit URL, screen-record results
- Diff `reasoning_log.md` against the final submission — every major decision should have an entry

---

## Out of Scope (deliberate, documented in methodology)

- Real-time monitoring / live RSS pipelines (framework supports it, but 48hrs is one-shot)
- LinkedIn automation (manual-only — bot detection makes scraping unreliable + ToS risk)
- Paid data sources (FINTRX, PitchBook, Sales Navigator, Crunchbase API)
- Tier-2 enrichment beyond the 3 deep-dive records
- Multi-user RAG (single-user Streamlit demo only)
