# Contributing

Install the package in an isolated Python 3.11+ environment and run `python -m unittest discover -s tests -v`. Keep code, comments, issues, pull requests, and documentation in English.

For bugs, include the version, command, expected result, observed result, and a minimal synthetic CSV/configuration pair. Never upload real banking records, private data, tokens, or employer documents. Avoid personal financial values even in screenshots.

Matching changes need objective acceptance criteria and tests for currency isolation, exact arithmetic, no row reuse, ambiguity preservation, and conservation. Do not weaken assertions to fit a changed algorithm. Prefer small changes with a clear explanation of user impact. Respect third-party licenses and identify any adapted material.

Run the synthetic demo after report changes and visually inspect the generated HTML. Release notes must describe limitations and tests actually run. The maintainer will prioritize defects and evidenced user needs over feature or repository counts.
