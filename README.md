# FinSight

**FinSight** is a small, dependency-light Python toolkit that turns a plain
history of bank transactions into useful insight. Given a CSV of your
transactions it will:

1. **Detect recurring payments** — salary, rent, subscriptions, gym
   memberships, variable utility bills, and so on — by grouping similar
   charges and recognising regular time intervals (weekly, biweekly,
   monthly, quarterly, yearly).
2. **Forecast your future account balance** — projecting scheduled
   recurring cash flows plus modelled day-to-day discretionary spending,
   with a confidence band.
3. **Generate plain-language recommendations** — about your savings rate,
   emergency buffer, upcoming liquidity risk, and subscription load.

It ships with a real 8-month sample transaction history, so you can try
everything out immediately.

> ⚠️ FinSight produces a descriptive summary of *your own* numbers. It is
> not professional financial advice.

---

## Installation

FinSight is a standard, installable Python package (Python ≥ 3.10). Using
[`uv`](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/203lol/finsight.git
cd finsight
uv pip install -e .
```

For the test and lint tooling as well:

```bash
uv pip install -e ".[dev]"
```

The only runtime dependency is `matplotlib` (used for the charts).

---

## Quick start

The package is runnable as a module. Three sub-commands are available. The
repository ships with a real 8-month transaction history at
[`data/sample_transactions.csv`](data/sample_transactions.csv), so you can
try everything immediately.

### 1. Run the full analysis

```bash
uv run -m finsight analyse data/sample_transactions.csv --starting-balance 1000 --plots outputs
```

This prints a full report (recurring payments, forecast summary,
recommendations) and, because `--plots` was given, saves three charts into
`outputs/`.

### 2. Just the forecast

```bash
uv run -m finsight forecast data/sample_transactions.csv --starting-balance 1000 --horizon 90 --every 7
```

### 3. Generate additional synthetic data (optional)

For testing or experimentation you can also generate a fresh synthetic
history:

```bash
uv run -m finsight generate-data data/generated.csv --months 12 --seed 7
```

Run `uv run -m finsight --help` (or `... <command> --help`) for all options.

---

## Using it as a library

Everything you need is exposed at the top level of the package:

```python
from finsight import load_transactions, analyse

txns = load_transactions("data/sample_transactions.csv")
result = analyse(txns, horizon_days=90, starting_balance=1000)

print(result.report())

# Programmatic access to the pieces:
for payment in result.recurring:
    print(payment.description, payment.frequency.value, payment.typical_amount)

print("Projected final balance:", result.forecast.final_balance)
for rec in result.recommendations:
    print(rec.title)
```

Lower-level building blocks (`detect_recurring_payments`,
`forecast_balance`, `generate_recommendations`, the visualisation helpers,
etc.) can be imported individually — see the module docstrings.

---

## Input format

FinSight reads CSV files with at least a **date**, a **description** and an
**amount** column; **type** and **category** columns are optional. Column
names are matched case-insensitively against common aliases (both English
and German, e.g. `Buchungstag`, `Betrag`, `Verwendungszweck`), several date
formats are accepted (`DD/MM/YYYY`, `DD.MM.YYYY`, `YYYY-MM-DD`, ...), and
both `1,234.56` and `1.234,56` number styles are handled.

There are two supported ways to express direction:

**A — unsigned amounts with a `type` column** (as in the bundled dataset):

```csv
date,description,amount,type,category
01/01/2024,Salary Credit,2500.00,credit,salary
03/01/2024,Rent Payment,650.00,debit,rent
01/01/2024,Netflix Subscription,12.99,debit,subscription
```

Here `credit` marks money in and `debit` marks money out; FinSight applies
the sign for you.

**B — signed amounts, no `type` column**: positive = money in, negative =
money out.

```csv
date,description,amount,category
2024-01-01,Salary Credit,2500.00,salary
2024-01-03,Rent Payment,-650.00,rent
```

---

## Example output

The `analyse` command, run on the bundled dataset, prints a report like
this (abridged):

```
================================================================
  FinSight -- Financial Analysis Report
================================================================
Period analysed : 2024-01-01 to 2024-08-30
Transactions    : 477
Current balance : 5,658.26

----------------------------------------------------------------
Recurring payments
----------------------------------------------------------------
  Salary Credit                    monthly   income     2500.00  (x9)
  Rent Payment                     monthly   expense    -650.00  (x9)
  Telekom Internet                 monthly   expense     -39.99  (x8)
  Gym Membership                   monthly   expense     -29.99  (x9)
  Adobe Creative Cloud             monthly   expense     -24.99  (x9)
  Mobile Plan                      monthly   expense     -19.99  (x9)
  Netflix Subscription             monthly   expense     -12.99  (x9)
  Spotify Premium                  monthly   expense      -9.99  (x9)
  GitHub Pro                       monthly   expense      -4.99  (x9)
----------------------------------------------------------------
Recommendations
----------------------------------------------------------------
[*] Thin emergency buffer
    Your balance covers about 2.2 months of spending ...
[i] Healthy savings rate
    You are saving about 18% of your income (~585.17/month) ...
```

The three saved charts (see `outputs/`) are referenced below.

### Balance history and forecast
![Balance forecast](outputs/balance_forecast.png)

### Spending by category
![Spending by category](outputs/spending_by_category.png)

### Recurring payments
![Recurring payments](outputs/recurring_payments.png)

---

## Project layout

```
finsight/
├── pyproject.toml            # package metadata + build system
├── README.md
├── REPORT.md                 # design & methodology write-up
├── LICENSE
├── data/
│   └── sample_transactions.csv   # real 8-month history the tool analyses
├── notebooks/
│   └── example_usage.ipynb   # walk-through of the library API
├── outputs/                  # generated charts (committed)
├── src/finsight/
│   ├── __init__.py           # public API
│   ├── __main__.py           # `python -m finsight`
│   ├── cli.py                # argument parsing / sub-commands
│   ├── models.py             # Transaction, RecurringPayment, Forecast
│   ├── loader.py             # CSV loading
│   ├── datagen.py            # optional synthetic data generator
│   ├── recurring.py          # recurring-payment detection
│   ├── forecast.py           # balance forecasting
│   ├── recommend.py          # textual recommendations
│   ├── analysis.py           # orchestration + report
│   └── visualize.py          # charts (saved to PNG)
└── tests/                    # pytest suite
```

---

## Development

Run the tests:

```bash
uv run pytest
```

Lint and format with [ruff](https://astral.sh/ruff):

```bash
uv run ruff check .
uv run ruff format .
```

---

## How it works

A short summary — see [`REPORT.md`](REPORT.md) for the full methodology.

- **Recurring detection** normalises each description to a merchant key,
  groups transactions, then keeps groups whose amounts are consistent (low
  coefficient of variation) *and* whose inter-charge intervals are regular
  and match a known frequency.
- **Forecasting** anchors on the current balance, projects each recurring
  payment onto its future due dates, and adds an average daily
  discretionary drain estimated from recent non-recurring spending. The
  spread of that daily spend is accumulated into a 95% confidence band.
- **Recommendations** are transparent rules over the resulting figures
  (savings rate, months of emergency cover, forecast shortfalls,
  subscription share of income).

---

## License

Released under the MIT License — see [`LICENSE`](LICENSE).
