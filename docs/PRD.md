# ReconcileX product requirements — v1.0.0

Status: approved implementation scope for Month 01; release subject to executed acceptance checks. Created 2026-10-17 before implementation.

## Product

Value proposition: compare two transaction CSV exports locally, accept only unambiguous exact-value pairs, and produce an inspectable exception report.

Target users: finance analysts and small operations teams with signed ledger and bank CSV exports. Primary use case: period-end or daily one-to-one transaction comparison without uploading financial data to a service. Existing alternatives: Excel, ERPNext, Firefly III import workflows, and dylanpulver/recon. Explainability and integer money are existing approaches; this product's intended value is a small Python tool and a conservative portable review workflow. Demand for this implementation is not established.

## Must have

- CSV inputs with transaction id, date, signed amount, currency, and optional reference/description. Configurable column mapping, date format, delimiter, encoding, and sign multiplier per source. Defaults are explicit, never locale-guessed.
- Reject duplicate IDs, duplicate/missing headers, ragged rows, malformed dates, unsupported currencies, nonfinite or overprecision money, missing values, empty datasets, and files exceeding documented limits. Preserve row numbers in validation errors. Flag duplicate content without silently dropping rows.
- Supported built-in currencies: SGD, USD, EUR, GBP, AUD, CAD (2 decimals), JPY (0), KWD (3). Allow additional explicit precision mappings. No FX conversion.
- Candidate pairs must share currency and sign, fall within a configurable date window, and meet the amount tolerance. If both references are present, they must match after trimming and case folding; do not remove punctuation.
- Compute a complete bounded candidate graph. Auto-match only exact nonzero amounts whose candidate is unique on both sides. All ambiguous candidates, amount differences, duplicate-content rows, and zero amounts remain for review. Do not greedily consume rows to manufacture certainty.
- Export matches, review candidates, remaining ledger and bank rows, warnings, a machine-readable JSON result, and an HTML report. Show every original transaction exactly once in matches or remaining rows. Candidate listings may reference remaining rows multiple times.
- Report totals independently per currency and verify accounting identity: input difference = matched difference + remaining difference. Do not sum different currencies or call equal totals proof of reconciliation.
- Record input SHA-256 fingerprints, normalized configuration, application version, and UTC creation time. No network calls, telemetry, ERP posting, or overwriting source files.
- Refuse existing output directories. Write a new report directory without leaving partial outputs on handled failures. Escape HTML and neutralize dangerous text in CSV exports while retaining raw strings in JSON. Do not claim universal spreadsheet safety after user edits or re-save.
- CLI and documented reusable Python entry points; zero runtime dependencies; Python 3.11+. Package installation, CI, synthetic demo and expected output, MIT license.

## Should have

Readable row-level rule/review reasons, a compact report summary, explicit failed-run exit codes, deterministic ordering, configurable candidate limits, and a generated-file checksum manifest.

## Deferred

XLSX/PDF parsing, bank/API connectors, fuzzy descriptions, FX conversion, many-to-one/batch matching, manual approvals persisted in the application, database history, accounts/authentication, web server deployment, tax/performance analysis, and automated journal posting.

## Journey and I/O

Export two sources, normalize signs and mappings, run the CLI with an optional JSON config, open the generated HTML, and inspect CSV/JSON exceptions. Correct data or config and rerun into a new directory. An unresolved item is a review task, not a failed software run. CLI returns 0 for a successful report, 2 for validation/usage/filesystem failure, and 3 when `--fail-on-unresolved` is selected and remaining rows exist.

## Architecture

Python standard library only at runtime. Modules: models/configuration, strict CSV ingestion and money parsing, graph-based reconciliation, output rendering, demo data, and CLI. Use immutable transaction records with integer minor units; parse decimal strings exactly before conversion. No binary floating-point money. Candidate lookup indexed by currency and sorted amounts, with date/reference filtering and explicit work/edge limits. HTML is generated locally with no external resources or scripts.

Default resource limits: 10 MiB per input, 50,000 data rows per source, 100,000 candidate edges, and 2,000,000 inspected amount-range pairs. Fail with an actionable message when limits are exceeded. These are safeguards, not performance promises for every input distribution.

## Acceptance criteria

1. Synthetic demo yields expected exact matches, ambiguous candidates, amount-difference review, and unmatched rows with known totals.
2. Unit and integration tests exercise all mandatory validation, money precision, currency separation, no row reuse, duplicate ambiguity, date boundaries, reference conflicts, deterministic ordering, tolerance review, zero amounts, and conservation.
3. Seeded randomized tests compare indexed candidates to an independent all-pairs oracle and verify row partition and conservation invariants.
4. Actual CLI succeeds from an installed wheel in a fresh environment; malformed input fails cleanly; existing outputs are preserved.
5. HTML and CSV escape tests pass; input hashes and export checksums can be recomputed. An actual generated report is visually inspected.
6. A realistic synthetic 10,000-row-per-source case completes, with measured time recorded without extrapolating a universal SLA.
7. GitHub CI installs the package and executes tests. A stable release is published only after acceptance checks pass; remote CI status is reported as observed.
8. README, PRD, architecture, limitations, contribution guidance, demo, release notes, and retrospective are complete and English. No customer or employer data or credentials are committed.
