"""Executable entry point so the package can be run with ``-m finsight``."""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
