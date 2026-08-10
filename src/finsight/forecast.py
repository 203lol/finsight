"""Project the future account balance.

The forecast combines two components:

1. **Scheduled cash flows** -- every detected
   :class:`~finsight.models.RecurringPayment` is projected forward onto its
   expected future dates.
2. **Discretionary spending** -- irregular, non-recurring transactions are
   modelled as a constant average daily drain, estimated from the recent
   history. Its day-to-day variability is used to build a simple
   confidence band around the projection.

The result is a :class:`~finsight.models.Forecast` giving the balance for
each day over the requested horizon.
"""

from __future__ import annotations

import math
import statistics
from datetime import date, timedelta

from .models import Forecast, RecurringPayment, Transaction
from .recurring import normalise_description


def current_balance(
    transactions: list[Transaction],
    starting_balance: float = 0.0,
) -> float:
    """Return the balance implied by summing the history.

    Parameters
    ----------
    transactions:
        The full history.
    starting_balance:
        Balance immediately before the first transaction.
    """
    return round(starting_balance + sum(t.amount for t in transactions), 2)


def _discretionary_daily_stats(
    transactions: list[Transaction],
    recurring: list[RecurringPayment],
    lookback_days: int = 90,
) -> tuple[float, float]:
    """Estimate mean and standard deviation of daily discretionary spend.

    Discretionary spending is everything that is *not* part of a detected
    recurring payment, measured over the most recent ``lookback_days``.
    """
    if not transactions:
        return 0.0, 0.0

    recurring_keys = {normalise_description(r.description) for r in recurring}
    last_day = max(t.date for t in transactions)
    window_start = last_day - timedelta(days=lookback_days)

    daily_totals: dict[date, float] = {}
    for txn in transactions:
        if txn.date < window_start:
            continue
        if txn.amount >= 0:
            continue  # income handled by the recurring model
        if normalise_description(txn.description) in recurring_keys:
            continue
        daily_totals[txn.date] = daily_totals.get(txn.date, 0.0) + txn.amount

    # Fill in zero-spend days so the average is not overstated.
    span = (last_day - window_start).days or 1
    totals = list(daily_totals.values()) + [0.0] * (span - len(daily_totals))
    if not totals:
        return 0.0, 0.0

    mean = statistics.fmean(totals)
    std = statistics.pstdev(totals) if len(totals) > 1 else 0.0
    return mean, std


def forecast_balance(
    transactions: list[Transaction],
    recurring: list[RecurringPayment],
    *,
    horizon_days: int = 90,
    starting_balance: float = 0.0,
    include_discretionary: bool = True,
) -> Forecast:
    """Project the balance forward day by day.

    Parameters
    ----------
    transactions:
        The full history, used to anchor the current balance and to
        estimate discretionary spending.
    recurring:
        Detected recurring payments to project forward.
    horizon_days:
        Number of days to forecast.
    starting_balance:
        Balance before the first historical transaction.
    include_discretionary:
        If ``True``, add modelled irregular spending on top of the
        scheduled cash flows.

    Returns
    -------
    :class:`~finsight.models.Forecast`
    """
    balance = current_balance(transactions, starting_balance)
    start_day = (
        max(t.date for t in transactions) if transactions else date.today()
    )

    daily_mean, daily_std = (
        _discretionary_daily_stats(transactions, recurring)
        if include_discretionary
        else (0.0, 0.0)
    )

    forecast = Forecast()
    running = balance
    variance = 0.0

    for offset in range(1, horizon_days + 1):
        day = start_day + timedelta(days=offset)

        # Scheduled recurring cash flows landing on this day.
        for payment in recurring:
            step = payment.frequency.days
            days_since_last = (day - payment.last_date).days
            if days_since_last > 0 and days_since_last % step == 0:
                running += payment.typical_amount

        # Modelled discretionary spend.
        running += daily_mean
        variance += daily_std**2

        band = 1.96 * math.sqrt(variance)  # ~95% confidence
        forecast.dates.append(day)
        forecast.balances.append(round(running, 2))
        forecast.lower.append(round(running - band, 2))
        forecast.upper.append(round(running + band, 2))

    return forecast
