# Polarity IQ Differentiator — Tasks 1 & 2 Implementation Plan (refined)

## Context

The Polarity IQ Differentiator Assessment requires, within a single 48-hour window:
- **Task 1**: 50 validated real Family Office records + working RAG pipeline + GitHub repo + live demo + methodology + 3 deep-dive validation chains
- **Task 2**: written analysis of how to lift a Family Office Intelligence SaaS from 3% free→paid conversion

The original `PLAN.md` had three rubric-critical failures: (a) Task 2 was missing entirely; (b) discovery started in the wrong haystack — SEC Form ADV — because Rule §202(a)(11)(G)-1 *exempts* most qualifying SFOs from IA registration; (c) the "visible thinking" surface was treated as a single file rather than a process woven through every artifact. A brutal review (see `Brutal Review & Refined Plan` Notion page) called these out and proposed a refined architecture. This plan adopts that refinement in full, with one user-confirmed exception: all 5 framework domains are retained for the 3 deep-dive records, with a hard 2-hour-per-record cap and honest documentation of any cuts.

The plan deliberately overweights the **visible-thinking discipline** — commit cadence, decision templates, "what I abandoned and why" sections, queries-that-failed sections — because that is what the rubric actually measures, not deliverable polish.

---

## Verdict the plan is engineered around

- **~28 working hours across 48 elapsed**, after sleep across two nights, including Task 2.
- **Top-down curation** beats bottom-up scraping. SEC EDGAR is a *cross-check* layer, not the discovery layer.
- **Soros Fund Management** is the pilot canary — registered IA with public Form ADV, 13F under SFM CIK, Open Society Foundations 990-PF publicly linked, named principals, news-rich. (Cascade Investment was rejected because it is structured to defeat the very signals our framework targets.)
- **Field-aware rule tables** for confidence, not a single decay formula.
- **No LangChain.** Direct OpenAI SDK + ChromaDB. The act of justifying that choice is itself visible thinking.
- **Visible thinking is a process, not a file.** Reasoning log + 3 chain markdowns + "abandoned and why" methodology sections + RAG queries that fail.

---

## Architecture (collapsed to 3 scripts)

```
                ┌────────────────────────────────────────────┐
                │  curate.py                                  │
                │   top-down list → ~60 candidates → 50 final │
                │   sources: FamilyCapital, Highworth,        │
                │     Campden, news-named FOs, EisnerAmper,   │
                │     Forbes families                          │
                │   SEC ADV §202(a)(11)(G)-1 = cross-check    │
                └────────────────────────────────────────────┘
                                    │
                                    ▼
                ┌────────────────────────────────────────────┐
                │  enrich.py                                  │
                │   per-FO module dispatch                    │
                │   Tier-1 (all 50): identity, principals,    │
                │     contact (LinkedIn + email),             │
                │     SEC if filed, 990-PF if linked,         │
                │     2–3 recent signals                       │
                │   Tier-2 (3 only): all 5 domains            │
                │     (equities, private, real assets,         │
                │      soft power, shadow bank)               │
                │     hard cap 2h/record                      │
                └────────────────────────────────────────────┘
                                    │
                                    ▼
                ┌────────────────────────────────────────────┐
                │  score_and_export.py                        │
                │   field-aware rule tables → confidence      │
                │   dedup by (legal_name | HQ | CRD/EIN)      │
                │   write family_offices.xlsx + signals.csv   │
                └────────────────────────────────────────────┘
                                    │
                                    ▼
                ┌────────────────────────────────────────────┐
                │  rag/                                       │
                │   build_index.py (parent + child chunks)    │
                │   eval.py (12 query → expected eval set)    │
                │   app.py (Streamlit; recording is canonical)│
                └────────────────────────────────────────────┘
```

Pilot-first execution rule: every script regression-tested on **Soros Fund Management** before scaling to 50.

---

## Repository (flatter)

