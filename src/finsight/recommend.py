"""Turn the analysis into plain-language financial recommendations.

The recommendation engine is deliberately rule-based and transparent: each
piece of advice can be traced to a concrete figure from the transaction
history. It looks at the savings rate, upcoming liquidity risk, the weight
of subscriptions, and the size of any emergency buffer, and returns a list
of prioritised, human-readable :class:`Recommendation` messages.

None of this constitutes professional financial advice; it is a
descriptive summary of the user's own numbers.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from .forecast import current_balance
from .models import Forecast, RecurringPayment, Transaction
from .recurring import summarise_recurring


class Priority(IntEnum):
    """Severity of a recommendation, highest first when sorted."""

    CRITICAL = 3
    WARNING = 2
    INFO = 1


@dataclass(slots=True)
class Recommendation:
    """A single actionable insight."""

    priority: Priority
    title: str
    detail: str

    def __str__(self) -> str:
        marker = {
            Priority.CRITICAL: "[!]",
            Priority.WARNING: "[*]",
            Priority.INFO: "[i]",
        }[self.priority]
        return f"{marker} {self.title}\n    {self.detail}"


def _months_covered(transactions: list[Transaction]) -> float:
    """Approximate number of months spanned by the history."""
    if len(transactions) < 2:
        return 1.0
    span = (transactions[-1].date - transactions[0].date).days
    return max(span / 30.4, 1.0)


def generate_recommendations(
    transactions: list[Transaction],
    recurring: list[RecurringPayment],
    forecast: Forecast,
    *,
    starting_balance: float = 0.0,
) -> list[Recommendation]:
    """Produce prioritised recommendations from the analysis.

    Parameters
    ----------
    transactions:
        The full history.
    recurring:
        Detected recurring payments.
    forecast:
        A balance forecast produced by
        :func:`finsight.forecast.forecast_balance`.
    starting_balance:
        Balance before the first historical transaction.
    """
    recs: list[Recommendation] = []
    balance = current_balance(transactions, starting_balance)
    summary = summarise_recurring(recurring)
    monthly_income = summary["monthly_income"]
    monthly_recurring_expenses = summary["monthly_expenses"]

    # --- 1. Liquidity risk from the forecast -----------------------------
    neg_date = forecast.first_negative_date()
    if neg_date is not None:
        recs.append(
            Recommendation(
                Priority.CRITICAL,
                "Projected shortfall ahead",
                f"At the current rate your balance is projected to fall "
                f"below zero around {neg_date.isoformat()}. Consider "
                f"reducing discretionary spending or moving funds in before "
                f"then.",
            )
        )
    elif forecast.minimum_balance < 0.1 * max(balance, 1.0):
        recs.append(
            Recommendation(
                Priority.WARNING,
                "Balance runs low within the horizon",
                f"Your projected balance dips to about "
                f"{forecast.minimum_balance:.2f}. Keeping a larger buffer "
                f"would reduce the risk of overdraft fees.",
            )
        )

    # --- 2. Savings rate --------------------------------------------------
    months = _months_covered(transactions)
    total_income = sum(t.amount for t in transactions if t.amount > 0)
    total_spent = -sum(t.amount for t in transactions if t.amount < 0)
    if total_income > 0:
        savings_rate = (total_income - total_spent) / total_income
        pct = savings_rate * 100
        avg_monthly_savings = (total_income - total_spent) / months
        if savings_rate < 0:
            recs.append(
                Recommendation(
                    Priority.CRITICAL,
                    "Spending exceeds income",
                    f"Over the last {months:.0f} months you spent about "
                    f"{-avg_monthly_savings:.2f} more per month than you "
                    f"earned. This trend is not sustainable; review the "
                    f"largest expense categories first.",
                )
            )
        elif savings_rate < 0.10:
            recs.append(
                Recommendation(
                    Priority.WARNING,
                    "Low savings rate",
                    f"You are saving roughly {pct:.0f}% of your income "
                    f"(~{avg_monthly_savings:.2f}/month). A common target is "
                    f"15-20%. Automating a fixed monthly transfer to savings "
                    f"can help.",
                )
            )
        else:
            recs.append(
                Recommendation(
                    Priority.INFO,
                    "Healthy savings rate",
                    f"You are saving about {pct:.0f}% of your income "
                    f"(~{avg_monthly_savings:.2f}/month). If this sits idle "
                    f"in a current account, consider a higher-interest "
                    f"savings account or a low-cost index fund.",
                )
            )

    # --- 3. Emergency fund ------------------------------------------------
    monthly_outflow = total_spent / months
    if monthly_outflow > 0:
        months_of_cover = balance / monthly_outflow
        if months_of_cover < 3:
            recs.append(
                Recommendation(
                    Priority.WARNING,
                    "Thin emergency buffer",
                    f"Your balance covers about {months_of_cover:.1f} months "
                    f"of spending. A widely used rule of thumb is 3-6 months. "
                    f"Building toward "
                    f"{3 * monthly_outflow:.0f} would give more resilience.",
                )
            )
        else:
            recs.append(
                Recommendation(
                    Priority.INFO,
                    "Solid emergency buffer",
                    f"Your balance covers roughly {months_of_cover:.1f} "
                    f"months of spending, which is a comfortable cushion.",
                )
            )

    # --- 4. Subscription weight ------------------------------------------
    subscriptions = [
        p
        for p in recurring
        if not p.is_income
        and p.amount_variability < 0.05
        and abs(p.monthly_impact) < 100
    ]
    sub_total = -sum(p.monthly_impact for p in subscriptions)
    if monthly_income > 0 and sub_total > 0.08 * monthly_income:
        names = ", ".join(sorted(p.description for p in subscriptions)[:5])
        recs.append(
            Recommendation(
                Priority.INFO,
                "Subscriptions add up",
                f"Fixed subscriptions cost about {sub_total:.2f}/month "
                f"({sub_total / monthly_income * 100:.0f}% of income): "
                f"{names}. Reviewing rarely used ones is an easy saving.",
            )
        )

    # --- 5. Recurring overview -------------------------------------------
    if recurring:
        recs.append(
            Recommendation(
                Priority.INFO,
                "Recurring cash flow summary",
                f"Detected recurring income of "
                f"{monthly_income:.2f}/month and recurring expenses of "
                f"{monthly_recurring_expenses:.2f}/month, leaving "
                f"{summary['monthly_net']:.2f}/month before discretionary "
                f"spending.",
            )
        )

    recs.sort(key=lambda r: r.priority, reverse=True)
    return recs
