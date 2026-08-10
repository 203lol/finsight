"""Command-line interface for FinSight.

Exposes three sub-commands:

* ``analyse`` -- run the full pipeline on a CSV and print a report,
  optionally saving charts.
* ``generate-data`` -- write a synthetic sample CSV.
* ``forecast`` -- print just the balance projection.

Run ``uv run -m finsight --help`` for usage.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .analysis import analyse
from .datagen import write_sample_csv
from .forecast import forecast_balance
from .loader import load_transactions
from .recurring import detect_recurring_payments


def _add_common_input_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "csv",
        type=Path,
        help="Path to a transactions CSV file.",
    )
    parser.add_argument(
        "--starting-balance",
        type=float,
        default=0.0,
        help="Balance before the first transaction (default: 0).",
    )


def build_parser() -> argparse.ArgumentParser:
    """Construct the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="finsight",
        description=(
            "FinSight -- detect recurring payments, forecast your balance, "
            "and get plain-language money recommendations."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # analyse
    p_analyse = sub.add_parser(
        "analyse", help="Run the full analysis and print a report."
    )
    _add_common_input_args(p_analyse)
    p_analyse.add_argument(
        "--horizon",
        type=int,
        default=90,
        help="Forecast horizon in days (default: 90).",
    )
    p_analyse.add_argument(
        "--plots",
        type=Path,
        metavar="DIR",
        default=None,
        help="If given, save charts as PNGs into this directory.",
    )

    # generate-data
    p_gen = sub.add_parser(
        "generate-data", help="Write a synthetic sample CSV."
    )
    p_gen.add_argument(
        "output",
        type=Path,
        help="Where to write the generated CSV.",
    )
    p_gen.add_argument(
        "--months",
        type=int,
        default=12,
        help="Months of history to generate (default: 12).",
    )
    p_gen.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42).",
    )

    # forecast
    p_fc = sub.add_parser(
        "forecast", help="Print only the balance forecast."
    )
    _add_common_input_args(p_fc)
    p_fc.add_argument(
        "--horizon",
        type=int,
        default=90,
        help="Forecast horizon in days (default: 90).",
    )
    p_fc.add_argument(
        "--every",
        type=int,
        default=7,
        help="Print every Nth day (default: 7).",
    )
    return parser


def _cmd_analyse(args: argparse.Namespace) -> int:
    transactions = load_transactions(args.csv)
    result = analyse(
        transactions,
        horizon_days=args.horizon,
        starting_balance=args.starting_balance,
    )
    print(result.report())

    if args.plots is not None:
        # Imported lazily so the common path does not require matplotlib.
        from .visualize import (
            plot_balance_forecast,
            plot_recurring_payments,
            plot_spending_by_category,
        )

        outdir = args.plots
        outdir.mkdir(parents=True, exist_ok=True)
        p1 = plot_balance_forecast(
            transactions,
            result.forecast,
            outdir / "balance_forecast.png",
            starting_balance=args.starting_balance,
        )
        p2 = plot_spending_by_category(
            transactions, outdir / "spending_by_category.png"
        )
        p3 = plot_recurring_payments(
            result.recurring, outdir / "recurring_payments.png"
        )
        print("\nSaved charts:")
        for p in (p1, p2, p3):
            print(f"  {p}")
    return 0


def _cmd_generate_data(args: argparse.Namespace) -> int:
    path = write_sample_csv(args.output, months=args.months, seed=args.seed)
    print(f"Wrote {args.months} months of sample data to {path}")
    return 0


def _cmd_forecast(args: argparse.Namespace) -> int:
    transactions = load_transactions(args.csv)
    recurring = detect_recurring_payments(transactions)
    fc = forecast_balance(
        transactions,
        recurring,
        horizon_days=args.horizon,
        starting_balance=args.starting_balance,
    )
    print(f"{'Date':<12} {'Balance':>12}")
    print("-" * 25)
    for i, (d, b) in enumerate(zip(fc.dates, fc.balances, strict=True)):
        if i % args.every == 0 or i == len(fc.dates) - 1:
            print(f"{d.isoformat():<12} {b:>12,.2f}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    handlers = {
        "analyse": _cmd_analyse,
        "generate-data": _cmd_generate_data,
        "forecast": _cmd_forecast,
    }
    try:
        return handlers[args.command](args)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