```
polarity-iq-task1/
├── README.md                       # Methodology summary + how-to-run
├── requirements.txt
├── .env.example                    # GEMINI_API_KEY, OPENAI_API_KEY
├── data/
│   ├── candidates.csv              # top-down curated list, every row has source
│   ├── polarity_iq.db              # SQLite (4 tables: family_offices, signals, sources, aliases)
│   ├── family_offices.xlsx         # final dataset deliverable
│   ├── signals.csv                 # long table: one row per signal w/ provenance
│   └── chains/                     # 3 deep-dive validation-chain markdown files
├── src/
│   ├── curate.py                   # discovery (top-down), writes candidates.csv
│   ├── enrich.py                   # per-domain enrichment functions in one file
│   ├── score_and_export.py         # field-aware rules, Excel + CSV output
│   ├── provenance.py               # Signal dataclass: value, source_url, extracted_at, confidence, method
│   ├── db.py                       # SQLite schema + helpers
│   ├── llm.py                      # Gemini + OpenAI thin wrappers, cost-logging
│   └── rag/
│       ├── build_index.py
│       ├── eval.py                 # 12 queries → expected source-FO IDs
│       └── app.py                  # Streamlit demo
├── docs/
│   ├── methodology.md              # found / enriched / validated / what I abandoned and why
│   ├── rag.md                      # stack + chunking + retrieval + eval results + queries that failed
│   ├── time_effort.md              # per-phase split: AI vs human work
│   ├── reasoning_log.md            # append-only running log
│   └── task2_saas_conversion.md    # Task 2 deliverable
├── scripts/
│   └── pilot.py                    # end-to-end pilot on Soros
└── tests/
    └── test_pilot_soros.py         # canary regression test (cited facts only)
```

---

## Time budget (realistic — 28 working hours across 48 elapsed)

| Block | Hours | Output |
|---|---|---|
| Repo scaffold + db schema + provenance + Soros pilot end-to-end | 4 | Skeleton + working canary |
| `curate.py` top-down curation + verify each → 50 records w/ identity layer | 4 | `candidates.csv` |
| `enrich.py` Tier-1 across 50 (contact, recent investments, principals, 990-PF link if any) | 6 | `signals.csv` populated |
| Tier-2 deep on 3 chosen records (all 5 domains, 2h cap each) + 3 chain markdowns | 6 | `data/chains/*.md` |
| `score_and_export.py` + Excel review pass | 2 | `family_offices.xlsx` |
| RAG: build_index + eval + minimal Streamlit + screen recording | 4 | live or recorded demo |
| Methodology, RAG doc, time-effort, reasoning log polish | 2 | `docs/*.md` |
| **Task 2 written analysis** | 2 | `docs/task2_saas_conversion.md` |
| **Total work** | **30** | (2h spillover budget into elapsed time) |

Hard cuts if behind at hour 30:
- Tier-2 from 3 → 2 records (drop the weakest deep-dive)
- Streamlit deploy → recording-only
- Task 2 → cap at 1500 words (target was 1500–2500)

---

## Discovery — top-down list (replaces SEC-first scraping)

`data/candidates.csv` is curated from public lists, with every row carrying source + extraction date. Sources, in priority order:

1. **FamilyCapital "Top 100 SFOs"** — multiple annual lists triangulated for stability
2. **Highworth Research** — listing pages
3. **Campden Wealth** — published case studies and named participants
4. **EisnerAmper Family Office Survey** — named participants in the published reports
5. **Forbes "America's richest families"** — filtered for those with confirmed FO entity
6. **News-named FOs in 2024–2026 funding announcements** — Gemini-grounded query, but every result is *primary-source verified before inclusion*
7. **SEC EDGAR Form ADV §202(a)(11)(G)-1 hits** — now a *cross-check* layer, used to confirm/deny identity facts on records discovered top-down

Curation gate: 60–80 candidates → drop to 50 by selecting for **signal availability** (FOs with the deepest public exhaust). Every cut documented in `reasoning_log.md`.

**Originality note:** the rubric requires "entirely original records sourced through your own work." The defence is the **enrichment layer**, not the seed list — every record gets independent primary-source signals on top of the public-list provenance. Methodology must state this explicitly.

