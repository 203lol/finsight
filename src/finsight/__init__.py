"""FinSight -- a small financial-analysis toolkit.

FinSight reads a history of bank transactions and:

1. **detects recurring payments** (salary, rent, subscriptions, ...),
2. **forecasts the future account balance**, and
3. **generates plain-language recommendations** for saving and spending.

The most convenient entry points are re-exported here so that users can
write::

    from finsight import load_transactions, analyse

    txns = load_transactions("transactions.csv")
    result = analyse(txns, horizon_days=90)
    print(result.report())

See the individual sub-modules for lower-level building blocks.
"""

from __future__ import annotations

from .analysis import AnalysisResult, analyse
from .datagen import generate_transactions, write_sample_csv
from .forecast import current_balance, forecast_balance
from .loader import load_transactions
from .models import (
    Forecast,
    Frequency,
    RecurringPayment,
    Transaction,
)
from .recommend import Priority, Recommendation, generate_recommendations
from .recurring import (
    detect_recurring_payments,
    summarise_recurring,
)

__version__ = "1.0.0"

__all__ = [
    "__version__",
    # high-level
    "analyse",
    "AnalysisResult",
    # io
    "load_transactions",
    "generate_transactions",
    "write_sample_csv",
    # models
    "Transaction",
    "RecurringPayment",
    "Forecast",
    "Frequency",
    # engines
    "detect_recurring_payments",
    "summarise_recurring",
    "forecast_balance",
    "current_balance",
    "generate_recommendations",
    "Recommendation",
    "Priority",
]
