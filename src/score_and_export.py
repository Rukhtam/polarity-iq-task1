"""Score per-field confidence and export the Excel + long-form signals CSV.

This is the deterministic, auditable layer. No LLM here — every rule is
explicit and can be eyeballed in the FIELD_RULES table below. The brutal
review's bar: a reader should be able to look at any cell in the output
spreadsheet, look at the corresponding FIELD_RULES entry, and see exactly
why that value was chosen and at what confidence.

Outputs:
  data/family_offices.xlsx  — sheet "family_offices" (wide, 1 row/FO) +
                              sheet "signals" (long, every signal w/ provenance)
  data/signals.csv          — same data as the signals sheet, plain CSV for
                              dataset consumers who don't want Excel.

Run:
  python -m src.score_and_export
"""

from __future__ import annotations

import csv
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

from .db import DB_PATH


REPO_ROOT = Path(__file__).resolve().parent.parent
XLSX_PATH = REPO_ROOT / "data" / "family_offices.xlsx"
SIGNALS_CSV = REPO_ROOT / "data" / "signals.csv"


# ---------------------------------------------------------------------------
# FIELD_RULES — the entire defensibility of the scoring layer lives here.
# ---------------------------------------------------------------------------
#
# Each tuple: (output_column, candidate_signals)
#   - output_column: the column name in family_offices.xlsx
#   - candidate_signals: list of (signal_field, method) tuples, IN PRIORITY
#       ORDER. The scorer picks the first match and stops. This is a
#       transparent way to encode "SEC wins on legal facts; seed is the
#       last-resort fallback."
#
# Reasoning for the priority decisions:
#   - legal_name (the SEC-registered name) is preferred over the seed's
#     canonical_name because the SEC name IS the legal name; the seed name
#     was our best guess. When both exist, prefer SEC.
#   - For type / principal_family / hq_country, the only source available
#     is seed_curation. We don't try to infer these from SEC.
#   - For SEC filing flags + 990-PF facts, only the primary-source method
#     is allowed — we deliberately do not invent these from seed data.
#
# Confidence (the column "<field>_confidence" in the output) comes from
# the picked signal's stored confidence. It is NOT overridden here.
FIELD_RULES: list[tuple[str, list[tuple[str, str]]]] = [
    # Identity
    ("canonical_name", [
        ("legal_name", "sec_edgar_submissions"),
        ("canonical_name_seed", "seed_curation"),
    ]),
    ("type", [
        ("type", "seed_curation"),
    ]),
    ("principal_family", [
        ("principal_family", "seed_curation"),
    ]),
    ("hq_address", [
        ("hq_address", "sec_edgar_submissions"),
    ]),
    ("hq_city", [
        ("hq_city_seed", "seed_curation"),
    ]),
    ("hq_country", [
        ("hq_country", "seed_curation"),
    ]),
    ("sec_cik", [
        ("cik", "manual_curation_from_primary_source"),
    ]),
    # Equities domain
    ("files_form_13f", [
        ("files_form_13f", "sec_edgar_submissions"),
    ]),
    ("latest_13f_filing_date", [
        ("latest_13f_filing_date", "sec_edgar_submissions"),
    ]),
    ("files_schedule_13gd", [
        ("files_schedule_13gd", "sec_edgar_submissions"),
    ]),
    # Private domain
    ("latest_form_d_date", [
        ("latest_form_d_date", "sec_edgar_submissions"),
    ]),
    # Soft power domain
    ("linked_foundation", [
        ("linked_foundation", "propublica_np_explorer"),
    ]),
    ("foundation_990pf_latest_year", [
        ("foundation_990pf_latest_year", "propublica_np_explorer"),
    ]),
    ("latest_990pf_pdf_url", [
        ("latest_990pf_pdf_url", "propublica_np_explorer"),
    ]),
]


