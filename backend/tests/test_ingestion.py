import json
from pathlib import Path

import openpyxl
import pandas as pd
import pytest

from app.services.ingestion import IngestionError, load_dataset


# --- CSV ---------------------------------------------------------------------


def test_csv_with_bom_strips_bom_and_parses_headers(tmp_path: Path):
    path = tmp_path / "bom.csv"
    path.write_bytes(b"\xef\xbb\xbfid,name\n1,Alice\n2,Bob\n")

    result = load_dataset(path)

    assert list(result.dataframe.columns) == ["id", "name"]
    assert result.encoding == "utf-8-sig"
    assert len(result.dataframe) == 2


def test_csv_embedded_comma_in_quoted_field_preserved(tmp_path: Path):
    path = tmp_path / "quoted.csv"
    path.write_text('id,address\n1,"123 Main St, Apt 4"\n2,"456 Oak Ave"\n', encoding="utf-8")

    result = load_dataset(path)

    assert result.dataframe.loc[0, "address"] == "123 Main St, Apt 4"
    assert len(result.dataframe) == 2


def test_csv_malformed_row_skipped_with_warning(tmp_path: Path):
    # A row with MORE fields than the header is genuinely ambiguous to the C parser
    # and raises ParserError (a row with fewer fields is just padded with NaN, which
    # is not an error case).
    path = tmp_path / "malformed.csv"
    path.write_text("a,b,c\n1,2,3\n4,5,6,7\n8,9,10\n", encoding="utf-8")

    result = load_dataset(path)

    assert len(result.dataframe) == 2
    assert any("malformed" in w.lower() for w in result.warnings)


def test_tsv_parsed_with_tab_delimiter(tmp_path: Path):
    path = tmp_path / "sample.tsv"
    path.write_text("id\tname\n1\tAlice\n2\tBob\n", encoding="utf-8")

    result = load_dataset(path)

    assert result.delimiter == "\t"
    assert list(result.dataframe.columns) == ["id", "name"]
    assert len(result.dataframe) == 2


def test_txt_file_with_semicolon_delimiter_is_sniffed(tmp_path: Path):
    path = tmp_path / "sample.txt"
    path.write_text("id;name;amount\n1;Alice;100\n2;Bob;200\n3;Carl;300\n", encoding="utf-8")

    result = load_dataset(path)

    assert result.delimiter == ";"
    assert list(result.dataframe.columns) == ["id", "name", "amount"]
    assert len(result.dataframe) == 3


# --- Excel ---------------------------------------------------------------------


def test_excel_skips_hidden_and_empty_sheets(tmp_path: Path):
    path = tmp_path / "workbook.xlsx"
    wb = openpyxl.Workbook()

    data_sheet = wb.active
    data_sheet.title = "Data"
    data_sheet.append(["id", "name"])
    data_sheet.append([1, "Alice"])
    data_sheet.append([2, "Bob"])

    hidden_sheet = wb.create_sheet("Hidden")
    hidden_sheet.sheet_state = "hidden"
    hidden_sheet.append(["secret"])
    hidden_sheet.append(["shhh"])

    empty_sheet = wb.create_sheet("Empty")
    # left with no rows

    wb.save(path)

    result = load_dataset(path)

    assert result.sheet_name == "Data"
    assert list(result.dataframe.columns) == ["id", "name"]
    assert len(result.dataframe) == 2
    assert any("Empty" in w for w in result.warnings)  # empty sheet is noted, not silently dropped


# --- JSON ---------------------------------------------------------------------


def test_json_flat_list_of_records(tmp_path: Path):
    path = tmp_path / "flat.json"
    path.write_text(json.dumps([{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]), encoding="utf-8")

    result = load_dataset(path)

    assert list(result.dataframe.columns) == ["id", "name"]
    assert len(result.dataframe) == 2
    assert not result.warnings


def test_json_nested_object_is_flattened(tmp_path: Path):
    path = tmp_path / "nested.json"
    data = [
        {"id": 1, "customer": {"name": "Alice", "region": "West"}},
        {"id": 2, "customer": {"name": "Bob", "region": "East"}},
    ]
    path.write_text(json.dumps(data), encoding="utf-8")

    result = load_dataset(path)

    assert "customer.name" in result.dataframe.columns
    assert "customer.region" in result.dataframe.columns
    assert len(result.dataframe) == 2
    assert any("flattened" in w.lower() for w in result.warnings)


# --- Parquet / Feather ---------------------------------------------------------


def test_parquet_roundtrip_preserves_dtypes(tmp_path: Path):
    path = tmp_path / "sample.parquet"
    original = pd.DataFrame({"id": [1, 2, 3], "amount": [10.5, 20.25, 30.0]})
    original.to_parquet(path, engine="pyarrow")

    result = load_dataset(path)

    assert list(result.dataframe.columns) == ["id", "amount"]
    assert result.dataframe["amount"].tolist() == [10.5, 20.25, 30.0]
    assert len(result.dataframe) == 3


def test_feather_roundtrip(tmp_path: Path):
    path = tmp_path / "sample.feather"
    original = pd.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]})
    original.to_feather(path)

    result = load_dataset(path)

    assert list(result.dataframe.columns) == ["id", "name"]
    assert len(result.dataframe) == 2


# --- XML -----------------------------------------------------------------------


def test_xml_parsed_correctly(tmp_path: Path):
    path = tmp_path / "sample.xml"
    path.write_text(
        "<root><row><id>1</id><name>Alice</name></row>"
        "<row><id>2</id><name>Bob</name></row></root>",
        encoding="utf-8",
    )

    result = load_dataset(path)

    assert list(result.dataframe.columns) == ["id", "name"]
    assert len(result.dataframe) == 2


# --- Encoding/robustness -------------------------------------------------------


def test_undecodable_bytes_raise_friendly_ingestion_error_not_raw_crash(tmp_path: Path, monkeypatch):
    # Force chardet to confidently misreport an encoding that cannot actually decode
    # the bytes, simulating a low-confidence wrong guess -- must degrade to a friendly
    # IngestionError, not an unhandled UnicodeDecodeError.
    path = tmp_path / "bad_encoding.csv"
    path.write_bytes(b"id,name\n1,\xff\xfe\x00\x01invalid\n")

    import app.services.ingestion as ingestion_module

    monkeypatch.setattr(ingestion_module.chardet, "detect", lambda _: {"encoding": "ascii", "confidence": 0.1})

    with pytest.raises(IngestionError):
        load_dataset(path)


def test_deeply_nested_json_raises_friendly_error_not_recursion_error(tmp_path: Path):
    path = tmp_path / "deep.json"
    # Deep enough to blow Python's default recursion limit inside json.loads.
    nested = "[" * 5000 + "]" * 5000
    path.write_text(nested, encoding="utf-8")

    with pytest.raises(IngestionError):
        load_dataset(path)


# --- Unsupported ----------------------------------------------------------------


def test_unsupported_extension_raises_friendly_error(tmp_path: Path):
    path = tmp_path / "document.docx"
    path.write_bytes(b"not a real docx file, just binary junk \x00\x01\x02")

    with pytest.raises(IngestionError):
        load_dataset(path)


def test_missing_file_raises_friendly_error(tmp_path: Path):
    with pytest.raises(IngestionError):
        load_dataset(tmp_path / "does_not_exist.csv")
