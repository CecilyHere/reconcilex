"""Reproducible synthetic benchmark; no customer data or universal SLA claim."""

import csv
import json
import platform
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path

from reconcilex.config import Settings, money_text
from reconcilex.engine import reconcile
from reconcilex.ingest import load_csv
from reconcilex.output import write_report

count = 10_000
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    for side, offset in [("ledger", 0), ("bank", 1)]:
        with (root / f"{side}.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["id", "date", "amount", "currency", "reference", "description"])
            for i in range(count):
                writer.writerow([f"{side[0]}{i:06}", date(2026,1,1)+timedelta(days=i%28+offset),
                                 money_text((i+1)*(-1 if i%2 else 1), 2),
                                 "USD" if i%7==0 else "SGD", f"SYN-{i}", "Synthetic benchmark"])
    start = time.perf_counter()
    settings = Settings()
    result = reconcile(load_csv(root/"ledger.csv", settings=settings),
                       load_csv(root/"bank.csv", settings=settings), settings)
    engine_seconds = time.perf_counter()-start
    write_report(result,root/"report")
    total_seconds = time.perf_counter()-start
    assert result["summary"]["matched_pairs"] == count
    assert result["summary"]["remaining_ledger"] == result["summary"]["remaining_bank"] == 0
    assert all(t["conservation_passed"] for t in result["totals"].values())
    print(json.dumps({"python":platform.python_version(),"platform":platform.platform(),
                      "rows_per_source":count,"load_and_match_seconds":round(engine_seconds,4),
                      "with_exports_seconds":round(total_seconds,4),"summary":result["summary"]},indent=2))
