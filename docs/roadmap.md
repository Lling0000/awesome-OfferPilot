# Roadmap

OfferPilot's public promise is intentionally narrow: a local-first job-search workspace that keeps generated interview prep tied to source URLs. The current implementation is mock/fixture-first and source-backed. Real parsing, search, transcription, and LLM providers should be added behind adapter contracts and must fail closed when they are not configured.

## Current Baseline

- Local demo data is seeded by `src/offerpilot/seed.py`.
- Mock provider boundaries live in `src/offerpilot/providers/mock.py`.
- Search source contracts live in `src/offerpilot/providers/search_sources.py` and `docs/adapters.md`.
- Evidence normalization and scoring live in `src/offerpilot/search.py`.
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

### 2. Improve Evidence Score Explanations

Goal: help users understand why a source is trusted, stale, weak, or only background context.

Suggested paths:

- `src/offerpilot/search.py`
- `src/offerpilot/templates/reports.html`
- `docs/search-and-evidence.md`
- `tests/test_search.py`
- `tests/test_app.py`

Acceptance criteria:

- Every displayed evidence item shows source type, publisher/domain, quality label, and score reasons.
- Official/current sources score higher than older forum-style or weak background signals in deterministic tests.
- Report pages still show top-level `sourceUrls`.
- Documentation explains that unsupported claims should become unknowns instead of confident recommendations.

### 3. Add Pasted JD Parser Fixtures

Goal: make the job intake loop useful even when the user has no job-board URL.

Suggested paths:

- `src/offerpilot/providers/mock.py`
- `src/offerpilot/intake.py`
- `src/offerpilot/routes/api.py`
- `src/offerpilot/templates/dashboard.html`
- `tests/test_intake.py`
- `tests/test_app.py`

Acceptance criteria:

- A pasted JD can create an application through the same source-backed report path as a URL.
- The parser marks the source as pasted user input, not public evidence.
- The resulting report still requires external `sourceUrls` from the search provider.
- Tests cover both URL input and pasted JD input.

### 4. Add A Fail-Closed External Search Adapter Skeleton

Goal: make real provider work easy to start while keeping the demo honest.

Suggested paths:

- `src/offerpilot/providers/search_sources.py`
- `docs/adapters.md`
- `.env.example`
- `.github/ISSUE_TEMPLATE/provider_adapter.yml`
- `tests/test_search.py`

Acceptance criteria:

- Missing credentials raise `SearchSourceNotConfigured` with a setup hint.
- The adapter never returns fake URLs to keep a report flowing.
- Tests cover the unconfigured state.
- Docs list required environment variables and expected returned fields.

### 5. Add Interview Intake Fixtures

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
