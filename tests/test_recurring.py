"""Tests for the recurring-payment detector."""

from __future__ import annotations

from datetime import date, timedelta

from finsight.models import Frequency, Transaction
from finsight.recurring import (
    detect_recurring_payments,
    normalise_description,
    summarise_recurring,
)


def _make_series(
    description: str,
    amount: float,
    start: date,
    step_days: int,
    count: int,
    category: str = "test",
) -> list[Transaction]:
    return [
        Transaction(
            date=start + timedelta(days=step_days * i),
            description=description,
            amount=amount,
            category=category,
        )
        for i in range(count)
    ]


def test_normalise_description_strips_digits_and_case():
    assert normalise_description("SuperMart 0453") == normalise_description(
        "supermart"
    )
    assert normalise_description("Netflix.com  #12") == "netflix com"


def test_detects_monthly_subscription():
    txns = _make_series("Streamflix", -12.99, date(2025, 1, 5), 30, 6)
    result = detect_recurring_payments(txns)
    assert len(result) == 1
    payment = result[0]
    assert payment.frequency == Frequency.MONTHLY
    assert payment.typical_amount == -12.99
    assert payment.occurrences == 6
    assert not payment.is_income


def test_detects_weekly_and_monthly_together():
    txns = _make_series("Weekly Fee", -5.0, date(2025, 1, 1), 7, 8)
    txns += _make_series("Salary", 2000.0, date(2025, 1, 27), 30, 6)
    result = detect_recurring_payments(txns)
    freqs = {r.description: r.frequency for r in result}
    assert freqs["Weekly Fee"] == Frequency.WEEKLY
    assert freqs["Salary"] == Frequency.MONTHLY


def test_ignores_too_few_occurrences():
    txns = _make_series("Rare", -10.0, date(2025, 1, 1), 30, 2)
    assert detect_recurring_payments(txns) == []


def test_ignores_irregular_intervals():
    txns = [
        Transaction(date(2025, 1, 1), "Random", -10.0),
        Transaction(date(2025, 1, 3), "Random", -10.0),
        Transaction(date(2025, 2, 20), "Random", -10.0),
        Transaction(date(2025, 3, 25), "Random", -10.0),
    ]
    assert detect_recurring_payments(txns) == []


def test_summarise_recurring_signs():
    txns = _make_series("Salary", 3000.0, date(2025, 1, 27), 30, 6)
    txns += _make_series("Rent", -900.0, date(2025, 1, 1), 30, 6)
    result = detect_recurring_payments(txns)
    summary = summarise_recurring(result)
    assert summary["monthly_income"] > 2900
    assert summary["monthly_expenses"] > 800
    assert summary["monthly_net"] > 0


def test_monthly_impact_scales_with_frequency():
    weekly = _make_series("W", -10.0, date(2025, 1, 1), 7, 10)
    result = detect_recurring_payments(weekly)
    # ~10 per week => roughly -43 per 30 days
    assert result[0].monthly_impact < -40
    assert result[0].monthly_impact > -45
