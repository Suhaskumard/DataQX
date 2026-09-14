"""Multi-format dataset ingestion.

Loads an uploaded raw file (already saved untouched under data/input/<run_id>/ by the
upload endpoint) into a pandas DataFrame, auto-detecting format/encoding/delimiter.
Never assumes CSV (DATAQX.pdf S13). Read-only with respect to the source file -- the
raw file on disk is never modified.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from pathlib import Path

import chardet
import openpyxl
import pandas as pd


class IngestionError(Exception):
    """Raised for a friendly, user-facing reason the dataset could not be loaded."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


@dataclass
class IngestionResult:
    dataframe: pd.DataFrame
    detected_format: str
    encoding: str | None = None
    delimiter: str | None = None
    sheet_name: str | None = None
    warnings: list[str] = field(default_factory=list)


_DELIMITER_BY_EXTENSION = {".csv": ",", ".tsv": "\t"}


def _detect_encoding(raw_bytes: bytes) -> str:
    if raw_bytes.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    try:
        raw_bytes.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass
    detected = chardet.detect(raw_bytes)
    encoding = detected.get("encoding")
    if not encoding:
        raise IngestionError("Could not detect the text encoding of this file.")
    return encoding


def _sniff_delimiter(sample_text: str, default: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample_text, delimiters=",\t;|")
        return dialect.delimiter
    except csv.Error:
        return default


def _load_delimited_text(path: Path, default_delimiter: str | None) -> IngestionResult:
    raw_bytes = path.read_bytes()
    encoding = _detect_encoding(raw_bytes)
    try:
        text = raw_bytes.decode(encoding)
    except UnicodeDecodeError as exc:
        # chardet's guess is a best-effort heuristic, not a guarantee -- a
        # low-confidence wrong guess must still surface as a friendly rejection,
        # not an unhandled 500.
        raise IngestionError(f"Could not decode file as {encoding}: {exc}") from exc
    sample = text[:8192]

    delimiter = _sniff_delimiter(sample, default_delimiter or ",")
    warnings: list[str] = []

    # keep_default_na=False + na_values=[]: pandas' default NA list silently turns
    # placeholder text ("N/A", "NA", "null", "Unknown", ...) into NaN during parsing,
    # which would make it invisible to Phase 6's contextual missing-value detection
    # (DATAQX.pdf S17 requires a *decision*, not pandas' blind default). Only a
    # genuinely empty cell is treated as missing here (normalized to NaN below);
    # everything else survives as literal text for issue detection to judge.
    read_kwargs = dict(sep=delimiter, keep_default_na=False, na_values=[])
    try:
        df = pd.read_csv(io.StringIO(text), **read_kwargs)
    except pd.errors.ParserError:
        bad_lines: list[list[str]] = []

        def _collect_bad_line(bad_line: list[str]) -> None:
            bad_lines.append(bad_line)
            return None

        df = pd.read_csv(
            io.StringIO(text),
            engine="python",
            on_bad_lines=_collect_bad_line,
            **read_kwargs,
        )
        if bad_lines:
            warnings.append(f"Skipped {len(bad_lines)} malformed row(s) with an unexpected field count.")

    if df.shape[1] == 0:
        raise IngestionError("File has no columns after parsing.")

    for column in df.select_dtypes(include="object").columns:
        df[column] = df[column].where(df[column].str.strip() != "", other=pd.NA)

    return IngestionResult(
        dataframe=df,
        detected_format="delimited-text",
        encoding=encoding,
        delimiter=delimiter,
        warnings=warnings,
    )


