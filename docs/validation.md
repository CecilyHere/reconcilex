# Validation — v1.0.0

Executed on 2026-10-17. Local host: Python 3.12.5, macOS 15.4.1, Apple Silicon. These results use synthetic data and are not evidence of production adoption or a general performance guarantee.

## Executed locally

- 47 behavioral tests passed from source. This includes one seeded randomized test covering 150 independent graph scenarios against an all-pairs eligibility oracle, plus row partition, no reuse, deterministic ordering, and per-currency conservation checks.
- Built the source distribution and universal Python wheel with build 1.6.1, setuptools 84.0.0, and wheel 0.48.0.
- Installed the wheel offline into a fresh temporary virtual environment with no runtime dependencies; `pip check` reported no broken requirements.
- Ran all 47 tests against the installed wheel and executed its actual `reconcilex` console entry point successfully. Verified built-in demo counts against committed expected values.
- Verified malformed input and existing-output failure behavior, formula-leading text handling, HTML escaping, input hashes, and generated-file checksums.
- Opened the actual generated HTML report in a browser and inspected the summary, currency totals, pair/exception sections, and download links. The screenshot is from the actual synthetic demo.
- Executed a 10,000-row-per-source synthetic benchmark: 10,000 accepted pairs, no remaining rows, 10,000 amount-range comparisons. Input loading and matching took 2.0539 seconds; including all output exports took 2.2396 seconds in that run. Dense duplicate amounts have different scaling and can hit safety limits.

Reproduction commands are documented in the README and `scripts/verify_distribution.py` / `scripts/benchmark.py`. A final packaging run is required after any source change; recorded results should only be updated after execution.

## GitHub validation status

CI is configured for Python 3.11–3.14 on Ubuntu and Python 3.12 on Windows. Remote runs and release publication are pending at this checkpoint. Do not interpret configured jobs as passed checks.

## Acceptance limits

Validated only for the documented one-to-one CSV scope. No bank integrations, FX conversion, XLSX/PDF extraction, split settlements, persistent approvals, or accounting posting. Unique candidates can still be economically wrong when source data or policy is wrong. No critical defect is known from the executed suite; real-world feedback and sanitized fixtures remain necessary.
