"""High-level orchestration tying the pipeline together.

:func:`analyse` runs the whole FinSight pipeline -- detection, forecasting
and recommendations -- and returns a single :class:`AnalysisResult` bundle.
This is the most convenient entry point for programmatic use::

    from finsight import load_transactions, analyse

    txns = load_transactions("data/transactions_sample.csv")
    result = analyse(txns, horizon_days=90)
    print(result.report())
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .forecast import current_balance, forecast_balance
from .models import Forecast, RecurringPayment, Transaction
from .recommend import Recommendation, generate_recommendations
from .recurring import detect_recurring_payments, summarise_recurring


@dataclass(slots=True)
class AnalysisResult:
    """Bundle of every artefact produced by :func:`analyse`."""

    transactions: list[Transaction]
    recurring: list[RecurringPayment]
    forecast: Forecast
    recommendations: list[Recommendation]
    starting_balance: float = 0.0
    _summary: dict[str, float] = field(default_factory=dict)

    @property
    def current_balance(self) -> float:
        """Balance implied by the history."""
        return current_balance(self.transactions, self.starting_balance)

    def report(self) -> str:
        """Render a plain-text report of the analysis."""
        lines: list[str] = []
        lines.append("=" * 64)
        lines.append("  FinSight -- Financial Analysis Report")
        lines.append("=" * 64)

        if self.transactions:
            first = self.transactions[0].date
            last = self.transactions[-1].date
            lines.append(
                f"Period analysed : {first.isoformat()} to {last.isoformat()}"
            )
        lines.append(f"Transactions    : {len(self.transactions)}")
        lines.append(f"Current balance : {self.current_balance:,.2f}")
        lines.append("")

        lines.append("-" * 64)
        lines.append("Recurring payments")
        lines.append("-" * 64)
        if self.recurring:
            for p in self.recurring:
                kind = "income " if p.is_income else "expense"
                lines.append(
                    f"  {p.description:<32.32} {p.frequency.value:<9} "
                    f"{kind} {p.typical_amount:>10.2f}  "
                    f"(x{p.occurrences})"
                )
            s = summarise_recurring(self.recurring)
            lines.append("")
            lines.append(
                f"  Monthly recurring income  : {s['monthly_income']:>10.2f}"
            )
            lines.append(
                f"  Monthly recurring expenses: {s['monthly_expenses']:>10.2f}"
            )
            lines.append(
                f"  Monthly recurring net     : {s['monthly_net']:>10.2f}"
            )
        else:
            lines.append("  (none detected)")
        lines.append("")

        lines.append("-" * 64)
        lines.append("Balance forecast")
        lines.append("-" * 64)
        if self.forecast.dates:
            lines.append(
                f"  Horizon end  : {self.forecast.dates[-1].isoformat()}"
            )
            lines.append(
                f"  Final balance: {self.forecast.final_balance:,.2f}"
            )
            lines.append(
                f"  Lowest point : {self.forecast.minimum_balance:,.2f}"
            )
            neg = self.forecast.first_negative_date()
            if neg:
                lines.append(f"  First negative: {neg.isoformat()}")
        lines.append("")

        lines.append("-" * 64)
        lines.append("Recommendations")
        lines.append("-" * 64)
        if self.recommendations:
            for rec in self.recommendations:
                lines.append(str(rec))
        else:
            lines.append("  (no recommendations)")
        lines.append("")
        lines.append(
            "Note: this is a descriptive summary of your own figures, "
            "not professional financial advice."
        )
        return "\n".join(lines)


def analyse(
    transactions: list[Transaction],
    *,
    horizon_days: int = 90,
    starting_balance: float = 0.0,
    min_occurrences: int = 3,
) -> AnalysisResult:
    """Run the full FinSight pipeline on a transaction history.

    Parameters
    ----------
    transactions:
        The history to analyse.
    horizon_days:
        How many days ahead to forecast.
    starting_balance:
        Balance before the first historical transaction.
    min_occurrences:
        Minimum repetitions before a payment counts as recurring.

    Returns
    -------
    :class:`AnalysisResult`
    """
    recurring = detect_recurring_payments(
        transactions, min_occurrences=min_occurrences
    )
    forecast = forecast_balance(
        transactions,
        recurring,
        horizon_days=horizon_days,
        starting_balance=starting_balance,
    )
    recommendations = generate_recommendations(
        transactions,
        recurring,
        forecast,
        starting_balance=starting_balance,
    )
    return AnalysisResult(
        transactions=transactions,
        recurring=recurring,
        forecast=forecast,
        recommendations=recommendations,
        starting_balance=starting_balance,
    )
