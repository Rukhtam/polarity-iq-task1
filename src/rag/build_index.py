"""Build the RAG index: hybrid chunking + embeddings into ChromaDB.

Chunking strategy (per PLAN.md, "Hybrid chunking" decision):
  - Parent doc per FO: a structured prose paragraph covering identity +
    headline facts. ~400-800 tokens. Tag: metadata.type = "fo_profile".
  - Child doc per signal: a short statement of one fact with its source.
    Always carries the parent FO's canonical name in the chunk text so
    the LLM can connect signal → FO at synthesis time. ~50-150 tokens.
    Tag: metadata.type = "signal".

Both indexed in the same ChromaDB collection. Retriever can do type-
balanced top-k sampling.

Run:
  python -m src.rag.build_index
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from openai import OpenAI

import chromadb
from chromadb.config import Settings

from ..db import DB_PATH
from ..llm import _log_cost  # reuse cost-logging primitive

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CHROMA_DIR = REPO_ROOT / "data" / "chromadb"
COLLECTION_NAME = "polarity_iq"
EMBEDDING_MODEL = "text-embedding-3-small"  # 1536 dimensions, cheap


# ---------------------------------------------------------------------------
# Chunk builders
# ---------------------------------------------------------------------------

def _format_usd(v: str | int | None) -> str:
    if v in (None, "", "0"):
        return ""
    try:
        n = int(v)
        if abs(n) >= 1_000_000_000:
            return f"${n / 1_000_000_000:.1f}B"
        if abs(n) >= 1_000_000:
            return f"${n / 1_000_000:.0f}M"
        return f"${n:,}"
    except Exception:
        return str(v)


def build_fo_profile(fo_row: dict, fo_signals: list[dict]) -> str:
    """Combine identity + headline facts into one prose chunk per FO."""
    name = fo_row.get("canonical_name") or fo_row.get("fo_id")
    fo_id = fo_row["fo_id"]
    type_ = fo_row.get("type", "Unknown")
    city = fo_row.get("hq_city", "")
    country = fo_row.get("hq_country", "")
    foundation_ein = fo_row.get("foundation_ein", "") or ""

    # Pull a few key signal values for the headline summary
    sig_by_field: dict[str, str] = {}
    for s in fo_signals:
        sig_by_field.setdefault(s["field"], s["value"])

    # principal_family lives in signals (not family_offices schema)
    family = sig_by_field.get("principal_family", "")

    headline_bits = []
    if sig_by_field.get("files_form_13f") == "true":
        date = sig_by_field.get("latest_13f_filing_date", "")
        headline_bits.append(
            f"Registered SEC investment adviser; files Form 13F-HR (most recent {date})."
        )
    total_aum = sig_by_field.get("total_13f_portfolio_value_usd")
    if total_aum:
        positions = sig_by_field.get("13f_position_count", "?")
        headline_bits.append(
            f"Reports {positions} 13F-managed positions totalling {_format_usd(total_aum)}."
        )
    linked_fnd = sig_by_field.get("linked_foundation")
    if linked_fnd:
        headline_bits.append(f"Linked private foundation: {linked_fnd} (EIN {foundation_ein}).")
    fnd_grants = next(
        (sig_by_field[k] for k in sig_by_field if k.startswith("grants_and_contributions_paid_usd_")),
        None,
    )
    if fnd_grants:
        year = next(
            (k.split("_")[-1] for k in sig_by_field if k.startswith("grants_and_contributions_paid_usd_")),
            "",
        )
        headline_bits.append(
            f"Foundation paid {_format_usd(fnd_grants)} in grants in {year}."
        )

    headline = " ".join(headline_bits) or "No primary-source enrichment signals captured at Tier-1."

    profile = (
        f"[{fo_id}] {name} is a {type_}-type family office, principal family "
        f"{family or 'unspecified'}, headquartered in {city}, {country}. "
        f"{headline}"
    )
    return profile


def build_signal_chunk(signal: dict, fo_name: str) -> str:
    """Compact chunk for one signal. Parent FO name embedded for retrieval."""
    value = signal["value"]
    # JSON-encoded values (e.g. top_10_13f_holdings): unpack briefly
    if isinstance(value, str) and value.startswith("[") and signal["field"].startswith("top_"):
        try:
            data = json.loads(value)
            preview = "; ".join(f"{d['issuer']} ({_format_usd(d['value_usd'])})" for d in data[:5])
            value = f"top positions including {preview}"
        except Exception:
            pass

    method = signal.get("method", "")
    source_hint = method.replace("_", " ").replace("propublica", "ProPublica").replace("sec", "SEC")
    return (
        f"[{signal['fo_id']}] {fo_name}: {signal['field']} = {value} "
        f"(domain={signal['domain']}, source={source_hint}, "
        f"confidence={signal['confidence']})"
    )


# ---------------------------------------------------------------------------
# Embedding helper (OpenAI directly — no LangChain)
# ---------------------------------------------------------------------------

def embed_batch(client: OpenAI, texts: list[str]) -> list[list[float]]:
    """Single batched call to OpenAI embeddings. Returns one vector per text."""
    resp = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    _log_cost(EMBEDDING_MODEL, resp.usage.prompt_tokens, 0, "rag_build_index")
    return [d.embedding for d in resp.data]


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main(dry_run: bool = False) -> None:
    import os
    from dotenv import load_dotenv
    load_dotenv()
    if not dry_run and not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY not set. Set it in .env (see .env.example) "
            "before running build_index. Or pass --dry-run to inspect "
            "chunks without embedding."
        )
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", "")) if not dry_run else None

    # Read DB
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    fos = [dict(r) for r in conn.execute(
        "SELECT * FROM family_offices ORDER BY fo_id"
    ).fetchall()]
    signals = [dict(r) for r in conn.execute(
        "SELECT * FROM signals ORDER BY fo_id, signal_id"
    ).fetchall()]
    conn.close()

    # Index signals by fo_id
    sigs_by_fo: dict[str, list[dict]] = {}
    for s in signals:
        sigs_by_fo.setdefault(s["fo_id"], []).append(s)

    # Build chunks
    chunks: list[dict] = []
    for fo in fos:
        fo_id = fo["fo_id"]
        fo_sigs = sigs_by_fo.get(fo_id, [])
        profile = build_fo_profile(fo, fo_sigs)
        chunks.append({
            "id": f"profile::{fo_id}",
            "text": profile,
            "metadata": {
                "type": "fo_profile",
                "fo_id": fo_id,
                "canonical_name": fo["canonical_name"] or "",
                "principal_family": fo.get("principal_family") or "",
            },
        })
        for s in fo_sigs:
            chunks.append({
                "id": f"signal::{s['signal_id']}",
                "text": build_signal_chunk(s, fo["canonical_name"] or fo_id),
                "metadata": {
                    "type": "signal",
                    "fo_id": fo_id,
                    "field": s["field"],
                    "domain": s["domain"],
                    "method": s["method"],
                    "confidence": float(s["confidence"]),
                    "source_url": s["source_url"],
                },
            })

    print(f"Built {len(chunks)} chunks "
          f"({sum(1 for c in chunks if c['metadata']['type']=='fo_profile')} profiles, "
          f"{sum(1 for c in chunks if c['metadata']['type']=='signal')} signals)")

    if dry_run:
        print()
        print("DRY RUN — sample chunks (first 5 profiles, first 5 signals):")
        profiles = [c for c in chunks if c["metadata"]["type"] == "fo_profile"][:5]
        signals_only = [c for c in chunks if c["metadata"]["type"] == "signal"][:5]
        for c in profiles:
            print(f"\n  PROFILE [{c['metadata']['fo_id']}]:\n    {c['text']}")
        for c in signals_only:
            print(f"\n  SIGNAL  [{c['metadata']['fo_id']} / {c['metadata']['field']}]:\n    {c['text']}")
        return

    # Embed in batches (OpenAI accepts up to 2048 inputs per call but for
    # clarity we batch in 100s)
    BATCH = 100
    embeddings: list[list[float]] = []
    for i in range(0, len(chunks), BATCH):
        batch = [c["text"] for c in chunks[i:i + BATCH]]
        embeddings.extend(embed_batch(client, batch))
        print(f"  embedded {min(i+BATCH, len(chunks))}/{len(chunks)}")

    # Chroma persistent store
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client_chroma = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )
    # Recreate the collection idempotently
    try:
        client_chroma.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    coll = client_chroma.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    coll.add(
        ids=[c["id"] for c in chunks],
        documents=[c["text"] for c in chunks],
        embeddings=embeddings,
        metadatas=[c["metadata"] for c in chunks],
    )

    print()
    print(f"Wrote {coll.count()} chunks → {CHROMA_DIR}")


if __name__ == "__main__":
    import sys
    main(dry_run="--dry-run" in sys.argv)
