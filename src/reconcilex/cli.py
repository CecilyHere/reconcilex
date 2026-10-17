"""Command-line boundary for validation, reconciliation, and report generation."""

import argparse
import json
import sys
import tempfile
from pathlib import Path

from . import __version__
from .config import load_settings, settings_from_dict
from .engine import reconcile
from .ingest import load_csv
from .models import ReconcileError
from .output import write_report


def run(ledger: Path | str, bank: Path | str, output: Path | str,
        config: Path | str | None = None) -> dict:
    settings = load_settings(config)
    result = reconcile(load_csv(ledger, settings.ledger, settings),
                       load_csv(bank, settings.bank, settings), settings)
    write_report(result, output)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reconcile two CSV exports locally; keep uncertain pairs for review.")
    parser.add_argument("--version", action="version", version=f"ReconcileX {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("reconcile", help="compare signed ledger and bank CSV exports")
    command.add_argument("ledger", type=Path)
    command.add_argument("bank", type=Path)
    command.add_argument("--config", type=Path, help="explicit JSON mapping and matching configuration")
    command.add_argument("--out", type=Path, required=True, help="new output directory; existing paths are refused")
    command.add_argument("--fail-on-unresolved", action="store_true", help="return exit code 3 if any rows remain")
    demo = commands.add_parser("demo", help="run synthetic fixtures; no credentials or real data needed")
    demo.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            from .demo import BANK, CONFIG, LEDGER
            settings = settings_from_dict(CONFIG)
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "ledger.csv").write_text(LEDGER, encoding="utf-8")
                (root / "bank.csv").write_text(BANK, encoding="utf-8")
                result = reconcile(load_csv(root / "ledger.csv", settings.ledger, settings),
                                   load_csv(root / "bank.csv", settings.bank, settings), settings)
                write_report(result, args.out)
        else:
            result = run(args.ledger, args.bank, args.out, args.config)
        print(f"Report: {args.out / 'report.html'}")
        print(json.dumps(result["summary"], sort_keys=True))
        if getattr(args, "fail_on_unresolved", False) and (
                result["summary"]["remaining_ledger"] or result["summary"]["remaining_bank"]):
            return 3
        return 0
    except (ReconcileError, OSError, ValueError) as exc:
        print(f"ReconcileX: {exc}", file=sys.stderr)
        return 2
