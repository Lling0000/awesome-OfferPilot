# Roadmap

OfferPilot's public promise is intentionally narrow: a local-first job-search workspace that keeps generated interview prep tied to source URLs. The current implementation is mock/fixture-first and source-backed. Real parsing, search, transcription, and LLM providers should be added behind adapter contracts and must fail closed when they are not configured.

## Current Baseline

- Local demo data is seeded by `src/offerpilot/seed.py`.
- Mock provider boundaries live in `src/offerpilot/providers/mock.py`.
- Search source contracts live in `src/offerpilot/providers/search_sources.py` and `docs/adapters.md`.
- The external search API skeleton fails closed until credentials, endpoint, and transport are configured.
- The external transcription provider skeleton fails closed until credentials, endpoint, and transport are configured.
- Job intake handles URLs and pasted JD text through the same source-backed report path.
- Company career-page and mirrored job-board fixtures exercise non-Boss job-link parsing.
- Pasted JD text is private user context and must not be counted as public evidence.
- Pasted JD parser fixtures cover backend, frontend, data, and product-style roles, including mixed Chinese/English fields.
- Evidence normalization and scoring live in `src/offerpilot/search.py`.
- Report evidence panels show source type, publisher/domain, quality label, score reasons, and usage guidance.
- Report claim sections cite stored evidence item IDs with `sourceIds`; weak or stale evidence becomes `unknowns`, not confident recommendations.
- Source URL validation lives in `src/offerpilot/reports.py`.
- Interview-note fixtures and audio-upload metadata fixtures live in `examples/interview-notes/`.
- Interview transcripts are private user context and are not `sourceUrls`.
- Web routes live in `src/offerpilot/routes/web.py` and templates live in `src/offerpilot/templates/`.
- API routes live in `src/offerpilot/routes/api.py`.
- Runnable examples live in `examples/search-source-plugin/` and `examples/reports/`.
- The search-source plugin example returns multiple deterministic fixture candidates without live network access.

## Good First Issues

The current good-first queue has been implemented. New contributor-friendly issues should be opened from the larger tracks below, with deterministic fixtures and privacy boundaries before any live provider claim.

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
