"""Tests for the balance-forecasting engine."""

from __future__ import annotations

from datetime import date, timedelta

from finsight.forecast import current_balance, forecast_balance
from finsight.models import Transaction
from finsight.recurring import detect_recurring_payments


def _series(desc, amount, start, step, count):
    return [
        Transaction(start + timedelta(days=step * i), desc, amount)
        for i in range(count)
    ]


def test_current_balance_sums_history():
    txns = [
        Transaction(date(2025, 1, 1), "A", 100.0),
        Transaction(date(2025, 1, 2), "B", -30.0),
    ]
    assert current_balance(txns, starting_balance=50.0) == 120.0


def test_forecast_has_expected_length():
    txns = _series("Salary", 2000.0, date(2025, 1, 1), 30, 6)
    recurring = detect_recurring_payments(txns)
    fc = forecast_balance(txns, recurring, horizon_days=60)
    assert len(fc.dates) == 60
    assert len(fc.balances) == 60


def test_forecast_projects_recurring_income_upward():
    txns = _series("Salary", 2000.0, date(2025, 1, 1), 30, 6)
    recurring = detect_recurring_payments(txns)
    fc = forecast_balance(
        txns, recurring, horizon_days=90, include_discretionary=False
    )
    # With only positive recurring income, the balance must not fall.
    assert fc.final_balance >= current_balance(txns)


def test_forecast_detects_negative_balance():
    # Big recurring outflow, no income, tiny starting balance.
    txns = _series("Rent", -1000.0, date(2025, 1, 1), 30, 4)
    recurring = detect_recurring_payments(txns)
    fc = forecast_balance(
        txns,
        recurring,
        horizon_days=120,
        starting_balance=500.0,
        include_discretionary=False,
    )
    assert fc.first_negative_date() is not None


def test_confidence_band_widens_over_time():
    txns = _series("Groceries", -20.0, date(2025, 1, 1), 1, 90)
    recurring = detect_recurring_payments(txns)
    fc = forecast_balance(txns, recurring, horizon_days=60)
    width_start = fc.upper[0] - fc.lower[0]
    width_end = fc.upper[-1] - fc.lower[-1]
    assert width_end >= width_start