# Confidence bucket colours for the Excel output. Cutoffs documented in
# reasoning_log "Confidence bucket cutoffs" (TODO when we finalise).
GREEN_FILL  = PatternFill("solid", fgColor="C6EFCE")
YELLOW_FILL = PatternFill("solid", fgColor="FFEB9C")
RED_FILL    = PatternFill("solid", fgColor="FFC7CE")
HEADER_FILL = PatternFill("solid", fgColor="305496")
HEADER_FONT = Font(color="FFFFFF", bold=True)


def confidence_fill(c: float | None) -> PatternFill | None:
    if c is None or c == "":
        return None
    try:
        c = float(c)
    except Exception:
        return None
    if c >= 0.85:
        return GREEN_FILL
    if c >= 0.6:
        return YELLOW_FILL
    return RED_FILL


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PickedValue:
    value: str | None
    confidence: float | None
    source_url: str | None
    method: str | None


def pick(signals_by_field: dict[str, list[sqlite3.Row]], rule: list[tuple[str, str]]) -> PickedValue:
    """Apply the priority list. First match wins. None if nothing matches."""
    for signal_field, method in rule:
        candidates = signals_by_field.get(signal_field, [])
        for sig in candidates:
            if sig["method"] == method:
                return PickedValue(
                    value=sig["value"],
                    confidence=sig["confidence"],
                    source_url=sig["source_url"],
                    method=sig["method"],
                )
    return PickedValue(None, None, None, None)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_signals(conn: sqlite3.Connection) -> dict[str, dict[str, list[sqlite3.Row]]]:
    """Returns {fo_id: {signal_field: [signal_rows...]}}."""
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT * FROM signals ORDER BY fo_id, field, extracted_at DESC"
    )
    by_fo: dict[str, dict[str, list[sqlite3.Row]]] = defaultdict(lambda: defaultdict(list))
    for r in cur.fetchall():
        by_fo[r["fo_id"]][r["field"]].append(r)
    return by_fo


