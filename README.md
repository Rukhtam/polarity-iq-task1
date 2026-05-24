# Polarity IQ — Differentiator Task 1

Validated dataset of 50 real Family Office records + RAG pipeline that exposes the dataset to natural-language queries.

## Status

Work in progress. See `PLAN.md` for the full plan and `docs/reasoning_log.md` for decisions in motion.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # then fill in keys

# Run the Soros pilot end-to-end (regression test)
pytest tests/test_pilot_soros.py

# Full pipeline (once stable)
python -m src.curate
python -m src.enrich --tier 1
python -m src.enrich --tier 2 --ids soros,<id2>,<id3>
python -m src.score_and_export

# RAG
python -m src.rag.build_index
python -m src.rag.eval
streamlit run src/rag/app.py
```

## Repo layout

See `PLAN.md` for the canonical structure and reasoning.

## Deliverables

- `data/family_offices.xlsx` — 50 records with per-field confidence
- `data/signals.csv` — long table, one row per signal with provenance
- `data/chains/*.md` — 3 deep-dive validation chains
- `src/rag/app.py` — Streamlit demo (live or recorded)
- `docs/methodology.md`, `docs/rag.md`, `docs/time_effort.md`, `docs/reasoning_log.md`
- `docs/task2_saas_conversion.md` — Task 2 written analysis
