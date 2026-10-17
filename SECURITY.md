# Security

ReconcileX reads local CSV files and writes local reports. It does not connect to banks, post accounting entries, or send telemetry. Reports and JSON can contain sensitive financial descriptions and identifiers; protect them like the original data.

HTML escapes input text and uses no scripts or external assets. CSV text beginning with formula triggers is prefixed with an apostrophe, but spreadsheet re-saving or application-specific interpretation can remove protections. JSON preserves original data and must not be treated as spreadsheet-safe text without appropriate handling.

Resource limits reduce accidental expansion; this is not a sandbox for adversarial files. Do not run untrusted source code or open untrusted spreadsheets as part of a report review.

For a vulnerability, use GitHub's private vulnerability reporting if it is enabled. If unavailable, open a minimal issue asking for a private reporting channel without including exploit payloads, credentials, or financial data. Do not post private information publicly.
