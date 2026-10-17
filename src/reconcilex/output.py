"""Portable, escaped review outputs and an export checksum manifest."""

import csv
import hashlib
import html
import json
import shutil
from pathlib import Path

from .models import ReconcileError

PAIR_FIELDS = ["ledger_id", "bank_id", "currency", "ledger_amount", "bank_amount", "difference",
               "date_gap_days", "ledger_date", "bank_date", "ledger_source_row", "bank_source_row",
               "ledger_reference", "bank_reference", "rule", "reasons"]
ROW_FIELDS = ["id", "date", "amount", "currency", "reference", "description", "source_row",
              "duplicate_content", "reason"]
NUMERIC_FIELDS = {"ledger_amount", "bank_amount", "difference", "amount", "date_gap_days", "source_row",
                  "ledger_source_row", "bank_source_row"}


def csv_text(value: object) -> str:
    """Neutralize formula-leading text for the initial spreadsheet import."""
    text = "; ".join(map(str, value)) if isinstance(value, list) else str(value)
    stripped = text.lstrip()
    if (stripped and stripped[0] in "=+-@") or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text


def _csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row[key] if key in NUMERIC_FIELDS else csv_text(row[key]) for key in fields})


def _table(title: str, rows: list[dict], fields: list[str], filename: str) -> str:
    esc = lambda value: html.escape(str(value), quote=True)
    def display(value: object) -> str:
        labels = {"reference_amount_date": "Reference + amount + date", "amount_date": "Amount + date",
                  "ambiguous_candidates": "Multiple eligible candidates", "duplicate_content": "Repeated source content",
                  "amount_difference": "Amount difference", "zero_amount": "Zero amount"}
        if isinstance(value, list):
            return "; ".join(labels.get(item, item) for item in value) or "—"
        return labels.get(str(value), str(value))
    headings = "".join(f"<th scope='col'>{esc(key.replace('_', ' '))}</th>" for key in fields)
    body = "".join("<tr>" + "".join(f"<td>{esc(display(row[key]))}</td>" for key in fields) + "</tr>" for row in rows[:200])
    if not rows:
        body = f"<tr><td colspan='{len(fields)}' class='empty'>No items in this section.</td></tr>"
    return (f"<section><div class='section-head'><h2>{esc(title)} <span>{len(rows)}</span></h2>"
            f"<a href='{esc(filename)}' download>Download CSV ↗</a></div>"
            f"<div class='table-wrap'><table><thead><tr>{headings}</tr></thead><tbody>{body}</tbody></table></div>"
            f"<p class='caption'>Showing {min(len(rows), 200)} of {len(rows)} rows. The CSV and JSON contain all rows and full field details.</p></section>")


