"""Generate realistic synthetic transaction histories.

Because real bank statements are private, FinSight ships with a
deterministic generator so that the tool can be demonstrated and tested
without any personal data. The generated history mixes:

* regular income (a monthly salary),
* fixed recurring subscriptions (streaming, gym, phone, ...),
* a variable recurring bill (electricity),
* and irregular day-to-day spending (groceries, restaurants, shopping).

The output is written as a CSV file compatible with
:func:`finsight.loader.load_transactions`.
"""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

# (description, monthly amount, category, day-of-month) for fixed items.
_FIXED_RECURRING = [
    ("Salary Employer GmbH", 2600.0, "salary", 27),
    ("Rent Landlord", -780.0, "housing", 1),
    ("Streamflix Subscription", -12.99, "entertainment", 5),
    ("SoundWave Music", -9.99, "entertainment", 8),
    ("FitLife Gym", -29.90, "health", 3),
    ("TeleConnect Mobile", -19.99, "utilities", 15),
    ("CloudStore Plus", -2.99, "utilities", 12),
    ("InsureCo Health Top-up", -84.50, "insurance", 20),
]

# Irregular spending drawn at random throughout each month.
_IRREGULAR = [
    ("SuperMart Groceries", (-15.0, -70.0), "groceries", 0.9),
    ("Corner Bakery", (-2.5, -9.0), "groceries", 0.5),
    ("Bella Italia Restaurant", (-18.0, -55.0), "dining", 0.35),
    ("QuickCab Ride", (-6.0, -24.0), "transport", 0.3),
    ("StyleHub Clothing", (-25.0, -120.0), "shopping", 0.15),
    ("BookNook", (-8.0, -35.0), "shopping", 0.12),
    ("PharmaPlus", (-5.0, -40.0), "health", 0.15),
]


def _month_range(start: date, months: int) -> list[date]:
    """Yield the first day of each month in the range."""
    result = []
    year, month = start.year, start.month
    for _ in range(months):
        result.append(date(year, month, 1))
        month += 1
        if month > 12:
            month = 1
            year += 1
    return result


def generate_transactions(
    months: int = 12,
    end: date | None = None,
    seed: int = 42,
) -> list[tuple[date, str, float, str]]:
    """Create a synthetic transaction list.

    Parameters
    ----------
    months:
        Number of whole months of history to generate.
    end:
        Last month to include (defaults to the current month).
    seed:
        Random seed, so the data is reproducible.

    Returns
    -------
    list of tuples
        Rows of ``(date, description, amount, category)`` sorted by date.
    """
    rng = random.Random(seed)
    end = end or date.today().replace(day=1)

    # Work out the first month so that exactly ``months`` are produced.
    year, month = end.year, end.month
    for _ in range(months - 1):
        month -= 1
        if month < 1:
            month = 12
            year -= 1
    first = date(year, month, 1)

    rows: list[tuple[date, str, float, str]] = []
    for month_start in _month_range(first, months):
        # Fixed recurring items.
        for desc, amount, category, dom in _FIXED_RECURRING:
            try:
                day = date(month_start.year, month_start.month, dom)
            except ValueError:
                day = month_start
            # small +/- jitter on the exact posting day
            day += timedelta(days=rng.randint(-1, 1))
            rows.append((day, desc, round(amount, 2), category))

        # Variable recurring bill: electricity, seasonally dependent.
        season = 1.0 + 0.35 * (
            1 if month_start.month in (11, 12, 1, 2) else 0
        )
        elec = -round(rng.uniform(55, 85) * season, 2)
        rows.append(
            (
                date(month_start.year, month_start.month, 18),
                "PowerGrid Electricity",
                elec,
                "utilities",
            )
        )

        # Irregular spending.
        days_in_month = (
            (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
            - timedelta(days=1)
        ).day
        for desc, (lo, hi), category, prob in _IRREGULAR:
            for dom in range(1, days_in_month + 1):
                if rng.random() < prob / 3.0:
                    amount = -round(rng.uniform(-hi, -lo), 2)
                    rows.append(
                        (
                            date(month_start.year, month_start.month, dom),
                            desc,
                            amount,
                            category,
                        )
                    )

    rows.sort(key=lambda r: r[0])
    return rows


def write_sample_csv(
    path: str | Path,
    months: int = 12,
    seed: int = 42,
) -> Path:
    """Generate a history and write it to ``path`` as CSV.

    Returns the resolved :class:`~pathlib.Path` that was written.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = generate_transactions(months=months, seed=seed)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["date", "description", "amount", "category"])
        for d, desc, amount, category in rows:
            writer.writerow([d.isoformat(), desc, f"{amount:.2f}", category])
    return path


if __name__ == "__main__":  # pragma: no cover
    out = write_sample_csv("data/transactions_sample.csv")
    print(f"Wrote sample data to {out}")
