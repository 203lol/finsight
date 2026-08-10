"""Detect recurring payments in a transaction history.

The detector groups transactions by a normalised description and then
inspects each group for a regular time interval between charges of a
similar amount. Groups that repeat at a recognised :class:`Frequency`
(weekly, biweekly, monthly, quarterly or yearly) with enough occurrences
are reported as :class:`~finsight.models.RecurringPayment` objects.
"""

from __future__ import annotations

import re
import statistics
from collections import defaultdict

from .models import Frequency, RecurringPayment, Transaction

# Nominal interval length in days -> Frequency, with an accepted tolerance.
_FREQUENCY_TABLE: list[tuple[Frequency, float, float]] = [
    (Frequency.WEEKLY, 7.0, 2.0),
    (Frequency.BIWEEKLY, 14.0, 3.0),
    (Frequency.MONTHLY, 30.4, 5.0),
    (Frequency.QUARTERLY, 91.3, 12.0),
    (Frequency.YEARLY, 365.0, 25.0),
]

_NORMALISE_RE = re.compile(r"[^a-z]+")


def normalise_description(description: str) -> str:
    """Reduce a description to a stable merchant key.

    Digits, punctuation and casing are stripped so that labels like
    ``"SuperMart Groceries 0453"`` and ``"SUPERMART GROCERIES"`` collapse
    to the same key.
    """
    lowered = description.lower()
    collapsed = _NORMALISE_RE.sub(" ", lowered).strip()
    return collapsed or lowered.strip()


def _classify_interval(median_interval: float) -> Frequency | None:
    """Return the :class:`Frequency` matching an interval, or ``None``."""
    for freq, nominal, tol in _FREQUENCY_TABLE:
        if abs(median_interval - nominal) <= tol:
            return freq
    return None


def _coefficient_of_variation(values: list[float]) -> float:
    """Return |std / mean|, or 0.0 when the mean is (near) zero."""
    if len(values) < 2:
        return 0.0
    mean = statistics.fmean(values)
    if abs(mean) < 1e-9:
        return 0.0
    return statistics.pstdev(values) / abs(mean)


def detect_recurring_payments(
    transactions: list[Transaction],
    *,
    min_occurrences: int = 3,
    amount_tolerance: float = 0.25,
    interval_tolerance: float = 0.35,
) -> list[RecurringPayment]:
    """Identify recurring payments within ``transactions``.

    Parameters
    ----------
    transactions:
        The full transaction history.
    min_occurrences:
        Minimum number of charges required before a group is considered
        recurring.
    amount_tolerance:
        Maximum allowed coefficient of variation of the amounts within a
        group. Larger values admit variable bills (e.g. utilities);
        smaller values restrict detection to fixed subscriptions.
    interval_tolerance:
        Maximum allowed coefficient of variation of the intervals between
        consecutive charges. Controls how strict the schedule must be.

    Returns
    -------
    list of :class:`~finsight.models.RecurringPayment`
        Sorted by absolute monthly impact, largest first.
    """
    groups: dict[str, list[Transaction]] = defaultdict(list)
    for txn in transactions:
        groups[normalise_description(txn.description)].append(txn)

    found: list[RecurringPayment] = []
    for txns in groups.values():
        if len(txns) < min_occurrences:
            continue

        txns = sorted(txns, key=lambda t: t.date)
        amounts = [t.amount for t in txns]

        # Amounts must be consistent enough (and share a sign).
        if not (all(a > 0 for a in amounts) or all(a < 0 for a in amounts)):
            continue
        amount_cv = _coefficient_of_variation(amounts)
        if amount_cv > amount_tolerance:
            continue

        # Intervals between consecutive charges must be regular.
        intervals = [
            (txns[i + 1].date - txns[i].date).days
            for i in range(len(txns) - 1)
        ]
        intervals = [i for i in intervals if i > 0]
        if len(intervals) < min_occurrences - 1:
            continue

        median_interval = statistics.median(intervals)
        if _coefficient_of_variation(
            [float(i) for i in intervals]
        ) > interval_tolerance:
            continue

        frequency = _classify_interval(median_interval)
        if frequency is None:
            continue

        # Use the most common human-readable label as the display name.
        label = max(
            (t.description for t in txns),
            key=lambda d: sum(1 for t in txns if t.description == d),
        )

        found.append(
            RecurringPayment(
                description=label,
                typical_amount=round(statistics.median(amounts), 2),
                frequency=frequency,
                occurrences=len(txns),
                first_date=txns[0].date,
                last_date=txns[-1].date,
                amount_variability=round(amount_cv, 3),
            )
        )

    found.sort(key=lambda r: abs(r.monthly_impact), reverse=True)
    return found


def summarise_recurring(payments: list[RecurringPayment]) -> dict[str, float]:
    """Aggregate recurring payments into monthly income / expense totals.

    Returns
    -------
    dict
        Keys ``"monthly_income"``, ``"monthly_expenses"`` (a positive
        number) and ``"monthly_net"``.
    """
    income = sum(p.monthly_impact for p in payments if p.is_income)
    expenses = -sum(p.monthly_impact for p in payments if not p.is_income)
    return {
        "monthly_income": round(income, 2),
        "monthly_expenses": round(expenses, 2),
        "monthly_net": round(income - expenses, 2),
    }
