# Support

OfferPilot is an early public project. The fastest way to get useful help is to share a small, fictional reproduction that keeps the evidence contract visible.

## Before Asking

Please try the local smoke checks first:

```bash
offerpilot demo --reset
offerpilot doctor --strict-publish
python -m pytest
```

If the problem involves package installation, include your Python version and the install command you used.

## Where To Ask

- Use GitHub Discussions if they are enabled for setup questions, ideas, and contributor planning.
- Use a bug report for reproducible failures.
- Use a feature request for new workflows or product behavior.
- Use a provider adapter issue for job-board parsers, search sources, transcription providers, interview analyzers, or evidence normalizers.
- Use private vulnerability reporting for security issues.

## What To Include

Good support requests include:

- The command, page, or workflow that failed.
- Expected behavior and actual behavior.
- Relevant output from `offerpilot doctor --strict-publish`, `python -m pytest`, or `ruff check .`.
- Whether the demo runs with mock providers.
- Any `sourceUrls` behavior that changed or failed.

## Privacy

Do not include real resumes, interview notes, recruiter messages, job-search spreadsheets, voice recordings, transcripts, cookies, tokens, API keys, or private screenshots. Replace real companies and people with fictional examples and `example.com` URLs.

## Maintainer Expectations

Maintainers may ask for a smaller reproduction before investigating. Issues that include private data, secrets, unsupported claims, or screenshots with personal information may be closed or edited to protect users.