---

## Field-aware rule tables (the defensibility lives here)

| Field | Authoritative source | Acceptable fallback | Freshness window | Rule |
|---|---|---|---|---|
| `legal_name` | SEC ADV / state corp registry | OpenCorporates | n/a | exact match → high; fuzzy → medium + flag |
| `hq_address` | SEC ADV / state corp registry | OpenCorporates / news | 36 mo | recent authoritative → high |
| `principals` | Form ADV Schedule A / 13G | LinkedIn + news cross-check | 24 mo | 2 sources agree → high; 1 → medium |
| `linkedin_url` | LinkedIn direct | — | 12 mo | URL resolves + name match → high |
| `email` | website / press release | inferred pattern + MX | 12 mo | published → high; inferred → low |
| `recent_investment` | SEC Form D / press release | news only | 24 mo | filing → high; news only → medium |
| `990_pf_grants` | ProPublica + IRS | — | most recent filing | direct linkage verified → high |
| `shell_entities` | OpenCorporates + state corp | county GIS | n/a | address + principal cross-match → high |
| `ucc_liens` | state UCC search | — | n/a | direct hit on FO or shell → medium |

Rule table inlined as a CSV at the top of `score_and_export.py`. Each cell carries `(value, source_url, extracted_at, confidence, method)` via the `provenance.py` dataclass.

**Dropped from previous plan:**
- SMTP RCPT TO probe — mostly noise on Gmail/M365/ProofPoint, disclaimed in methodology
- "No public mention in 18 months → flag stale" — inverts reality for legitimate quiet SFOs
- `last_verified` 6-month re-check — cargo-culted from continuous monitoring into a one-shot deliverable
- Single confidence formula with exponential decay — replaced by field-aware tables above

---

## RAG — minimum viable

- **No LangChain.** Direct OpenAI SDK + `chromadb`. Simpler code, no version churn, justifying this is itself visible thinking.
- **Embeddings:** `text-embedding-3-small` (1536-d, cheap, plenty for 50 entities).
- **Chunking:** hybrid.
  - Parent doc per FO (~600 tokens, structured profile w/ key facts and principals)
  - Child docs per signal (~150 tokens; parent FO name embedded in chunk text)
  - One Chroma collection; `metadata.type = "fo_profile" | "signal"`
- **Retrieval:** top-k = 8 (4 profile + 4 signal balanced sample), passed to GPT-4o-mini for synthesis. No reranker.
- **Eval set:** `rag/eval.py` runs 12 queries → expected source-FO IDs. Run before declaring done. Honestly report failures in `docs/rag.md`.
- **Hosting:** Streamlit Cloud as a *bonus*. **Screen recording is the canonical demo deliverable.** OpenAI key has a hard spend cap. App enforces a query rate-limit (20/IP/hour) if it goes live.

**Considered and rejected:** "no retrieval at all, dataset fits in 32K context." Rejected because (a) the brief explicitly asks for a "RAG pipeline," and (b) the pattern-query workload (cross-FO signal search) benefits from retrieval even at 50 records. Considering this alternative is documented in `docs/rag.md`.

---

## Visible-thinking discipline (process, not file)

Mandatory across the project:

1. **Commit cadence:** small, narrative commits. Messages of the form `tried X for Y, didn't hold because Z, switched to W`. The git log is itself a thinking artifact.
2. **Reasoning log template** (every non-trivial decision gets an entry):
   ```
   ## <decision>
   - Observed: …
   - Assumed: …
   - Verified by: …
   - Could be wrong because: …
   - Decision (and revision history): …
   ```
3. **Validation-chain markdown template** (3 deep-dive records):
   ```
   # FO Name

   ## Discovery
   Source / extraction date / why this list / who I cross-checked against

   ## Identity layer
   Observed: …
   Assumed: …
   Verified by: …
   Could be wrong because: …

   ## Per-domain enrichment (one section per domain hit)
   (per signal: same Observed / Assumed / Verified / Could-be-wrong template)

   ## Final confidence
   Field-by-field rule trace from the rule table
   ```
