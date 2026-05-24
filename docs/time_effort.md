# Time + Effort Report

The brief asks for total hours, allocation across activities, and an
AI-vs-human split per activity. This is my honest accounting.

The clock-time numbers below are **session-wall-time**, not always
butt-in-chair. A long session may include thinking pauses; a short
one may be intense. I've broken work into discrete blocks and tried
to label each.

## Total time

- **Task 1 work:** ~7-8 hours wall-time across multiple sessions.
- **Task 2 work:** ~1.5 hours.
- **Total:** ~9-10 hours.

That's substantially less than the 28-hour budget in PLAN.md. Two
reasons: (a) AI assistance accelerated the build-heavy phases more
than I'd assumed; (b) the "What I abandoned and why" decisions
removed work from scope rather than completing it.

## Per-block breakdown

| Block | Wall hrs | What got produced | AI assist | Mostly mine |
|---|---|---|---|---|
| Discovery — reading the brief, "How We Work" doc, brutal review | 0.5 | mental model | n/a | reasoning + decisions |
| Planning + back-and-forth on architecture (Notion + brutal-review cycle) | 1.0 | PLAN.md (refined) | drafted by AI, critiqued + edited by me | the trade-off decisions |
| Phase 1 — scaffold + Soros pilot end-to-end | 1.0 | scaffold, db.py, provenance.py, llm.py, fetch_sec_edgar + fetch_propublica_990pf, 7-test pilot regression | code drafted by AI from my specs | API discovery + cross-source verification of Soros facts |
| Phase 2 — 50-record curation + verification | 2.0 | seeds.yaml (50 entries), curate.py (with fuzzy matching + EIN verification), candidates.csv, signals.csv, family_offices.xlsx, score_and_export.py with FIELD_RULES | code by AI, ProPublica EIN lookups partly by AI partly by me | seed list curation, EIN-mismatch corrections (Dalio, Heinz, Tisch), trade-off calls on which FOs to include |
| Phase 3a — Tier-2 enrichment for 3 deep dives | 1.0 | fetch_13f_holdings (XML parsing), fetch_990pf_financials, the --tier2 CLI | code by AI | XML-namespace-stripping debugging, share-count anomaly flagging |
| Phase 3b — 3 validation chain markdowns | 1.0 | data/chains/{soros, rockefeller, walton}.md | AI helped with structure + paragraph drafts | the Observed/Assumed/Verified/Could-be-wrong calls — substance is mine |
| Phase 3c — RAG pipeline | 1.0 | build_index, retriever, eval, Streamlit app | code by AI | architectural choices (no LangChain, hybrid chunking, type-balanced retrieval) |
| Phase 3d — documentation | 0.5 | methodology, rag, this file, README updates | AI drafted, I edited | the "what I abandoned and why" lists, the honest gap callouts |
| reasoning_log.md upkeep across all phases | 0.5 (running) | 11 entries with full template | AI drafted entries from my decisions; I checked they accurately reflected the decision | the decisions themselves |
| Task 2 — SaaS conversion analysis | 1.5 | docs/task2_saas_conversion.md | AI drafted; I made the hypothesis-prioritisation calls | the analysis structure + uncertainty framing |

## AI-vs-human split, in plain English

**AI was the primary driver of:**
- Code drafting (every script in the repo)
- API endpoint research (finding the right SEC + ProPublica URLs)
- Debugging (XML namespace issues, fuzzy-match thresholds, etc.)
- Documentation paragraph drafts
- Schema design suggestions

**I was the primary driver of:**
- Every architectural decision recorded in `docs/reasoning_log.md` —
  inverting discovery to top-down, swapping the canary from Cascade to
  Soros, dropping LangChain, replacing the confidence formula with
  field-aware rules, dropping SMTP email validation, etc.
- Curating the 50 seeds (which FOs to include + which sources to cite)
- Catching the EIN-hint mismatches when they surfaced
- Flagging the Global Payments share-count anomaly during 13F parsing
- The "What I abandoned and why" calls — scope-cut decisions
- Reading the brutal review carefully and integrating it

**The model in plain terms:** AI built. I thought.

That's the framing the "How We Work" doc asked for. The visible
thinking — in reasoning_log, in the validation chains, in the
methodology — is mine. The buildable artifacts that flow from those
decisions are AI-assisted.

## What this report intentionally does not pretend

I have not tried to attribute fractional credit per line of code. The
honest summary is that on a build-heavy task, AI does most of the
typing and I do most of the deciding. On the visible-thinking
deliverables (reasoning_log, validation chains, methodology), the
ratio reverses — I do most of the deciding *and* most of the
substantive writing; AI drafts paragraphs that I then edit for
substance.

## What surprised me

- **The brutal review was right about scope.** I had drafted a
  7-stage architecture that would not have fit. Collapsing to 3
  scripts bought time for the visible-thinking work, which was
  rubric-critical.
- **EIN verification caught real mistakes.** Three EINs in my
  initial seed file were wrong (Dalio, Heinz, Tisch). curate.py
  caught all three because of the cross-API fuzzy-match step. If I
  had skipped that step the dataset would have shipped with three
  silently-wrong foundation linkages.
- **The "honest thin" Walton record is more useful than a falsely-
  rich one would have been.** Demonstrating that the framework
  degrades gracefully when SEC is silent is itself a deliverable.
- **The ProPublica 990-PF lag window** was discovered by the pilot
  regression test, not by my planning. The test was supposed to
  assert "recent enough", and it failed against real data — which
  surfaced the IRS-release lag. The fix (relax to 3 years) is honest;
  the discovery is exactly the kind of thing the brutal review said
  visible thinking should look like.
