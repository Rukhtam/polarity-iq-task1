"""Retriever + synthesis. The query → response part of the RAG pipeline.

Flow:
  1. Embed the query with Gemini text-embedding-004 (task_type=retrieval_query)
  2. Search ChromaDB for top-k chunks, balanced between fo_profile and signal
  3. Pack chunks into a context string with source attribution
  4. Call Gemini 1.5 Flash with a system prompt that enforces source-grounded
     answers (no hallucination beyond the retrieved chunks)
  5. Return the answer + the source citations

No LangChain. Direct google-generativeai + chromadb. Provider switched
from OpenAI to Gemini because the user has a Gemini key, not OpenAI.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import chromadb
from chromadb.config import Settings
from google import genai
from google.genai import types

from ..llm import _log_cost

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CHROMA_DIR = REPO_ROOT / "data" / "chromadb"
COLLECTION_NAME = "polarity_iq"
EMBEDDING_MODEL = "gemini-embedding-001"
# Flash is the right tier for synthesis: faster, cheaper, and good enough
# at temperature=0 grounded synthesis. Pro is reserved for the longer
# unstructured-parsing jobs (990-PF grant extraction, news classification)
# that we deferred to Tier-3.
# Note: gemini-1.5-flash returned 404 on this account / API version.
# gemini-2.5-flash is the supported flash tier on the current v1beta API.
SYNTHESIS_MODEL = "gemini-2.5-flash"


SYSTEM_PROMPT = """You answer questions about family offices using only the
context retrieved from a curated dataset. Rules:

1. Ground every claim in the provided context. If the context does not
   support a claim, say so — do not invent.
2. Cite the FO by canonical name when answering. The context items are
   prefixed with [fo_id] tags; use those tags to attribute facts.
3. If the user asks about a specific FO and no context items for that FO
   are retrieved, say "I have no records on that FO" rather than guess.
4. Numbers are reported as-is from primary sources. If a number requires
   a caveat (e.g., 13F portfolio value is for managed positions, not
   family ownership), surface that caveat.
5. Keep answers concise. No hedging filler. No restating the question.
"""


@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    metadata: dict
    distance: float


@dataclass
class AnswerWithSources:
    answer: str
    chunks: list[RetrievedChunk]


# ---------------------------------------------------------------------------
# Clients (built lazily so tests can run without an API key)
# ---------------------------------------------------------------------------

def _gemini_client() -> "genai.Client":
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY not set. Add it to .env (see .env.example) "
            "before querying the RAG pipeline."
        )
    return genai.Client(api_key=key)


def _chroma_collection():
    if not CHROMA_DIR.exists():
        raise RuntimeError(
            f"ChromaDB store not found at {CHROMA_DIR}. "
            "Run `python -m src.rag.build_index` first."
        )
    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )
    return client.get_collection(COLLECTION_NAME)


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def retrieve(query: str, k_per_type: int = 4) -> list[RetrievedChunk]:
    """Type-balanced retrieval: k_per_type fo_profile + k_per_type signal.

    Two separate Chroma queries with `where` filters, then merged. This
    avoids the case where one type dominates the top-k just because the
    embeddings happen to score higher.
    """
    client = _gemini_client()
    coll = _chroma_collection()

    # Use RETRIEVAL_QUERY task_type so the query vector lives in the same
    # semantic space as the indexed RETRIEVAL_DOCUMENT vectors.
    emb = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=query,
        config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
    )
    _log_cost(EMBEDDING_MODEL, len(query) // 4, 0, "rag_query_embed")
    query_vec = emb.embeddings[0].values

    results: list[RetrievedChunk] = []
    for type_filter in ("fo_profile", "signal"):
        r = coll.query(
            query_embeddings=[query_vec],
            n_results=k_per_type,
            where={"type": type_filter},
        )
        ids = r["ids"][0]
        docs = r["documents"][0]
        metas = r["metadatas"][0]
        dists = r["distances"][0]
        for i in range(len(ids)):
            results.append(RetrievedChunk(
                chunk_id=ids[i],
                text=docs[i],
                metadata=metas[i],
                distance=dists[i],
            ))
    return results


# ---------------------------------------------------------------------------
# Synthesis
# ---------------------------------------------------------------------------

def answer(query: str, k_per_type: int = 4) -> AnswerWithSources:
    """Retrieve + synthesise. Returns (answer string, retrieved chunks)."""
    chunks = retrieve(query, k_per_type=k_per_type)
    if not chunks:
        return AnswerWithSources(
            answer="I have no records relevant to that query.",
            chunks=[],
        )

    # Build the context prompt — group profile chunks first, then signals
    profile_chunks = [c for c in chunks if c.metadata.get("type") == "fo_profile"]
    signal_chunks = [c for c in chunks if c.metadata.get("type") == "signal"]
    context_parts = []
    if profile_chunks:
        context_parts.append("Profile chunks:")
        for c in profile_chunks:
            context_parts.append(f"  - {c.text}")
    if signal_chunks:
        context_parts.append("Signal chunks (one fact each):")
        for c in signal_chunks:
            context_parts.append(f"  - {c.text}")
    context = "\n".join(context_parts)

    client = _gemini_client()
    user_message = f"Context:\n{context}\n\nQuestion: {query}"
    resp = client.models.generate_content(
        model=SYNTHESIS_MODEL,
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.0,
        ),
    )
    # Gemini exposes token counts via usage_metadata
    try:
        in_tok = resp.usage_metadata.prompt_token_count
        out_tok = resp.usage_metadata.candidates_token_count
    except Exception:
        in_tok = (len(SYSTEM_PROMPT) + len(user_message)) // 4
        out_tok = len(resp.text) // 4
    _log_cost(SYNTHESIS_MODEL, in_tok, out_tok, "rag_query_synthesis")
    return AnswerWithSources(
        answer=resp.text,
        chunks=chunks,
    )


if __name__ == "__main__":
    # Smoke test if invoked directly
    import sys
    q = " ".join(sys.argv[1:]) or "Tell me about Soros Fund Management."
    out = answer(q)
    print(f"Q: {q}\n")
    print(f"A: {out.answer}\n")
    print(f"Retrieved {len(out.chunks)} chunks:")
    for c in out.chunks:
        kind = c.metadata.get("type", "?")
        fo = c.metadata.get("fo_id", "?")
        print(f"  [{kind:11s}] {fo:30s}  dist={c.distance:.3f}")
