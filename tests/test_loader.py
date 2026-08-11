"""Tests for the CSV loader and the end-to-end pipeline."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from finsight import analyse, load_transactions
from finsight.datagen import write_sample_csv
from finsight.loader import _apply_direction, _parse_amount, _parse_date


def test_parse_date_multiple_formats():
    assert _parse_date("2025-03-14") == date(2025, 3, 14)
    assert _parse_date("14.03.2025") == date(2025, 3, 14)
    assert _parse_date("03/14/2025") == date(2025, 3, 14)


def test_parse_date_day_month_year():
    # European DD/MM/YYYY must not be read as MM/DD.
    assert _parse_date("04/01/2024") == date(2024, 1, 4)
    assert _parse_date("31/01/2024") == date(2024, 1, 31)


def test_apply_direction_signs():
    assert _apply_direction(12.99, "debit") == -12.99
    assert _apply_direction(12.99, "credit") == 12.99
    # Unsigned amount stays negative for a debit even if given positive.
    assert _apply_direction(-5.0, "credit") == 5.0


def test_type_column_sets_sign(tmp_path):
    csv_path = tmp_path / "typed.csv"
    csv_path.write_text(
        "date,description,amount,type,category\n"
        "01/01/2024,Salary,2500.0,credit,salary\n"
        "01/01/2024,Netflix,12.99,debit,subscription\n"
        "03/01/2024,Rent,650.0,debit,rent\n",
        encoding="utf-8",
    )
    txns = load_transactions(csv_path)
    by_desc = {t.description: t.amount for t in txns}
    assert by_desc["Salary"] == 2500.0
    assert by_desc["Netflix"] == -12.99
    assert by_desc["Rent"] == -650.0


def test_parse_amount_handles_separators():
    assert _parse_amount("1,234.56") == pytest.approx(1234.56)
    assert _parse_amount("1.234,56") == pytest.approx(1234.56)
    assert _parse_amount("-42,00") == pytest.approx(-42.00)


def test_load_and_analyse_roundtrip(tmp_path):
    csv_path = tmp_path / "sample.csv"
    write_sample_csv(csv_path, months=12, seed=1)

    txns = load_transactions(csv_path)
    assert len(txns) > 50
    # Sorted ascending by date.
    assert txns == sorted(txns, key=lambda t: t.date)

    result = analyse(txns, horizon_days=60)
    # The sample data contains an obvious monthly salary and rent.
    descriptions = {r.description for r in result.recurring}
    assert any("Salary" in d for d in descriptions)
    assert result.forecast.dates  # forecast produced
    assert result.recommendations  # at least one recommendation
    assert "FinSight" in result.report()


def test_bundled_dataset_loads_and_analyses():
    # The real dataset shipped with the project should load cleanly, apply
    # credit/debit signs, and yield the expected recurring structure.
    dataset = Path(__file__).resolve().parent.parent / (
        "data/sample_transactions.csv"
    )
    if not dataset.exists():
        pytest.skip("bundled dataset not present")
    txns = load_transactions(dataset)
    assert len(txns) > 400
    # Debits must be negative, credits positive.
    salary = [t for t in txns if t.description == "Salary Credit"]
    rent = [t for t in txns if t.description == "Rent Payment"]
    assert salary and all(t.amount > 0 for t in salary)
    assert rent and all(t.amount < 0 for t in rent)

    result = analyse(txns, horizon_days=90, starting_balance=1000)
    descriptions = {r.description for r in result.recurring}
    assert "Salary Credit" in descriptions
    assert "Rent Payment" in descriptions
    assert "Netflix Subscription" in descriptions


def test_missing_column_raises(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("foo,bar\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_transactions(bad)


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_transactions(tmp_path / "does_not_exist.csv")


def test_empty_csv_returns_empty_list(tmp_path):
    # A CSV with only a header row (no transactions) should load as an
    # empty list, not raise an error.
    csv_path = tmp_path / "empty.csv"
    csv_path.write_text(
        "date,description,amount,type,category\n", encoding="utf-8"
    )
    assert load_transactions(csv_path) == []


def test_single_transaction(tmp_path):
    # A CSV with exactly one row should load that one transaction.
    csv_path = tmp_path / "single.csv"
    csv_path.write_text(
        "date,description,amount,type,category\n"
        "15/03/2024,Coffee Shop,4.50,debit,dining\n",
        encoding="utf-8",
    )
    txns = load_transactions(csv_path)
    assert len(txns) == 1
    assert txns[0].description == "Coffee Shop"
    assert txns[0].amount == -4.50  # debit -> negative


def test_iso_date_format(tmp_path):
    # The loader should also accept ISO (YYYY-MM-DD) dates, not just DD/MM.
    csv_path = tmp_path / "iso.csv"
    csv_path.write_text(
        "date,description,amount,type,category\n"
        "2024-03-15,Coffee Shop,4.50,debit,dining\n",
        encoding="utf-8",
    )
    txns = load_transactions(csv_path)
    assert txns[0].date == date(2024, 3, 15)


def test_transactions_sorted_by_date(tmp_path):
    # Rows given out of order should come back sorted ascending by date.
    csv_path = tmp_path / "unordered.csv"
    csv_path.write_text(
        "date,description,amount,type,category\n"
        "20/03/2024,Later,10.00,debit,other\n"
        "05/03/2024,Earlier,10.00,debit,other\n",
        encoding="utf-8",
    )
    txns = load_transactions(csv_path)
    assert txns[0].description == "Earlier"
    assert txns[1].description == "Later"
