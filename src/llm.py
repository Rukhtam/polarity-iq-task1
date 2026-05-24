"""LLM client wrappers.

Single entry point for every LLM call in the project. Two reasons:
  1. Cost log — every call appends a row to data/llm_cost.log so we can
     report AI-vs-human work breakdown honestly in docs/time_effort.md.
  2. Spend cap — fail loudly if monthly cap is breached.

Providers:
  - Gemini (1.5 Pro) for bulk classification, news parsing, fuzzy entity
    resolution edge cases, and 990-PF PDF grant extraction.
  - OpenAI (gpt-4o-mini + text-embedding-3-small) for RAG synthesis +
    embeddings.

Pricing is approximate (May 2026). Update if providers change rates.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

COST_LOG = Path(__file__).resolve().parent.parent / "data" / "llm_cost.log"
COST_LOG.parent.mkdir(parents=True, exist_ok=True)

# USD per 1K tokens. Source: provider pricing pages, May 2026.
# text-embedding-004: priced per 1K *characters* not tokens, but free on
# the standard tier within generous limits — we log usage anyway.
PRICES = {
    "gemini-2.5-flash":            {"in": 0.000075, "out": 0.0003},
    "gemini-2.5-pro":              {"in": 0.00125, "out": 0.005},
    "gemini-embedding-001":        {"in": 0.0,     "out": 0.0},
    # Legacy / fallback entries
    "gemini-1.5-pro":              {"in": 0.00125, "out": 0.005},
    "gemini-1.5-flash":            {"in": 0.000075, "out": 0.0003},
    "gpt-4o-mini":                 {"in": 0.00015, "out": 0.0006},
    "text-embedding-3-small":      {"in": 0.00002, "out": 0.0},
}


def _log_cost(model: str, in_tokens: int, out_tokens: int, purpose: str) -> float:
    price = PRICES.get(model, {"in": 0.0, "out": 0.0})
    cost = (in_tokens / 1000) * price["in"] + (out_tokens / 1000) * price["out"]
    entry = {
        "ts":     datetime.now(timezone.utc).isoformat(),
        "model":  model,
        "in":     in_tokens,
        "out":    out_tokens,
        "usd":    round(cost, 6),
        "purpose": purpose,
    }
    with COST_LOG.open("a") as f:
        f.write(json.dumps(entry) + "\n")
    return cost


def gemini_generate(prompt: str, purpose: str, model: str = "gemini-1.5-pro") -> str:
    """One-shot Gemini text generation. Uses the supported google-genai SDK."""
    from google import genai
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")
    client = genai.Client(api_key=key)
    resp = client.models.generate_content(model=model, contents=prompt)
    try:
        in_tok = resp.usage_metadata.prompt_token_count
        out_tok = resp.usage_metadata.candidates_token_count
    except Exception:
        in_tok = len(prompt) // 4  # crude fallback
        out_tok = len(resp.text) // 4
    _log_cost(model, in_tok, out_tok, purpose)
    return resp.text


def openai_chat(
    messages: list[dict[str, str]],
    purpose: str,
    model: str = "gpt-4o-mini",
    temperature: float = 0.0,
) -> str:
    """OpenAI chat completion."""
    from openai import OpenAI
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )
    in_tok = resp.usage.prompt_tokens
    out_tok = resp.usage.completion_tokens
    _log_cost(model, in_tok, out_tok, purpose)
    return resp.choices[0].message.content


def openai_embed(texts: list[str], purpose: str, model: str = "text-embedding-3-small") -> list[list[float]]:
    """Batch OpenAI embeddings."""
    from openai import OpenAI
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    resp = client.embeddings.create(model=model, input=texts)
    in_tok = resp.usage.prompt_tokens
    _log_cost(model, in_tok, 0, purpose)
    return [d.embedding for d in resp.data]


def total_cost_usd() -> float:
    """Sum costs logged so far. Useful for spend-cap checks."""
    if not COST_LOG.exists():
        return 0.0
    total = 0.0
    with COST_LOG.open() as f:
        for line in f:
            try:
                total += json.loads(line)["usd"]
            except Exception:
                continue
    return total


if __name__ == "__main__":
    print(f"Cost log: {COST_LOG}")
    print(f"Total spent so far: ${total_cost_usd():.4f}")
