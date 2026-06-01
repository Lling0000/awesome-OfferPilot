## Summary

What changed, and why?

## Evidence Contract

- [ ] New or changed research outputs keep top-level `sourceUrls`.
- [ ] Claims distinguish sourced facts, user-provided context, and inference.
- [ ] Missing evidence is represented as unknowns, not guessed specifics.

## Privacy

- [ ] No real resumes, interview notes, recruiter messages, voice files, or private screenshots are included.
- [ ] Logs, fixtures, examples, and screenshots use fictional data.
- [ ] Any third-party provider boundary or secret handling change is documented.

## Public Readiness

- [ ] User-facing behavior updates docs, examples, templates, or `CHANGELOG.md` when useful.
- [ ] Packaging or CI changes keep `offerpilot doctor --strict-publish` passing.
- [ ] New adapters fail closed when credentials, permissions, or source URLs are missing.

## Verification

Commands run:

```bash
ruff format --check .
ruff check .
pytest
offerpilot doctor --strict-publish
```

## Screenshots Or Output

Add screenshots, CLI output, or report snippets when the change affects UI, reports, adapters, or developer workflow.
