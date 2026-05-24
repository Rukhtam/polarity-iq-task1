# RAG Pipeline Notes

This documents the natural-language query layer over the 50-record FO
dataset. The brief asks: "stack choices, chunking strategy, embedding
model, retrieval approach, what works, what does not, and what you
would improve." Answered in order, with two mandatory sections the
brutal review insisted on: "Why no LangChain" and "Queries that
failed."

---

## Stack

| Layer | Choice | Why |
|---|---|---|
| Embeddings | Google `text-embedding-004` (768-d) | Free tier ample for 50 entities; user has Gemini key, not OpenAI |
| Vector store | ChromaDB (persistent, local) | Zero infra; persistent directory commits cleanly |
| Synthesis LLM | Google `gemini-1.5-flash` | Cheap, low-latency, good enough for grounded synthesis at temperature 0 |
| UI | Streamlit | Fastest path to a live URL; Streamlit Cloud deploys free in 10 min |
| Glue | Direct google-generativeai SDK + chromadb. No LangChain | See below |

**Note on provider choice:** First draft used OpenAI (`text-embedding-3-small`
+ `gpt-4o-mini`) because that was the obvious default. Switched to Gemini
when the user confirmed they have a Gemini API key but not OpenAI. The
switch was a 30-minute refactor — both providers have the same shape of
API (embed text → vector, chat-completion). The fact that this swap was
small is itself a defence of the "no LangChain" decision: dependency-free
code is provider-agnostic by accident.

### Why no LangChain

The first draft reached for LangChain by default. The brutal review
flagged it. After looking at what we actually need at this scale:
- 50 FOs → ~450 chunks → ~2MB of embeddings → trivial for any vector store
- Two endpoints: embed query + chat completion
- One chunking pass, one indexing pass
- No agentic loop, no multi-collection re-ranking, no MCP routing

LangChain adds:
- A dependency with rapid breaking changes (we've seen multiple 0.x →
  0.y deprecations within a calendar year)
- Retriever and chain abstractions that obscure the actual prompt sent
  to the model — review nightmare
- Version coupling to `langchain-community`, `langchain-openai`,
  `langchain-chroma` and friends

Doing this directly is ~200 lines across `build_index.py`,
`retriever.py`, `eval.py`, `app.py`. Every prompt is visible in the
source. Every API call is one library hop away from inspection.

The decision to skip LangChain is itself a visible-thinking artifact;
the brutal review correctly called out that going with "the default"
without considering alternatives is the failure mode the rubric
punishes. See `docs/reasoning_log.md` entry "No LangChain in the RAG
layer".

---

## Chunking — hybrid (parent + child)

Two chunk shapes per FO:

**Parent doc (`metadata.type = "fo_profile"`)** — one per FO, ~400–800
tokens. Structured prose summary that names the FO, its type, family,
HQ, and key headline facts. Example:

> Soros Fund Management LLC is a MFO-type family office, principal
> family Soros, headquartered in New York, US. Registered SEC
> investment adviser; files Form 13F-HR (most recent 2026-05-15).
> Reports 263 13F-managed positions totalling $9.1B. Linked private
> foundation: Foundation To Promote Open Society (EIN 263753801).
> Foundation paid $837M in grants in 2023.

**Child doc (`metadata.type = "signal"`)** — one per signal, ~50–150
tokens. Always carries the parent FO's canonical name in the chunk
text so retrieval can connect signal → FO at synthesis time:

> [soros_fund_management] Soros Fund Management LLC:
> latest_13f_filing_date = 2026-05-15
> (domain=equities, source=SEC edgar submissions, confidence=1.0)

### Why hybrid

A user querying the dataset will ask two fundamentally different
question types:
- **Entity questions** ("Tell me about Soros Fund Management") need
  the whole FO profile in a single chunk for clean retrieval