def render_html(result: dict) -> str:
    esc = lambda value: html.escape(str(value), quote=True)
    s = result["summary"]
    cards = [("Exact pairs", s["matched_pairs"]), ("Review candidates", s["review_candidates"]),
             ("Ledger remaining", s["remaining_ledger"]), ("Bank remaining", s["remaining_bank"])]
    metrics = "".join(f"<div class='metric'><strong>{value}</strong><span>{label}</span></div>" for label, value in cards)
    totals = [{"currency": code, **values} for code, values in result["totals"].items()]
    total_fields = ["currency", "ledger_total", "bank_total", "input_difference", "remaining_difference", "conservation_passed"]
    totals_html = "<table><thead><tr>" + "".join(f"<th scope='col'>{key.replace('_', ' ')}</th>" for key in total_fields) + "</tr></thead><tbody>"
    totals_html += "".join("<tr>" + "".join(f"<td>{esc(row[key])}</td>" for key in total_fields) + "</tr>" for row in totals) + "</tbody></table>"
    preview_fields = ["ledger_id", "bank_id", "currency", "ledger_amount", "bank_amount", "difference",
                      "date_gap_days", "rule", "reasons"]
    sections = _table("Accepted exact pairs", result["matches"], preview_fields, "matches.csv")
    sections += _table("Candidates requiring review", result["review_candidates"], preview_fields, "review_candidates.csv")
    sections += _table("Remaining ledger transactions", result["remaining_ledger"], ROW_FIELDS, "remaining_ledger.csv")
    sections += _table("Remaining bank transactions", result["remaining_bank"], ROW_FIELDS, "remaining_bank.csv")
    warnings = [(source, message) for source, messages in result["warnings"].items() for message in messages]
    warnings_html = "".join(f"<li>{esc(source)}: {esc(message)}</li>" for source, message in warnings[:50])
    if warnings:
        sections += f"<section><h2>Input warnings ({len(warnings)})</h2><ul>{warnings_html}</ul><p>All warnings are retained in result.json.</p></section>"
    inputs = "".join(f"<p><strong>{esc(side)}</strong> · {esc(data['filename'])}<br><code>{esc(data['sha256'])}</code></p>" for side, data in result["inputs"].items())
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>ReconcileX · Reconciliation review</title><style>
:root {{color-scheme:light;--ink:#163633;--muted:#506762;--line:#d5dfd8;--paper:#f3f5ee;--green:#d2f273}}
* {{box-sizing:border-box}} body {{margin:0;background:var(--paper);color:var(--ink);font:15px/1.6 system-ui,sans-serif}}
header {{background:#123b35;color:#f2f6e9;padding:42px max(28px,calc((100vw - 1180px)/2)) 38px}}
.brand {{font-weight:750;letter-spacing:.08em;font-size:18px}} .eyebrow {{text-transform:uppercase;letter-spacing:.12em;font-size:12px;color:#b9d1c6}}
h1 {{font:500 clamp(30px,4vw,48px)/1.15 Georgia,serif;margin:18px 0}} header p {{max-width:750px;color:#c9ded2}}
.tag {{display:inline-block;border:1px solid #51776a;padding:4px 12px;border-radius:20px;font-size:12px}}
main {{max-width:1236px;margin:auto;padding:28px}} .metrics {{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:28px}}
.metric {{background:white;border:1px solid var(--line);border-top:4px solid #86ad83;padding:18px 22px;border-radius:6px}}
.metric:first-child {{background:var(--green);border-color:#abc667}} .metric strong {{display:block;font:500 38px/1.3 Georgia,serif}}
.metric span {{color:var(--muted);font-size:13px}} section {{background:white;border:1px solid var(--line);border-radius:6px;padding:24px;margin:20px 0}}
h2 {{font-size:18px;margin:0 0 12px}} h2 span {{font-size:12px;padding:2px 8px;background:#eef3e8;border-radius:12px}}
a {{color:#236547;text-underline-offset:3px}} .section-head {{display:flex;justify-content:space-between;gap:12px;align-items:baseline}}
.section-head a,.caption {{font-size:12px;color:var(--muted)}} .table-wrap {{overflow-x:auto}} .table-wrap table {{min-width:720px}} table {{border-collapse:collapse;width:100%;font-size:12px}}
th {{text-transform:uppercase;letter-spacing:.04em;font-size:10px;background:#f1f5ed;text-align:left;color:var(--muted)}}
th,td {{padding:12px 10px;border-bottom:1px solid #e5ebe2;vertical-align:top}} td {{overflow-wrap:anywhere;min-width:65px}}
.empty {{color:var(--muted);padding:20px}} .notice {{border-left:4px solid #b1cf80;padding:8px 16px;background:#f3f7ed}}
code {{font-size:11px;overflow-wrap:anywhere}} footer {{padding:12px 0 32px;color:var(--muted);font-size:12px}}
@media(max-width:700px) {{.metrics {{grid-template-columns:repeat(2,1fr)}} main {{padding:16px}} section {{padding:16px}} .section-head {{display:block}}}}
@media print {{header {{background:white;color:#123b35}} header p,.eyebrow {{color:#123b35}} section {{break-inside:avoid}}}}
</style></head><body><header><div class="brand">RECONCILE<span style="color:#d2f273">X</span></div>
<p class="eyebrow">Local transaction reconciliation / review report</p><h1>Clarity before you close.</h1>
<p>Exact pairs are separated from items that need your judgment. No records have been posted, modified, or sent to an external service by this tool.</p>
<span class="tag">{s['ledger_rows']} ledger rows · {s['bank_rows']} bank rows</span></header><main>
<div class="metrics">{metrics}</div><section><h2>Control totals by currency</h2>
<div class="table-wrap">{totals_html}</div><p class="notice">Conservation checks account for every row. Equal totals alone do not establish that transactions are reconciled. Review candidates can share rows; they are suggestions, not accepted pairs.</p></section>
{sections}<section><h2>Audit information</h2>{inputs}<p>Version {esc(result['app_version'])} · Created {esc(result['created_at'])}</p>
<p><a href="result.json" download>Full result &amp; configuration</a> · <a href="manifest.json" download>Export checksums</a></p>
<p class="caption">CSV exports neutralize formula-leading text. JSON preserves original text. Use appropriate access controls for financial data and review exports before sharing.</p></section>
<footer>ReconcileX · One-to-one CSV comparison. No FX conversion, split settlements, or automated accounting entries.</footer>
</main></body></html>'''


def write_report(result: dict, output: Path | str) -> Path:
    """Create a new report directory; refuse replacement of any existing path."""
    output = Path(output)
    try:
        output.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        raise ReconcileError(f"cannot create output directory (choose a new path): {exc}") from exc
    try:
        (output / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        for key, fields in [("matches", PAIR_FIELDS), ("review_candidates", PAIR_FIELDS),
                            ("remaining_ledger", ROW_FIELDS), ("remaining_bank", ROW_FIELDS)]:
            _csv(output / f"{key}.csv", result[key], fields)
        (output / "report.html").write_text(render_html(result), encoding="utf-8")
        hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(output.iterdir())}
        manifest = {"algorithm": "sha256", "files": hashes,
                    "note": "Checksums detect changes when compared with a trusted copy; they are not digital signatures."}
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError):
        shutil.rmtree(output)
        raise
    return output
