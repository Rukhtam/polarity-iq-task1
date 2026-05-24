"""Minimal Streamlit demo for the Polarity IQ RAG pipeline.

Deliberately small. Per PLAN.md the screen recording is the canonical
demo deliverable; this Streamlit is the bonus live version.

Run locally:
    streamlit run src/rag/app.py

The app enforces a per-session query counter (20 queries max) as a soft
guard against unbounded OpenAI billing if it ever goes public-facing.
"""

from __future__ import annotations

import os

import streamlit as st
from dotenv import load_dotenv

from .retriever import answer

load_dotenv()

st.set_page_config(page_title="Polarity IQ — FO Knowledge Base", page_icon=":mag:")

st.title("Polarity IQ — Family Office Knowledge Base")
st.caption(
    "50 family offices, 400+ signals, all primary-source-grounded where Tier-1 "
    "yielded data. Answers are constrained to the dataset — no general-purpose "
    "world knowledge."
)


if "query_count" not in st.session_state:
    st.session_state.query_count = 0

MAX_QUERIES = 20

# Sidebar: status + sample queries
with st.sidebar:
    st.markdown("### Status")
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        st.success("Gemini key configured.")
    else:
        st.error("GEMINI_API_KEY not set — queries will fail.")
    st.markdown(f"**Queries this session:** {st.session_state.query_count}/{MAX_QUERIES}")
    st.markdown("---")
    st.markdown("### Sample queries")
    st.markdown(
        """
        - *Tell me about Soros Fund Management.*
        - *Which FOs file Form 13F with the SEC?*
        - *Foundation grant spending in 2023*
        - *European family offices*
        - *What is Walton Enterprises?*
        """
    )
    st.markdown("---")
    st.markdown(
        "Source code: "
        "[github.com/Rukhtam/polarity-iq-task1]"
        "(https://github.com/Rukhtam/polarity-iq-task1)"
    )


query = st.text_input(
    "Ask a question",
    placeholder="e.g. Which family offices file Form 13F?",
)

if query:
    if st.session_state.query_count >= MAX_QUERIES:
        st.warning(
            f"Query limit reached ({MAX_QUERIES}) for this session. "
            "Refresh to start a new session."
        )
    else:
        st.session_state.query_count += 1
        with st.spinner("Retrieving + synthesising..."):
            try:
                out = answer(query)
            except Exception as e:
                st.error(f"Error: {e}")
                out = None

        if out is not None:
            st.markdown("### Answer")
            st.markdown(out.answer)

            with st.expander(f"Retrieved {len(out.chunks)} source chunks"):
                for c in out.chunks:
                    kind = c.metadata.get("type", "?")
                    fo = c.metadata.get("fo_id", "?")
                    source = c.metadata.get("source_url", "")
                    st.markdown(
                        f"**[{kind}]** `{fo}`  *(distance: {c.distance:.3f})*\n\n"
                        f"{c.text}\n"
                    )
                    if source:
                        st.markdown(f"_Source:_ {source}")
                    st.markdown("---")
