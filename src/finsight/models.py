"""Core data structures used throughout FinSight.

This module defines lightweight, typed containers for the three central
concepts of the package:

* :class:`Transaction` -- a single dated money movement.
* :class:`RecurringPayment` -- a group of transactions that repeat on a
  regular schedule (e.g. a salary or a subscription).
* :class:`Forecast` -- a day-by-day projection of the account balance.

All classes are implemented as :func:`dataclasses.dataclass` instances so
they stay easy to read, compare and serialise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class Frequency(str, Enum):
    """Recognised repetition intervals for recurring payments.

    The value of each member is a human-readable label; the
    :attr:`days` property returns the canonical length of the interval in
    days, which is used by the forecasting engine to project future dates.
    """

    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"

    @property
    def days(self) -> int:
        """Return the nominal number of days in one interval."""
        return {
            Frequency.WEEKLY: 7,
            Frequency.BIWEEKLY: 14,
            Frequency.MONTHLY: 30,
            Frequency.QUARTERLY: 91,
            Frequency.YEARLY: 365,
        }[self]


@dataclass(frozen=True, slots=True)
class Transaction:
    """A single account transaction.

    Parameters
    ----------
    date:
        Calendar date on which the transaction was booked.
    description:
        Free-text label, typically the counter-party or merchant name.
    amount:
        Signed amount in the account currency. Positive values are
        credits (money in), negative values are debits (money out).
    category:
        Optional coarse category such as ``"groceries"`` or ``"salary"``.
    """

    date: date
    description: str
    amount: float
    category: str = "uncategorised"

    @property
    def is_income(self) -> bool:
        """``True`` if the transaction increases the balance."""
        return self.amount > 0

    @property
    def is_expense(self) -> bool:
        """``True`` if the transaction decreases the balance."""
        return self.amount < 0


@dataclass(slots=True)
class RecurringPayment:
    """A payment that repeats on a detectable, regular schedule.

    Instances are produced by
    :func:`finsight.recurring.detect_recurring_payments`.

    Parameters
    ----------
    description:
        Representative label for the payment group.
    typical_amount:
        Median signed amount across the group's transactions.
    frequency:
        Detected :class:`Frequency` of the payment.
    occurrences:
        Number of transactions that make up the group.
    first_date, last_date:
        Dates of the earliest and latest observed occurrence.
    amount_variability:
        Coefficient of variation of the amounts (0.0 means every charge is
        identical). Useful for telling fixed subscriptions apart from
        variable bills such as utilities.
    """

    description: str
    typical_amount: float
    frequency: Frequency
    occurrences: int
    first_date: date
    last_date: date
    amount_variability: float = 0.0

    @property
    def is_income(self) -> bool:
        """``True`` for recurring credits such as a salary."""
        return self.typical_amount > 0

    @property
    def monthly_impact(self) -> float:
        """Approximate effect of this payment on the balance per 30 days."""
        return self.typical_amount * (30.0 / self.frequency.days)

    def next_date_after(self, reference: date) -> date:
        """Return the next expected occurrence strictly after ``reference``."""
        from datetime import timedelta

        step = timedelta(days=self.frequency.days)
        nxt = self.last_date
        while nxt <= reference:
            nxt += step
        return nxt


@dataclass(slots=True)
class Forecast:
    """A projected balance trajectory.

    Parameters
    ----------
    dates:
        Ordered list of future dates.
    balances:
        Projected balance for each date in :attr:`dates`.
    lower, upper:
        Optional confidence band around :attr:`balances`.
    """

    dates: list[date] = field(default_factory=list)
    balances: list[float] = field(default_factory=list)
    lower: list[float] = field(default_factory=list)
    upper: list[float] = field(default_factory=list)

    @property
    def final_balance(self) -> float:
        """Projected balance on the last forecast day."""
        return self.balances[-1] if self.balances else 0.0

    @property
    def minimum_balance(self) -> float:
        """Lowest projected balance over the horizon."""
        return min(self.balances) if self.balances else 0.0

    def first_negative_date(self) -> date | None:
        """Return the first date the balance is projected to go negative."""
        for d, b in zip(self.dates, self.balances, strict=False):
            if b < 0:
                return d
        return None
