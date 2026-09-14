"""PDF Reporting (DATAQX.pdf S43).

Assembles DataQX_Report.pdf from already-persisted per-run artifacts -- this module
never re-runs the pipeline. A missing artifact (e.g. validation_report.json when
/api/validate hasn't been called yet) is reported honestly as "not run", never
fabricated.
"""

from __future__ import annotations

import io
import json
import math
from pathlib import Path
from xml.sax.saxutils import escape as _xml_escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.core.config import get_settings

_MAX_LINEAGE_ROWS = 50
_TABLE_STYLE = TableStyle(
    [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
)


def _esc(value) -> str:
    """Escape a data-derived value for safe interpolation into a ReportLab
    Paragraph. Paragraph text is parsed as a small XML-like markup language --
    unescaped '&'/'<'/'>' in an ordinary filename or column name (e.g. "Sales &
    Marketing.csv") otherwise raises a parse error instead of rendering literally.
    None/NaN/Infinity render as "N/A" rather than the literal string "nan"."""
    if value is None:
        return "N/A"
    if isinstance(value, float) and not math.isfinite(value):
        return "N/A"
    return _xml_escape(str(value))


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _table(headers: list[str], rows: list[list[str]]) -> Table:
    data = [headers] + rows
    table = Table(data, repeatRows=1)
    table.setStyle(_TABLE_STYLE)
    return table


def generate_pdf_report(run_dir: Path, run_id: str) -> bytes:
    settings = get_settings()
    styles = getSampleStyleSheet()

    run_metadata = _load_json(run_dir / "run_metadata.json") or {}
    profile_data = _load_json(run_dir / "profile.json")
    issues_data = _load_json(run_dir / "issues.json")
    cleaning_data = _load_json(run_dir / "cleaning_log.json")
    lineage_data = _load_json(run_dir / "data_lineage.json")
    drift_data = _load_json(run_dir / "drift_report.json")
    validation_data = _load_json(run_dir / "validation_report.json")
    analytics_readiness_data = _load_json(run_dir / "analytics_readiness.json")
    quality_data = _load_json(run_dir / "quality_report.json")
    before_after_data = _load_json(run_dir / "before_after_summary.json")

    filenames = sorted((profile_data or {}).get("files", {}).keys())

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=LETTER, title="DataQX Report")
    story = []

    # --- Cover ---------------------------------------------------------------
    story.append(Spacer(1, 1.5 * inch))
    story.append(Paragraph("DATAQX", styles["Title"]))
    story.append(Paragraph("DATA QUALITY &amp; CLEANING REPORT", styles["Heading2"]))
    story.append(Spacer(1, 0.5 * inch))
    story.append(Paragraph(f"Project: {_esc(run_metadata.get('project_name') or 'N/A')}", styles["Normal"]))
    story.append(Paragraph(f"Dataset(s): {', '.join(_esc(f) for f in filenames) or 'N/A'}", styles["Normal"]))
    story.append(Paragraph(f"Date: {_esc(run_metadata.get('timestamp', 'N/A'))}", styles["Normal"]))
    story.append(Paragraph(f"Run ID: {_esc(run_id)}", styles["Normal"]))
    story.append(PageBreak())

    # --- Executive Summary -----------------------------------------------------
    story.append(Paragraph("Executive Summary", styles["Heading1"]))
    for filename in filenames:
        story.append(Paragraph(_esc(filename), styles["Heading3"]))
        q = (quality_data or {}).get("files", {}).get(filename)
        if q:
            story.append(
                Paragraph(
                    f"Initial quality: {_esc(q['before']['overall_score'])}/100 &nbsp;&rarr;&nbsp; "
                    f"Final quality: {_esc(q['after']['overall_score'])}/100",
                    styles["Normal"],
                )
            )
        else:
            story.append(Paragraph("Quality score not available (run /api/clean).", styles["Normal"]))

        file_issues = (issues_data or {}).get("files", {}).get(filename, [])
        top_issues = sorted(file_issues, key=lambda i: i.get("severity", ""), reverse=True)[:5]
        if top_issues:
            story.append(Paragraph("Major issues:", styles["Normal"]))
            for issue in top_issues:
                story.append(
                    Paragraph(
                        f"- {_esc(issue['issue_type'])} ({_esc(issue['column'])}): {_esc(issue['description'])}",
                        styles["Normal"],
                    )
                )
        else:
            story.append(Paragraph("No issues detected.", styles["Normal"]))

        low_confidence_count = sum(
            1 for i in file_issues if i.get("confidence", {}).get("confidence") == "LOW"
        )
        story.append(Paragraph(f"Remaining risks flagged for review: {low_confidence_count}", styles["Normal"]))
        story.append(Spacer(1, 0.2 * inch))
    story.append(PageBreak())

    # --- Dataset Overview -----------------------------------------------------
    story.append(Paragraph("Dataset Overview", styles["Heading1"]))
    for filename in filenames:
        file_profile = (profile_data or {}).get("files", {}).get(filename, {}).get("profile")
        story.append(Paragraph(_esc(filename), styles["Heading3"]))
        if file_profile:
            story.append(
                _table(
                    ["Rows", "Columns", "File Size (bytes)", "Duplicate Rows"],
                    [[
                        str(file_profile["row_count"]),
                        str(file_profile["column_count"]),
                        str(file_profile.get("file_size_bytes") or "N/A"),
                        str(file_profile["duplicate_row_count"]),
                    ]],
                )
            )
        story.append(Spacer(1, 0.2 * inch))
    story.append(PageBreak())

    # --- Data Quality Assessment -------------------------------------------
    story.append(Paragraph("Data Quality Assessment", styles["Heading1"]))
    for filename in filenames:
        file_issues = (issues_data or {}).get("files", {}).get(filename, [])
        story.append(Paragraph(_esc(filename), styles["Heading3"]))
        if file_issues:
            rows = [[i["issue_type"], str(i["column"]), i["severity"], str(i["affected_count"])] for i in file_issues]
            story.append(_table(["Issue Type", "Column", "Severity", "Affected"], rows))
        else:
            story.append(Paragraph("No data quality issues detected.", styles["Normal"]))
        story.append(Spacer(1, 0.2 * inch))
    story.append(PageBreak())

    # --- Cleaning Actions ------------------------------------------------------
    story.append(Paragraph("Cleaning Actions", styles["Heading1"]))
    for filename in filenames:
        file_clean = (cleaning_data or {}).get("files", {}).get(filename)
        story.append(Paragraph(_esc(filename), styles["Heading3"]))
        log_entries = (file_clean or {}).get("log", [])
        if log_entries:
            rows = [
                [e["issue_type"], str(e["column"]), e["confidence"], e["action_taken"], str(e["affected_count"])]
                for e in log_entries
            ]
            story.append(_table(["Issue", "Column", "Confidence", "Action", "Affected"], rows))
        else:
            story.append(Paragraph("No cleaning actions were applied.", styles["Normal"]))
        story.append(Spacer(1, 0.2 * inch))
    story.append(PageBreak())

    # --- Data Lineage -----------------------------------------------------------
    story.append(Paragraph("Data Lineage", styles["Heading1"]))
    for filename in filenames:
        entries = (lineage_data or {}).get("files", {}).get(filename, [])
        story.append(Paragraph(_esc(filename), styles["Heading3"]))
        if entries:
            shown = entries[:_MAX_LINEAGE_ROWS]
            rows = [[e["source_column"], e["transformation"], str(e["output_column"])] for e in shown]
            story.append(_table(["Raw Column", "Transformation", "Clean Column"], rows))
            if len(entries) > _MAX_LINEAGE_ROWS:
                story.append(
                    Paragraph(
                        f"+{len(entries) - _MAX_LINEAGE_ROWS} more row(s) -- see data_lineage.csv for the full list.",
                        styles["Italic"],
                    )
                )
        else:
            story.append(Paragraph("No lineage data available.", styles["Normal"]))
        story.append(Spacer(1, 0.2 * inch))
    story.append(PageBreak())

    # --- Data Drift ---------------------------------------------------------
    story.append(Paragraph("Data Drift", styles["Heading1"]))
    for filename in filenames:
        drift = (drift_data or {}).get("files", {}).get(filename)
        story.append(Paragraph(_esc(filename), styles["Heading3"]))
        if not drift or drift["overall_status"] == "no_history":
            story.append(Paragraph("No prior version of this dataset to compare against.", styles["Normal"]))
        elif not drift["findings"]:
            story.append(Paragraph(f"No drift detected (compared against {_esc(drift['compared_against'])}).", styles["Normal"]))
        else:
            rows = [[f["drift_type"], str(f["column"]), f["severity"], f["description"]] for f in drift["findings"]]
            story.append(_table(["Drift Type", "Column", "Severity", "Description"], rows))
        story.append(Spacer(1, 0.2 * inch))
    story.append(PageBreak())

    # --- Validation Gates ------------------------------------------------------
    story.append(Paragraph("Validation Gates", styles["Heading1"]))
    for filename in filenames:
        validation = (validation_data or {}).get("files", {}).get(filename)
        story.append(Paragraph(_esc(filename), styles["Heading3"]))
        if not validation:
            story.append(Paragraph("Validation was not run for this report. Run /api/validate to include it.", styles["Normal"]))
        else:
            story.append(Paragraph(f"Overall: {validation['overall_status'].upper()}", styles["Normal"]))
            rows = [[c["check_name"], c["status"].upper(), c["message"]] for c in validation["checks"]]
            story.append(_table(["Check", "Status", "Message"], rows))
        story.append(Spacer(1, 0.2 * inch))
    story.append(PageBreak())

    # --- Analytics Readiness ---------------------------------------------------
    # DataQX evaluates readiness for multiple analytics platforms from the same
    # underlying facts -- this is a readiness assessment, never a vendor
    # certification (no platform is ever described as "Certified").
    story.append(Paragraph("Analytics Readiness", styles["Heading1"]))
    for filename in filenames:
        file_readiness = (analytics_readiness_data or {}).get("files", {}).get(filename)
        story.append(Paragraph(_esc(filename), styles["Heading3"]))
        if not file_readiness:
            story.append(Paragraph("Analytics readiness not available.", styles["Normal"]))
            story.append(Spacer(1, 0.2 * inch))
            continue

        story.append(Paragraph(f"Overall Readiness: {file_readiness['overall_score']}/100", styles["Normal"]))
        platforms = file_readiness.get("platforms", {})
        comparison_rows = [
            [p["platform"], f"{p['score']}/100", p["status"].replace("_", " ")] for p in platforms.values()
        ]
        story.append(_table(["Platform", "Score", "Status"], comparison_rows))
        story.append(Spacer(1, 0.15 * inch))

        for platform_result in platforms.values():
            story.append(Paragraph(f"{_esc(platform_result['platform'])} Ready", styles["Heading4"]))
            rows = [[c["check_name"], c["status"].upper(), c["message"]] for c in platform_result["checks"]]
            story.append(_table(["Check", "Status", "Message"], rows))
            if platform_result.get("recommendations"):
                for rec in platform_result["recommendations"]:
                    story.append(Paragraph(f"- {_esc(rec)}", styles["Normal"]))
            story.append(Spacer(1, 0.1 * inch))
        story.append(Spacer(1, 0.2 * inch))
    story.append(PageBreak())

    # --- Before vs After ------------------------------------------------------
    story.append(Paragraph("Before vs After", styles["Heading1"]))
    for filename in filenames:
        summary = (before_after_data or {}).get("files", {}).get(filename)
        story.append(Paragraph(_esc(filename), styles["Heading3"]))
        if summary:
            rows = [[metric, str(v["before"]), str(v["after"]), str(v["change"])] for metric, v in summary.items()]
            story.append(_table(["Metric", "Before", "After", "Change"], rows))
        else:
            story.append(Paragraph("Before/after summary not available.", styles["Normal"]))
        story.append(Spacer(1, 0.2 * inch))
    story.append(PageBreak())

    # --- Remaining Issues & Recommendations ------------------------------------
    story.append(Paragraph("Remaining Issues", styles["Heading1"]))
    all_recommendations = []
    for filename in filenames:
        file_issues = (issues_data or {}).get("files", {}).get(filename, [])
        low_conf_issues = [i for i in file_issues if i.get("confidence", {}).get("confidence") == "LOW"]
        story.append(Paragraph(_esc(filename), styles["Heading3"]))
        if low_conf_issues:
            rows = [[i["issue_type"], str(i["column"]), str(i["affected_count"]), i["description"]] for i in low_conf_issues]
            story.append(_table(["Issue", "Column", "Affected", "Description"], rows))
            for issue in low_conf_issues:
                all_recommendations.append(
                    f"Review {issue['affected_count']} '{_esc(issue['issue_type'])}' finding(s) in "
                    f"'{_esc(issue['column'])}' ({_esc(filename)})."
                )
        else:
            story.append(Paragraph("No unresolved issues remain.", styles["Normal"]))
        story.append(Spacer(1, 0.2 * inch))
    story.append(PageBreak())

    story.append(Paragraph("Recommendations", styles["Heading1"]))
    if all_recommendations:
        for rec in all_recommendations:
            story.append(Paragraph(f"- {rec}", styles["Normal"]))
    else:
        story.append(Paragraph("No further action recommended.", styles["Normal"]))
    story.append(PageBreak())

    # --- Technical Appendix ---------------------------------------------------
    story.append(Paragraph("Technical Appendix", styles["Heading1"]))
    story.append(Paragraph(f"Software version: {settings.app_version}", styles["Normal"]))
    processing_times = run_metadata.get("processing_time_seconds", {})
    if processing_times:
        rows = [[stage, f"{seconds:.4f}s"] for stage, seconds in processing_times.items()]
        story.append(_table(["Stage", "Processing Time"], rows))
    bottleneck_stage = run_metadata.get("bottleneck_stage")
    if bottleneck_stage:
        story.append(
            Paragraph(
                f"Slowest stage: {bottleneck_stage} ({run_metadata.get('bottleneck_seconds', 0):.4f}s)",
                styles["Normal"],
            )
        )
    for filename in filenames:
        file_meta = run_metadata.get("files", {}).get(filename, {})
        story.append(
            Paragraph(
                f"{_esc(filename)} -- input hash: {_esc(file_meta.get('input_hash') or 'N/A')}, "
                f"output hash: {_esc(file_meta.get('output_hash') or 'N/A')}",
                styles["Normal"],
            )
        )
    if quality_data:
        first_file = next(iter(quality_data.get("files", {}).values()), None)
        if first_file:
            story.append(Paragraph("Quality score methodology:", styles["Heading3"]))
            for dimension, formula in first_file["after"]["methodology"].items():
                story.append(Paragraph(f"- {dimension}: {formula}", styles["Normal"]))

    doc.build(story)
    return buffer.getvalue()
