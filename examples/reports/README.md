# Report Fixtures

These fixtures are fictional report outputs used to test the source-backed report contract. They are examples only; real reports must refresh source URLs and re-score evidence before use.

- `job-report-with-sourceUrls.json`: a job-link interview-prep report with object-style top-level `sourceUrls`, claim `sourceIds`, evidence quality expectations, and private user context markers.
- `daily-intelligence-with-sourceUrls.json`: a daily intelligence brief with string-style retained `sourceUrls` and weak signal unknowns.
- `report-fixtures.jsonl`: structured expectations for report type, retained `sourceUrls`, required claim `sourceIds`, expected evidence rows, quality labels, and weak-source handling.

Evidence contract:

- Completed reports must preserve top-level `sourceUrls`.
- Claims must cite supporting evidence through `sourceIds` when evidence items are available.
- Weak, stale, or missing evidence should become `unknowns`, not confident claims.
- `expected_evidence` rows can be used to test which sources support claims and which sources become `unknowns`.
- Fixture URLs are placeholders, so `sourceUrls_refresh_required` remains true for real use.
