"""Load transaction histories from CSV files.

The loader is intentionally forgiving about column names and date formats
so that exports from different banks can be used with minimal editing. A
CSV needs at least a *date*, a *description* and an *amount* column; a
*category* column is optional.
"""

from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path

from .models import Transaction

# Accepted header spellings, mapped to the canonical field name.
_COLUMN_ALIASES: dict[str, str] = {
    "date": "date",
    "booking date": "date",
    "buchungstag": "date",
    "value date": "date",
    "description": "description",
    "text": "description",
    "payee": "description",
    "merchant": "description",
    "verwendungszweck": "description",
    "amount": "amount",
    "betrag": "amount",
    "value": "amount",
    "category": "category",
    "kategorie": "category",
    # Optional direction column: when present it decides the sign of the
    # amount (credit -> positive, debit -> negative). This lets FinSight
    # read exports that store unsigned amounts alongside a type flag.
    "type": "direction",
    "transaction type": "direction",
    "direction": "direction",
    "dr/cr": "direction",
    "debit/credit": "direction",
    "soll/haben": "direction",
}

# Direction labels understood in a "type" column.
_CREDIT_LABELS = {"credit", "cr", "c", "haben", "deposit", "in", "income"}
_DEBIT_LABELS = {"debit", "dr", "d", "soll", "withdrawal", "out", "expense"}

# Date formats tried in order.
_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d.%m.%Y",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%Y/%m/%d",
)


def _parse_date(raw: str) -> date:
    """Parse a date string using several common formats."""
    raw = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognised date format: {raw!r}")


def _parse_amount(raw: str) -> float:
    """Parse a monetary amount, tolerating thousands separators.

    Handles both ``1,234.56`` (English) and ``1.234,56`` (German) styles.
    """
    raw = raw.strip().replace(" ", "").replace("\u00a0", "")
    if "," in raw and "." in raw:
        # Whichever separator comes last is the decimal separator.
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        # Assume comma is the decimal separator (German style).
        raw = raw.replace(",", ".")
    return float(raw)


def _apply_direction(amount: float, direction: str) -> float:
    """Return a signed amount given a credit/debit direction label.

    Credits become positive, debits become negative, regardless of the
    sign the amount was stored with. An unrecognised label is treated as a
    debit (the common case in bank exports) but raises no error.
    """
    label = direction.strip().lower()
    if label in _CREDIT_LABELS:
        return abs(amount)
    if label in _DEBIT_LABELS:
        return -abs(amount)
    # Fall back to the amount as given if the label is unknown.
    return amount


def _resolve_headers(fieldnames: list[str]) -> dict[str, str]:
    """Map the CSV's own headers onto canonical field names."""
    resolved: dict[str, str] = {}
    for name in fieldnames:
        canonical = _COLUMN_ALIASES.get(name.strip().lower())
        if canonical:
            resolved[canonical] = name
    missing = {"date", "description", "amount"} - resolved.keys()
    if missing:
        raise ValueError(
            "CSV is missing required column(s): "
            + ", ".join(sorted(missing))
            + f". Found headers: {fieldnames}"
        )
    return resolved


def load_transactions(path: str | Path) -> list[Transaction]:
    """Read a CSV file and return a date-sorted list of transactions.

    Parameters
    ----------
    path:
        Path to a CSV file with (at least) date, description and amount
        columns. Column names are matched case-insensitively against a set
        of common aliases.

    Returns
    -------
    list of :class:`~finsight.models.Transaction`
        Sorted ascending by date.

    Raises
    ------
    FileNotFoundError
        If ``path`` does not exist.
    ValueError
        If required columns are missing or a row cannot be parsed.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No such file: {path}")

    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError("CSV file appears to be empty.")
        cols = _resolve_headers(reader.fieldnames)

        transactions: list[Transaction] = []
        for lineno, row in enumerate(reader, start=2):
            try:
                amount = _parse_amount(row[cols["amount"]])
                if "direction" in cols and row.get(cols["direction"]):
                    amount = _apply_direction(amount, row[cols["direction"]])
                txn = Transaction(
                    date=_parse_date(row[cols["date"]]),
                    description=row[cols["description"]].strip(),
                    amount=amount,
                    category=(
                        row[cols["category"]].strip()
                        if "category" in cols and row.get(cols["category"])
                        else "uncategorised"
                    ),
                )
            except (ValueError, KeyError) as exc:
                raise ValueError(
                    f"Error parsing line {lineno}: {exc}"
                ) from exc
            transactions.append(txn)

    transactions.sort(key=lambda t: t.date)
    return transactions