def load_family_offices(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return conn.execute(
        "SELECT * FROM family_offices ORDER BY fo_id"
    ).fetchall()


# ---------------------------------------------------------------------------
# Scoring + export
# ---------------------------------------------------------------------------

def score_all(conn: sqlite3.Connection) -> tuple[list[dict], list[sqlite3.Row]]:
    """Returns (scored_rows, all_signals).

    scored_rows: list of dicts with one entry per (field, picked-value),
    plus the *_confidence + *_source columns.
    all_signals: every signal row in the DB, for the long-form sheet.
    """
    fos = load_family_offices(conn)
    signals_per_fo = load_signals(conn)

    rows = []
    for fo in fos:
        fo_id = fo["fo_id"]
        signals_by_field = signals_per_fo.get(fo_id, {})
        out: dict = {"fo_id": fo_id}
        for col, rule in FIELD_RULES:
            picked = pick(signals_by_field, rule)
            out[col] = picked.value
            out[f"{col}_confidence"] = (
                round(picked.confidence, 2) if picked.confidence is not None else None
            )
            out[f"{col}_source"] = picked.source_url
        # Carry across foundation_ein from family_offices table (it's not a signal field)
        out["foundation_ein"] = fo["foundation_ein"]
        # Total signal count + the highest-authority method used anywhere
        all_sigs = [s for sigs in signals_by_field.values() for s in sigs]
        out["signal_count"] = len(all_sigs)
        # Number of primary-source signals (i.e. not seed_curation)
        out["primary_source_count"] = sum(
            1 for s in all_sigs if s["method"] != "seed_curation"
        )
        rows.append(out)

    conn.row_factory = sqlite3.Row
    all_signals = conn.execute(
        "SELECT fo_id, field, domain, value, source_url, method, confidence, extracted_at, notes "
        "FROM signals ORDER BY fo_id, signal_id"
    ).fetchall()
    return rows, all_signals


def write_excel(rows: list[dict], all_signals: list[sqlite3.Row], path: Path = XLSX_PATH) -> None:
    wb = Workbook()

    # ---- Sheet 1: family_offices ----
    ws = wb.active
    ws.title = "family_offices"

    if not rows:
        ws.append(["no data"])
        wb.save(path)
        return

    # Column order: fo_id, then for each output field group: (value, confidence, source)
    columns = ["fo_id", "foundation_ein"]
    for col, _ in FIELD_RULES:
        columns.append(col)
        columns.append(f"{col}_confidence")
        columns.append(f"{col}_source")
    columns += ["signal_count", "primary_source_count"]

    ws.append(columns)
    for cell in ws[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(vertical="center", horizontal="left")
    ws.freeze_panes = "B2"

    for row in rows:
        ws.append([row.get(c, "") for c in columns])
        excel_row = ws.max_row
        # Apply confidence colouring to the *_confidence cells
        for ci, col in enumerate(columns, start=1):
            if col.endswith("_confidence"):
                val = row.get(col)
                fill = confidence_fill(val)
                if fill is not None:
                    ws.cell(row=excel_row, column=ci).fill = fill

    # Wider columns for readability
    widths = {
        "fo_id": 32, "foundation_ein": 14, "canonical_name": 38,
        "canonical_name_source": 60, "hq_address": 50,
        "linked_foundation": 38, "latest_990pf_pdf_url": 70,
    }
    for i, col in enumerate(columns, start=1):
        w = widths.get(col, 18 if col.endswith("_confidence") else 22)
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = w

    # ---- Sheet 2: signals (long form) ----
    ws2 = wb.create_sheet("signals")
    sig_cols = ["fo_id", "field", "domain", "value", "source_url",
                "method", "confidence", "extracted_at", "notes"]
    ws2.append(sig_cols)
    for cell in ws2[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
    ws2.freeze_panes = "B2"
    for s in all_signals:
        ws2.append([s[c] for c in sig_cols])
        excel_row = ws2.max_row
        fill = confidence_fill(s["confidence"])
        if fill is not None:
            ws2.cell(row=excel_row, column=sig_cols.index("confidence") + 1).fill = fill

    widths2 = {"fo_id": 32, "field": 30, "domain": 14, "value": 50,
               "source_url": 50, "method": 26, "confidence": 12,
               "extracted_at": 28, "notes": 50}
    for i, col in enumerate(sig_cols, start=1):
        ws2.column_dimensions[ws2.cell(row=1, column=i).column_letter].width = widths2.get(col, 16)

    # ---- Sheet 3: rule_table (the FIELD_RULES, made visible) ----
    ws3 = wb.create_sheet("rule_table")
    ws3.append(["output_field", "priority", "signal_field", "method", "reasoning"])
    for cell in ws3[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
    for output_field, rule in FIELD_RULES:
        for i, (sf, m) in enumerate(rule, start=1):
            ws3.append([output_field, i, sf, m, ""])
    for i, col in enumerate(["output_field", "priority", "signal_field", "method", "reasoning"], start=1):
        ws3.column_dimensions[ws3.cell(row=1, column=i).column_letter].width = 24

    wb.save(path)


def write_signals_csv(all_signals: list[sqlite3.Row], path: Path = SIGNALS_CSV) -> None:
    sig_cols = ["fo_id", "field", "domain", "value", "source_url",
                "method", "confidence", "extracted_at", "notes"]
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=sig_cols)
        w.writeheader()
        for s in all_signals:
            w.writerow({c: s[c] for c in sig_cols})


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    rows, all_signals = score_all(conn)
    write_excel(rows, all_signals)
    write_signals_csv(all_signals)
    conn.close()

    # Console summary
    print(f"Wrote {len(rows)} family-office rows + {len(all_signals)} signals")
    print(f"  Excel: {XLSX_PATH}")
    print(f"  CSV:   {SIGNALS_CSV}")
    print()
    high = sum(1 for r in rows if (r.get("canonical_name_confidence") or 0) >= 0.85)
    primary = sum(1 for r in rows if (r.get("primary_source_count") or 0) > 0)
    seed_only = len(rows) - primary
    print(f"Rows with primary-source name (SEC):  {high}")
    print(f"Rows with >= 1 primary-source signal:  {primary}")
    print(f"Rows with seed identity only (no SEC/IRS yet): {seed_only}")


if __name__ == "__main__":
    main()
