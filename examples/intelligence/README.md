# Daily Intelligence Fixtures

These fixtures are fictional public-source signals for the deterministic daily intelligence demo. They document the expected output of each mock scout without using private interview notes, private resumes, recruiter messages, cookies, or live scraping.

- `daily-intelligence.jsonl`: structured cases for company-scale labels, role family, signal type, source type, expected tags, relevance score, retained `sourceUrls`, `needs_verification`, and corroboration requirements.

Evidence contract:

- Intelligence fixtures are public-source signals, not private interview notes.
- Every row keeps retained `sourceUrls` because daily intelligence findings must remain source-backed.
- Social and forum examples set `needs_corroboration` so weak or uncorroborated findings stay marked as needing verification.
- Every row sets `sourceUrls_refresh_required` because fixture URLs are examples, not current live hiring intelligence.
- Fixture rows are deterministic examples only; production adapters must refresh and re-score sources before presenting live hiring intelligence.