def _load_excel(path: Path) -> IngestionResult:
    try:
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:
        raise IngestionError(f"Could not open Excel file: {exc}") from exc
    visible_sheets = [ws.title for ws in workbook.worksheets if ws.sheet_state == "visible"]
    workbook.close()

    if not visible_sheets:
        raise IngestionError("Workbook has no visible sheets.")

    warnings: list[str] = []
    chosen_sheet = None
    df = None

    for sheet_name in visible_sheets:
        candidate = pd.read_excel(path, sheet_name=sheet_name)
        candidate = candidate.dropna(how="all")
        if not candidate.empty:
            chosen_sheet = sheet_name
            df = candidate
            break
        warnings.append(f"Sheet '{sheet_name}' is empty and was skipped.")

    if df is None:
        raise IngestionError("Workbook has no sheet containing data.")

    other_sheets = [s for s in visible_sheets if s != chosen_sheet]
    if other_sheets:
        warnings.append(
            f"Workbook contains additional sheet(s) not loaded: {', '.join(other_sheets)}."
        )

    return IngestionResult(
        dataframe=df.reset_index(drop=True),
        detected_format="excel",
        sheet_name=chosen_sheet,
        warnings=warnings,
    )


def _has_nested_values(df: pd.DataFrame) -> bool:
    for column in df.columns:
        series = df[column]
        if series.dtype == object and series.map(lambda v: isinstance(v, (dict, list))).any():
            return True
    return False


def _load_json(path: Path) -> IngestionResult:
    warnings: list[str] = []
    needs_flattening = False

    try:
        df = pd.read_json(path)
        if _has_nested_values(df):
            needs_flattening = True
    except ValueError:
        needs_flattening = True
        df = None

    if needs_flattening:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except RecursionError as exc:
            # json.loads is a recursive-descent parser -- extremely deeply nested
            # (adversarial or accidental) JSON can exhaust the interpreter's stack
            # before json_normalize is ever reached.
            raise IngestionError("JSON structure is too deeply nested to parse.") from exc
        if isinstance(raw, dict):
            raw = [raw]
        try:
            df = pd.json_normalize(raw)
        except Exception as exc:  # pragma: no cover - defensive
            raise IngestionError(f"Could not parse JSON structure: {exc}") from exc
        warnings.append("Nested JSON structure was flattened.")

    if df.empty:
        raise IngestionError("JSON file contains no records.")

    return IngestionResult(dataframe=df, detected_format="json", warnings=warnings)


def _load_parquet(path: Path) -> IngestionResult:
    try:
        df = pd.read_parquet(path, engine="pyarrow")
    except Exception as exc:
        raise IngestionError(f"Could not parse Parquet file: {exc}") from exc
    return IngestionResult(dataframe=df, detected_format="parquet")


def _load_feather(path: Path) -> IngestionResult:
    try:
        df = pd.read_feather(path)
    except Exception as exc:
        raise IngestionError(f"Could not parse Feather file: {exc}") from exc
    return IngestionResult(dataframe=df, detected_format="feather")


def _load_xml(path: Path) -> IngestionResult:
    try:
        df = pd.read_xml(path, parser="etree")
    except Exception as exc:
        raise IngestionError(f"Could not parse XML file: {exc}") from exc
    return IngestionResult(dataframe=df, detected_format="xml")


def load_dataset(path: Path) -> IngestionResult:
    """Load a raw dataset file into a DataFrame, auto-detecting its format.

    Read-only: never modifies the source file at `path`.
    """
    if not path.exists():
        raise IngestionError("File not found.")

    ext = path.suffix.lower()

    if ext in (".csv", ".tsv"):
        return _load_delimited_text(path, _DELIMITER_BY_EXTENSION[ext])
    if ext == ".txt":
        return _load_delimited_text(path, default_delimiter=None)
    if ext in (".xlsx", ".xls"):
        return _load_excel(path)
    if ext == ".json":
        return _load_json(path)
    if ext == ".parquet":
        return _load_parquet(path)
    if ext == ".feather":
        return _load_feather(path)
    if ext == ".xml":
        return _load_xml(path)

    # Unknown extension: never blindly guess CSV on arbitrary/binary content.
    raise IngestionError(f"Unsupported or unrecognized file type: '{ext or '(none)'}'.")