4. **`docs/methodology.md`** must include a mandatory **"What I abandoned and why"** section.
5. **`docs/rag.md`** must include a mandatory **"Queries that failed"** section with 2–3 examples and analysis.
6. **`docs/time_effort.md`** must split AI-vs-human per phase, not in aggregate.

---

## Task 2 — SaaS Free → Paid Conversion (was missing — now scoped)

`docs/task2_saas_conversion.md`. 2 hours. 1500–2500 words.

Outline:
- **Reframe the 3% number.** What's the denominator? Cold-marketing free signups convert differently than ICP-matched outbound. Without that decomposition, 3% is unreadable.
- **Hypothesis enumeration**, each with a falsification condition:
  - Weak ICP fit at signup (free funnel is too broad)
  - Weak activation moment (no aha-moment in trial)
  - Weak commercial trigger (paywall in the wrong place / wrong feature)
  - Weak follow-up (no nurture sequence, no sales-assist)
- **Recommendation:** bias toward activation + trigger experiments before pricing changes. Specific testable interventions with expected lift ranges and falsification criteria.
- **Make uncertainty visible** — explicitly mark which hypotheses are speculative vs grounded in industry benchmarks. Same rubric applies to Task 2 as Task 1.

---

## Critical files

- `src/provenance.py` — `Signal` dataclass + `record_signal()` helper. Every enrichment function returns these. Score reads them.
- `src/db.py` — SQLite schema. Single source of truth across all stages. Tables: `family_offices`, `signals`, `sources`, `aliases`.
- `src/score_and_export.py` — field-aware rule tables. The defensibility lives here. Rule table inlined as a CSV at the top of the file.
- `docs/reasoning_log.md` — append-only running log; one entry per non-trivial decision; template enforced.
- `data/chains/*.md` — 3 deep-dive validation chains using the mandatory template above.
- `tests/test_pilot_soros.py` — regression test using *cited* facts only (Soros CRD #, principal name, NYC HQ — all from public Form ADV).

---

## Verification

End-to-end before submission:

```bash
pytest tests/test_pilot_soros.py            # canary regression
python -m src.curate                        # writes data/candidates.csv
python -m src.enrich --tier 1               # all 50
python -m src.enrich --tier 2 --ids ...     # the chosen 3
python -m src.score_and_export              # writes data/family_offices.xlsx
python -m src.rag.build_index
python -m src.rag.eval                      # prints pass/fail per query
streamlit run src/rag/app.py                # local smoke
```

**Manual gates before sending the email:**
- Open `family_offices.xlsx`: every row has a populated confidence per field, primary source URL in `signals.csv`.
- Read all 3 chains end-to-end out loud — if any sentence sounds like clean AI prose without an `Observed/Assumed/Verified/Could-be-wrong` cycle behind it, rewrite.
- Run all 12 RAG eval queries on the live or recorded UI; record outcomes including failures in `docs/rag.md`.
- Skim `reasoning_log.md` — should look like a working notebook, not a polished doc. If it reads too clean, that's a smell. Rewrite.
- Confirm Task 2 doc is complete and addressed in the submission email.
- Confirm screen recording exists and plays end-to-end *before* relying on the live URL.

---

## Out of scope (deliberate, documented in methodology)

- Real-time monitoring / live RSS pipelines (framework supports it; 48hrs is one-shot)
- LinkedIn automation (manual-only — bot detection + ToS risk)
- Paid data sources (FINTRX, PitchBook, Sales Navigator, Crunchbase API)
- Tier-2 enrichment beyond the 3 deep-dive records
- Multi-user RAG (single-user Streamlit demo only)
- LangChain (rejected — adds dependency churn for no gain at this scale)
- SMTP RCPT TO email validation (rejected — too noisy on major mail servers)

---

## Post-approval sync

Once approved, this plan replaces the contents of `PLAN.md` in the repo, then commit + push so the GitHub source-of-truth matches.
