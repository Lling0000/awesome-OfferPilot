# Launch Checklist

Use this checklist before publishing OfferPilot as a public GitHub project, demo, or release candidate.

## Launch Blockers

These items should be true before the repository is announced or shared beyond a small review group.

### Runtime And Verification

- [ ] Fresh-clone quick start works from `README.md`.
- [ ] The two-terminal smoke path in `docs/demo-script.md` works, with `offerpilot serve` left running while the browser is inspected.
- [ ] `/api/health` returns `{"ok":true,"service":"offerpilot"}`.
- [ ] `/` shows applications, reminders, daily intelligence, and evidence reports.
- [ ] `/intelligence` shows recent fixture-backed briefs and findings.
- [ ] `/intelligence/{run_id}` shows worker coverage and source URLs.
- [ ] `/applications/{application_id}` shows interview intake and summaries.
- [ ] `/reports/{search_report_id}` shows source URLs and evidence quality scores.

```bash
ruff format --check .
ruff check .
pytest
offerpilot demo --reset
offerpilot doctor --strict-publish
```

### Evidence Contract

- [ ] Completed reports require top-level `sourceUrls`.
- [ ] `examples/reports/job-report-with-sourceUrls.json` demonstrates the report contract.
- [ ] `examples/reports/daily-intelligence-with-sourceUrls.json` demonstrates the daily intelligence contract.
- [ ] Search and daily intelligence outputs keep query plans or worker traces.
- [ ] Social/forum-style signals are marked as needing verification.
- [ ] Unsupported claims become unknowns instead of confident statements.
- [ ] Fixtures use fictional companies and sample URLs; no fixture is presented as current live hiring intelligence.

### Privacy And Safety

- [ ] No real resumes, voice recordings, transcripts, recruiter messages, screenshots, cookies, or tokens are committed.
- [ ] Logs and fixtures do not contain private job-search history.
- [ ] Upload, transcription, search, and LLM adapter boundaries are documented in `docs/privacy.md` and `docs/adapters.md`.
- [ ] Security reporting instructions are visible in `SECURITY.md`.

### Release Boundary

- [ ] README clearly says the current release is local-first and mock/fixture-backed.
- [ ] The project is not marketed as live web intelligence, real Boss Zhipin scraping, automated application submission, or production speech-to-text.
- [ ] External providers fail closed when credentials, network access, or setup are missing.

## Polish Before Sharing

These items make the repo easier to trust, star, and contribute to, but they should not hide missing launch blockers.

### Repository Face

- [ ] README explains the product in the first screen.
- [ ] README includes quick start, demo flow, commands, adapter entry points, and roadmap links.
- [ ] Architecture, privacy, evidence, adapter, intelligence, demo, launch checklist, and roadmap docs are linked.
- [ ] Social card, architecture asset, and fixture-backed dashboard/report/intelligence screenshots render.
- [ ] License, contributing guide, security policy, PR template, and issue templates are present.
- [ ] `docs/roadmap.md` has good-first-issue candidates with file paths and acceptance criteria.
- [ ] Initial public issues are created from the roadmap and labeled clearly.

### GitHub Metadata

Suggested description:

```text
Evidence-backed job search tracking and interview prep with source URLs, voice notes, reminders, and daily intelligence.
```

Suggested topics:

```text
job-search, interview-prep, fastapi, sqlite, agents, evidence, source-citations, voice-notes, career-tools
```

CLI setup commands after the GitHub repository exists:

```bash
gh repo edit \
  --description "Evidence-backed job search tracking and interview prep with source URLs, voice notes, reminders, and daily intelligence." \
  --add-topic "job-search,interview-prep,fastapi,sqlite,agents,evidence,source-citations,voice-notes,career-tools"
```

Only set a homepage when there is a hosted demo or docs site:

```bash
gh repo edit --homepage "https://..."
```

GitHub social preview note: use `assets/social-card.svg` as the source artwork. If GitHub does not accept SVG for the preview upload, export it to PNG and upload it manually in repository settings.

### Public Positioning

- [ ] README and issue templates invite provider adapters without promising live scraping.
- [ ] Roadmap separates good first issues, larger tracks, and non-goals.
- [ ] Launch copy says "source-backed" and "mock/fixture-first" rather than "real-time" or "live scraping".
- [ ] Screenshots, if added later, show fixture data only.
