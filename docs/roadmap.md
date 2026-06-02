# Roadmap

OfferPilot's public promise is intentionally narrow: a local-first job-search workspace that keeps generated interview prep tied to source URLs. The current implementation is mock/fixture-first and source-backed. Real parsing, search, transcription, and LLM providers should be added behind adapter contracts and must fail closed when they are not configured.

## Current Baseline

- Local demo data is seeded by `src/offerpilot/seed.py`.
- Mock provider boundaries live in `src/offerpilot/providers/mock.py`.
- Search source contracts live in `src/offerpilot/providers/search_sources.py` and `docs/adapters.md`.
- The external search API skeleton fails closed until credentials, endpoint, and transport are configured.
- Job intake handles URLs and pasted JD text through the same source-backed report path.
- Pasted JD text is private user context and must not be counted as public evidence.
- Evidence normalization and scoring live in `src/offerpilot/search.py`.
- Report evidence panels show source type, publisher/domain, quality label, score reasons, and usage guidance.
- Source URL validation lives in `src/offerpilot/reports.py`.
- Web routes live in `src/offerpilot/routes/web.py` and templates live in `src/offerpilot/templates/`.
- API routes live in `src/offerpilot/routes/api.py`.
- Runnable examples live in `examples/search-source-plugin/` and `examples/reports/`.

## Good First Issues

These are small enough for first-time contributors and concrete enough to review.

### 1. Add A Second Fixture SearchSource

Goal: make the plugin example more useful without adding network access.

Suggested paths:

- `examples/search-source-plugin/example_source.py`
- `examples/search-source-plugin/run_example.py`
- `examples/search-source-plugin/README.md`
- `tests/test_adapter_example.py`

Acceptance criteria:

- The example returns at least two deterministic candidates with `title`, `url`, `snippet`, `publisher`, and `published_at`.
- `python examples/search-source-plugin/run_example.py` prints a report containing `sourceUrls`.
- `pytest tests/test_adapter_example.py` passes.
- The README states that the example is fixture-backed and not live search.

### 2. Expand Pasted JD Parser Coverage

Goal: improve the pasted-JD parser beyond the current backend fixture and make it useful for more roles.

Suggested paths:

- `src/offerpilot/providers/mock.py`
- `src/offerpilot/intake.py`
- `src/offerpilot/routes/api.py`
- `src/offerpilot/templates/dashboard.html`
- `examples/job-descriptions/`
- `tests/test_intake.py`
- `tests/test_app.py`

Acceptance criteria:

- Fixtures cover at least backend, frontend, data, and product-style JD text.
- Mixed Chinese/English JD fields can still produce stable company, role, city, and skill fields.
- Pasted JD text remains user context, not public evidence.
- The resulting report still requires external `sourceUrls` from the search provider.

### 3. Add Interview Intake Fixtures

Goal: give contributors a safe way to test transcript-backed summaries without committing real recordings.

Suggested paths:

- `examples/`
- `src/offerpilot/providers/mock.py`
- `src/offerpilot/interviews.py`
- `docs/privacy.md`
- `tests/test_interviews.py`

Acceptance criteria:

- Example interview notes are fictional and safe to commit.
- Mock transcription/analyzer output remains deterministic.
- Transcript text is treated as private user context, not a `sourceUrls` citation.
- Tests cover typed notes and uploaded fixture metadata.

## Larger Tracks

These are valuable but should be broken into smaller pull requests.

- Real search providers: add source-specific adapters behind `SearchSource`, with query IDs, result metadata, dedupe, freshness scoring, credibility scoring, and clear setup errors.
- Job-link parsing: support company career pages, Boss Zhipin-style URLs, LinkedIn-style URLs, and pasted JD text without coupling parsing to search.
- Evidence UX: make `/reports/{search_report_id}` easier to scan by separating official sources, community signals, older background sources, and unknowns.
- Interview artifacts: add provider-backed transcription while keeping audio, transcripts, and notes out of public fixtures.
- Daily intelligence workers: add allowed, documented sources only; keep social/forum findings marked as needing verification.
- Hosted demo path: document deployment only after auth, storage, privacy, and data retention boundaries are explicit.

## Non-Goals For Now

- No live scraping claims until real adapters are implemented, documented, and compliant with source terms.
- No automated job applications or recruiter messaging.
- No private resume, transcript, cookie, token, or screenshot fixtures.
- No unsourced AI reports. A completed report must keep valid top-level `sourceUrls`.
- No production speech-to-text claim while transcription is mock-backed.
- No multi-user hosted SaaS promise before authentication, authorization, storage, and deletion flows exist.
