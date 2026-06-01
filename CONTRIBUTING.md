# Contributing to OfferPilot

Thanks for helping build OfferPilot, an evidence-first job search command center.

The project is early, so contributions should keep the product promise clear: users bring job links, resumes, interview notes, voice updates, files, and free-form text; OfferPilot turns them into structured job-search decisions with forced search, daily reminders, privacy controls, and `sourceUrls`.

## Contribution Themes

Good first contribution areas include:

- Documentation for architecture, evidence contracts, privacy, and threat models.
- Fictional examples for job links, resumes, interview notes, and reports.
- Parsers for job links and uploaded files.
- SearchSource plugins for public sources that can return URLs and snippets.
- Daily intelligence worker fixtures or adapters with clear source coverage.
- Reminder rules for missing application or interview information.
- Evidence scoring and report schemas.
- Tests that prevent unsourced claims from being labeled as facts.

## Evidence-First Rules

For report, search, or agent changes:

- Keep a top-level `sourceUrls` field in research outputs.
- Do not convert model memory into a sourced claim.
- Preserve the distinction between sourced facts, user-provided context, and inference.
- Prefer "unknown" over unsupported specificity.
- Add fixtures that show how evidence IDs map to report claims.

## Privacy Rules

Do not commit real candidate data. This includes:

- Resumes.
- Interview notes.
- Recruiter messages.
- Voice recordings or transcripts.
- Screenshots with personal information.
- Job-search spreadsheets.
- API keys, cookies, tokens, or provider secrets.

Use fictional names, `example.com` URLs, and obvious placeholders.

## Development Expectations

Before opening a pull request:

- Keep changes focused and easy to review.
- Add or update examples when changing report shapes.
- Add tests when changing behavior.
- Run available formatting and test commands once implementation exists.
- Run `offerpilot doctor --strict-publish` for repo-facing changes.
- Explain privacy or evidence tradeoffs in the PR description.

## Documentation Style

- Write for contributors who are new to the project.
- Use concrete examples.
- Name fields exactly when they are part of a contract, such as `sourceUrls`.
- Avoid claims about real companies unless the source is included.

## Pull Request Checklist

- The change preserves the evidence-first workflow.
- Search-related outputs include `sourceUrls`.
- Private user data is not committed.
- Examples are fictional.
- New reminders are useful, not noisy.
- The PR description names any open privacy or security questions.
