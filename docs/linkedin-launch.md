# LinkedIn launch draft

Status: prepared for the owner to review and publish; this post has not been sent to LinkedIn.

Bank reconciliation looks straightforward until the same amount appears more than once, dates differ, or references conflict.

I built ReconcileX, a small open-source Python tool that compares ledger and bank CSV exports locally. It accepts exact pairs only when the candidate is unique on both sides, then puts ambiguous items and amount differences into a review report.

The engineering focus was financial correctness: integer money arithmetic, currency separation, row-level traceability, and tests that check every row and amount is accounted for. The basic workflow has no API keys or runtime dependencies.

This first release handles one-to-one CSV comparisons. It does not handle FX conversion or split settlements, and it has been validated with synthetic data rather than production customer records.

Repository: https://github.com/CecilyHere/reconcilex

If you work with reconciliation exports, I'd welcome feedback on the review workflow and column mapping. Please use synthetic examples when opening an issue.
