# Architecture

The runtime uses Python's standard library. There is no service, database, model, network client, or API key. Python package/build metadata is in pyproject.toml.

| Module | Responsibility |
| --- | --- |
| models | Immutable transaction/source records and actionable errors |
| config | Explicit source mappings, validated settings, exact decimal-string/integer conversion |
| ingest | Bounded CSV decoding, strict headers/rows, required fields, dates, IDs, precision, duplicate flags, hashes |
| engine | Candidate indexing, eligibility graph, conservative pair decisions, row partition, per-currency controls |
| output | CSV safety, escaped HTML, JSON, checksums, exclusive output directory creation and failure cleanup |
| demo | Small synthetic source fixtures and expected counts |
| cli | Commands, orchestration, messages, and exit codes |

## Money

Plain decimal strings are split into a sign, whole digits, and fractional digits, then scaled using integer arithmetic. There is no binary float conversion, decimal-context rounding, locale inference, or implicit FX conversion. Precision is explicit per currency, and excess fractional digits fail validation. Signed zero is normalized to zero. All totals and differences use integer addition/subtraction and serialize to fixed-point text.

## Candidates and decision policy

Bank rows are bucketed by currency and sorted by signed minor-unit amount. Bisect identifies the amount range for each ledger row; date, sign, and reference rules filter inspected pairs. Work is approximately O(B log B + L log B + inspected pairs); dense values can still be quadratic, so comparison and edge limits stop expansion rather than silently truncating results.

No candidates are removed to make a later candidate appear unique. Both endpoints must have degree one in the original eligible graph before an exact nonzero pair can be accepted; duplicate-content rows are excluded from automatic acceptance. Tolerance differences and all ambiguous/zero cases remain review candidates. There is no claim of economic certainty from algorithmic uniqueness.

The engine partitions each original source into matched and remaining rows. It verifies each currency independently: total ledger minus total bank equals accepted-pair difference plus remaining-row difference. Current acceptance rules make accepted-pair differences zero, while the formula leaves the accounting control explicit.

## Provenance and outputs

Input hashes are computed from the bytes actually parsed. Only the filename, not the absolute local path, is included in reports. CSV source row numbers use the last physical line of the record. Results include normalized configuration and version. Output ordering is stable by transaction IDs/candidate lookup; generated timestamps make byte-for-byte exports differ across runs.

Output directory creation is exclusive. Handled write failures remove the newly created directory. Abrupt termination can leave partial files. The checksum manifest covers all other generated outputs and does not hash itself. It is not a signature. Spreadsheet formula protections are applied only to text export fields; validated numeric values remain numeric. HTML data is escaped and the report uses no scripts, fonts, or other external resources.

## Trust boundaries and deferred functionality

Public API callers should ingest through load_csv. Internal record construction assumes validated fields; this is not a general-purpose hostile-object validation API. Limits are configurable and should suit available memory. Error messages provide actionable context without hiding invalid financial rows.

No automatic posting, fuzzy descriptions, partial/batch settlement, FX conversion, persistent approvals, or remote hosting is included. Each requires a new explicit scope and corresponding correctness/security review.
