"""RAG evaluation: 12 queries with expected-FO retrieval targets.

This is the "queries that failed" surface the brutal review insisted on.
Run this BEFORE declaring the RAG pipeline done. Honestly report failures
in docs/rag.md.

Run:
  python -m src.rag.eval
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from src.rag.retriever import retrieve


# Each query specifies which fo_ids we expect to see in the top-k results.
# "Should retrieve" = at least one chunk for the listed fo_id should appear
# in the merged top-8 (4 profile + 4 signal) results.
EVAL_QUERIES = [
    # ----- Entity questions (parent-doc retrieval expected) -----
    {
        "query": "Tell me about Soros Fund Management.",
        "expects_fo_ids": ["soros_fund_management"],
        "kind": "entity",
    },
    {
        "query": "What is the Walton family office?",
        "expects_fo_ids": ["walton_enterprises"],
        "kind": "entity",
    },
    {
        "query": "Describe Rockefeller Capital Management.",
        "expects_fo_ids": ["rockefeller_capital_management"],
        "kind": "entity",
    },
    {
        "query": "Cascade Investment Bill Gates",
        "expects_fo_ids": ["cascade_investment"],
        "kind": "entity",
    },

    # ----- Pattern questions across multiple FOs -----
    {
        "query": "Which family offices file Form 13F with the SEC?",
        "expects_fo_ids": ["soros_fund_management", "rockefeller_capital_management"],
        "kind": "pattern",
    },
    {
        "query": "Family offices with linked private foundations paying large grants.",
        "expects_fo_ids": ["soros_fund_management", "walton_enterprises",
                           "rockefeller_capital_management"],
        "kind": "pattern",
    },
    {
        "query": "Which family offices are headquartered in New York City?",
        "expects_fo_ids": ["soros_fund_management", "rockefeller_capital_management"],
        "kind": "pattern",
    },
    {
        "query": "Tech-founder-affiliated family offices",
        "expects_fo_ids": ["cascade_investment", "iconiq_capital", "bezos_expeditions",
                           "hillspire", "sergey_brin"],
        "kind": "pattern",
    },

    # ----- Specific-signal questions -----
    {
        "query": "What is the value of Soros's largest 13F position?",
        "expects_fo_ids": ["soros_fund_management"],
        "kind": "signal",
    },
    {
        "query": "Foundation grant spending in 2023",
        "expects_fo_ids": ["soros_fund_management", "walton_enterprises",
                           "rockefeller_capital_management"],
        "kind": "signal",
    },
    {
        "query": "European family offices",
        "expects_fo_ids": ["jab_holding", "pictet_group", "bregal_investments"],
        "kind": "pattern",
    },

    # ----- A deliberately hard one — we expect this to underperform -----
    {
        "query": "Which family offices have invested in artificial intelligence?",
        "expects_fo_ids": [],   # No Tier-1 source gave us AI-investment signals
        "kind": "out_of_scope",
    },
]


@dataclass
class EvalResult:
    query: str
    kind: str
    expected: set[str]
    retrieved_fos: set[str]
    hit: bool
    note: str = ""


def run_eval() -> list[EvalResult]:
    results: list[EvalResult] = []
    for case in EVAL_QUERIES:
        try:
            chunks = retrieve(case["query"], k_per_type=4)
        except Exception as e:
            results.append(EvalResult(
                query=case["query"],
                kind=case["kind"],
                expected=set(case["expects_fo_ids"]),
                retrieved_fos=set(),
                hit=False,
                note=f"retrieval-error: {e}",
            ))
            continue
        retrieved = {c.metadata.get("fo_id") for c in chunks}
        expected = set(case["expects_fo_ids"])
        # Pass criterion:
        #   - For entity / signal queries: at least one expected fo_id is retrieved
        #   - For pattern queries: >= half of the expected fo_ids retrieved
        #   - For out_of_scope: empty expected, so we just record what came back
        if case["kind"] == "out_of_scope":
            hit = True  # not a pass/fail; we're documenting behaviour
            note = (
                f"Query is deliberately out of dataset scope. "
                f"Retrieval returned: {sorted(retrieved)}"
            )
        elif case["kind"] == "pattern":
            overlap = retrieved & expected
            hit = len(overlap) >= max(1, len(expected) // 2)
            note = (
                f"Overlap: {sorted(overlap)} / expected {sorted(expected)}"
            )
        else:
            hit = bool(retrieved & expected)
            note = (
                f"Retrieved {sorted(retrieved)[:5]}; expected at least one of "
                f"{sorted(expected)}"
            )
        results.append(EvalResult(
            query=case["query"],
            kind=case["kind"],
            expected=expected,
            retrieved_fos=retrieved,
            hit=hit,
            note=note,
        ))
    return results


def main() -> None:
    results = run_eval()
    passes = sum(1 for r in results if r.hit and r.kind != "out_of_scope")
    total = sum(1 for r in results if r.kind != "out_of_scope")
    print(f"Eval: {passes}/{total} queries pass (excluding out-of-scope cases)")
    print()
    for r in results:
        flag = "PASS" if r.hit else "FAIL"
        if r.kind == "out_of_scope":
            flag = "OOS "
        print(f"  [{flag}] {r.kind:12s} | {r.query[:60]:60s}")
        print(f"          {r.note[:160]}")
        print()


if __name__ == "__main__":
    main()
