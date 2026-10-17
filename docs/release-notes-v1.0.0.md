# ReconcileX v1.0.0

ReconcileX compares two transaction CSV exports locally and produces an explicit reconciliation review report.

## Features

- Configurable columns, encoding, date format, source sign, date window, and amount tolerance.
- Exact signed integer money and independent currency controls.
- Exact pairs accepted only when each row has one eligible candidate on both sides.
- Ambiguous candidates, duplicate-content rows, zero values, and amount differences remain for review.
- HTML, CSV, JSON, input fingerprints, and export checksum manifest.
- Reusable Python API and a synthetic demo with no credentials or runtime dependencies.

## Install and try

Requires Python 3.11+:

```bash
python -m pip install "git+https://github.com/CecilyHere/reconcilex.git@v1.0.0"
reconcilex demo --out reports/demo
```

Open `reports/demo/report.html`. Expected demo: 3 accepted pairs, 4 review candidates, 5 remaining ledger rows, 6 remaining bank rows. See the README for configuration and the validation report for executed checks.

## Known limitations

CSV-only, one-to-one, export-only. No FX conversion, PDF/XLSX extraction, split/batch settlements, persistent manual approvals, or automatic journal entries. A unique candidate is not proof of economic identity; users must understand the matching policy and inspect unresolved records. Validation uses synthetic datasets; real-world adoption is not yet established. Existing output directories are refused. Spreadsheet re-saving can change formula protections.