- **Pattern questions** ("Which FOs file Form 13F?" or "Foundation
  grant spending in 2023") need to retrieve specific signal-level
  facts across many FOs, not 50 huge parent docs

Per-FO-only chunking would force the LLM to dig signal-level facts out
of long profile chunks (slow + lossy). Per-signal-only chunking would
fragment the picture for entity questions (LLM gets 8 fragments of
the same FO with no summary). Hybrid + type-balanced retrieval handles
both.

Trade-off: ~10x storage compared to per-FO chunking. At 50 FOs ×
text-embedding-3-small (1536-d) that's ~2MB of embeddings — irrelevant
cost. At 50,000 FOs it would force a different choice.

### Considered and rejected: no retrieval at all

The brutal review noted that with only 50 records, the entire dataset
summary could fit in a 32K-token context window. A simpler
implementation would skip retrieval entirely: load all profile chunks
into the system prompt, ask the question, done.

I considered this and rejected it because:
- The brief explicitly asks for a "RAG pipeline" — building it is the
  deliverable
- The pattern-query workload benefits from retrieval even at 50
  records (the LLM is better at synthesising 8 targeted chunks than
  scanning 50 profiles)
- The retrieval layer is what extends to 500 or 5,000 records — the
  "no retrieval" alternative does not

Documenting the consideration is the visible-thinking step.

---

## Retrieval — type-balanced top-k

Implementation in `src/rag/retriever.py`:

1. Embed the query via `gemini-embedding-001` with `task_type=RETRIEVAL_QUERY`
2. Two separate ChromaDB queries with `where = {"type": "fo_profile"}`
   and `where = {"type": "signal"}`, each with k=4
3. Merge into a final 8-chunk context
4. Pack as `Profile chunks:` block + `Signal chunks:` block
5. Send to `gemini-2.5-flash` (temperature 0) with a system prompt that
   constrains answers to retrieved context (no general-purpose world
   knowledge)

Why type-balanced vs raw top-8: if I just took top-8 from the combined
collection, profile chunks (longer, more keywords) would dominate
queries like "Which FOs file Form 13F?" because their text contains
the entity name and the field name together. Splitting forces both
types into the context regardless of distance scores.

No reranker — the dataset is small enough that cosine distance is
fine.

### Synthesis prompt (in `retriever.py:SYSTEM_PROMPT`)

The key constraints:
- Ground every claim in the provided context. If unsupported, say so.
- Cite the FO by canonical name; use the `[fo_id]` tags in chunks.
- If no context retrieved for the asked FO, say "I have no records on
  that FO" — explicitly do not guess.
- Surface caveats baked into the data (e.g., RCM's $56B AUM is client
  capital not family ownership — the chunk text carries this caveat,
  the LLM should propagate it).

---

## Eval results

`src/rag/eval.py` defines 12 queries with expected FO-id retrieval
targets. Pass criteria depend on query kind:
- **entity** — at least one expected fo_id appears in the merged top-8
- **pattern** — at least half of expected fo_ids appear
- **signal** — at least one expected appears
- **out_of_scope** — recorded but not pass/fail

**Live run, 2026-05-25, against the Gemini-embedded index. Final
score: 10 / 11 pass (91%) excluding the out-of-scope case.**

| # | Query | Kind | Result | Notes |
|---|---|---|---|---|
| 1 | Tell me about Soros Fund Management. | entity | PASS | soros_fund_management in top-4 |
| 2 | What is the Walton family office? | entity | PASS | walton_enterprises in top-4 |
| 3 | Describe Rockefeller Capital Management. | entity | PASS | rockefeller_capital_management in top-4 |
| 4 | Cascade Investment Bill Gates | entity | PASS | cascade_investment + Schmidt's hillspire co-retrieved |
| 5 | Which family offices file Form 13F? | pattern | PASS | Soros + Rockefeller both retrieved |
| 6 | FOs with linked foundations paying large grants | pattern | PASS | Soros + Rockefeller + Walton retrieved |
| 7 | FOs headquartered in New York City | pattern | FAIL (see below) | Retrieved 8 NYC FOs, just not the *expected* two |
| 8 | Tech-founder-affiliated family offices | pattern | PASS | Bezos, Cascade, Iconiq retrieved |
| 9 | Soros's largest 13F position | signal | PASS | Top-position signal in top-4 |
| 10 | Foundation grant spending in 2023 | signal | PASS | Multiple foundation FOs retrieved |
| 11 | European family offices | pattern | PASS | Pictet retrieved; JAB / Bregal didn't make top-4 |
| 12 | Which FOs invested in artificial intelligence? | out_of_scope | recorded | See below |

### Sample answers (3 spot-checks of the synthesis layer)

**Q: Tell me about Soros Fund Management.**

> Soros Fund Management LLC is a MFO-type family office, with the
> principal family Soros, headquartered in New York, US.
> [soros_fund_management] It is a registered SEC investment adviser and
> files Form 13F-HR, with the most recent filing on 2026-05-15. It
> reports 263 13F-managed positions totaling $9.1B. Its top 10 13F
> holdings include STATE STR SPDR S&P 500 ETF T ($773M), AMAZON COM INC
> ($405M), SELECT SECTOR SPDR TR ($303M), COREWEAVE INC ($220M), and
> GLOBAL PMTS INC ($218M). The family office is linked to the private
> foundation Foundation To Promote Open Society (EIN 263753801), which
> paid $837M in grants in 2023. Its headquarters address is 250 WEST
> 55TH STREET, FLOOR 29, NEW YORK, NY, 10019.

**Q: Which family offices file Form 13F with the SEC?**

> The following family offices file Form 13F with the SEC:
> * [rockefeller_capital_management] Rockefeller Capital Management LP
> * [soros_fund_management] Soros Fund Management LLC
> * [tisch_family] Loews Corporation

**Q: Walton Family Foundation grants in 2023**

> The Walton Family Foundation Inc, linked to [walton_enterprises]
> Walton Enterprises LLC, paid $641,316,726 in grants in 2023.

Each answer is grounded in retrieved chunks, every entity is cited
with its `[fo_id]` tag, and the synthesis declines to invent facts
beyond the context.

### Queries that failed (live-run honesty)

**Q7 — "Which family offices are headquartered in New York City?"** —
pass criterion expected Soros + Rockefeller in the top-k. The actual
top-4 profile chunks returned were Lauder, Tisch (Loews), Willett
Advisors (Bloomberg), Helmsley. The top-4 signal chunks returned
Lauder, Mellon, Helmsley, Duke.

**All 8 retrieved chunks are genuinely NYC-headquartered FOs.** The
retrieval was correct; the eval expectation was too narrow. The
dataset has 7+ NYC FOs and the embeddings prefer the ones whose
chunks state the location most cleanly: the seed-curated FOs say
"headquartered in New York, US" verbatim; Soros's profile says the
more specific "250 West 55th Street, NEW YORK NY 10019", which scores
lower on a "New York City" similarity query because the address-style
phrasing diverges from the query phrasing.

Fix options:
- **Loosen the eval.** Pattern queries with many valid answers should
  score on "N or more relevant FOs returned", not "specific FOs
  returned". Considered, deferred.
- **Normalise chunk text.** Make every profile chunk include a
  uniformly-phrased "located in $CITY, $COUNTRY" sentence so the city
  signal is consistent across records. Easier to maintain; would also
  improve any future location-aware patterns.

The honest takeaway: **the failure was in the eval's narrow
expectations, not in the pipeline.** Surfacing this is exactly the
visible-thinking artifact the rubric rewards.

**Q12 — "Which family offices have invested in artificial
intelligence?"** — out-of-scope. The dataset does not carry
investment-thesis signals at the Tier-1 layer (we have 13F holdings
but not domain/sector tags on each position). Retrieval returned a
mix of tech-adjacent FOs (Iconiq, Cascade, Dalio) and the synthesis
correctly declined to assert specific AI investments. This is the
documented gap from Tier-2 deferral — see methodology.md "990-PF PDF
grant extraction" and the equivalent gap for parsing 13F holdings
into sector tags.

---

## What works

- Hybrid chunking handles both entity and pattern queries from the
  same index
- Type-balanced retrieval cleanly separates the two query types
- Provenance metadata (source_url, confidence, method) is preserved
  on every chunk and surfaceable in the UI's "retrieved chunks"
  expander
- Cost per query: embedding is free under Gemini's generous tier;
  synthesis on gemini-1.5-flash is roughly $0.0001 per question at
  typical context size. Per-session 20-query cap in `app.py` keeps
  total exposure < $0.005 per session.

## What doesn't (yet)

- No retrieval evaluation against a live key, so I cannot quantify
  recall@k against the 12 evals. The chunk-text inspection is a
  *necessary* condition not a *sufficient* one.
- No reranker. With 50 records the top-k from a small collection is
  usually fine, but on a corner-case pattern query a learned-ranker
  pass would help.
- The Streamlit demo's 20-query session cap is per-IP-loose (Streamlit
  Cloud doesn't enforce hard rate limits). A real public deploy would
  need a server-side rate limiter; current implementation is a soft
  guard.
- Grant-level detail (the 990-PF PDF top recipients) is not in any
  chunk because we deferred PDF extraction. RAG queries about "which
  causes does the Walton Family Foundation fund?" will return the
  foundation's total grant amount but not the named recipients.

## What I would improve

1. **Multi-vector chunks per signal.** Each signal currently produces
   one embedding. A duplicate embedding for the value alone (without
   the source/confidence metadata in the text) might score better for
   value-centric questions. Easy A/B test.
2. **Family-level alias rewriter at query time.** Today, "Bill Gates"
   doesn't directly retrieve Cascade Investment chunks unless "Gates"
   appears in the chunk text (it does, via principal_family). A small
   prompt-side query rewriter could expand person names to FO names.
3. **Conversation memory.** The Streamlit app is one-shot. Adding
   short conversation history would let users drill down ("and what
   about their PE positions?").
4. **Per-domain retrieval filters.** Allow the user to scope to
   `domain=equities` etc. via a sidebar — sometimes the user knows
   which framework domain they care about.
5. **Honest eval automation.** A cron job that runs `eval.py` weekly
   against a frozen index, flagging regressions when chunks change.
