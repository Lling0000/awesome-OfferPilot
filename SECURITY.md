# Security Policy

OfferPilot is an early-stage project, but its data is sensitive by design. A vulnerability can expose resumes, voice transcripts, interview notes, job-search history, reminders, files, or evidence reports.

## Supported Versions

OfferPilot has not published a stable release yet. Security reports should target the current default branch until versioned releases exist.

## Reporting a Vulnerability

Please do not open a public issue for a suspected vulnerability.

Use GitHub private vulnerability reporting if it is enabled for the repository. If it is not enabled yet, open a minimal public issue that says security contact is needed, without technical details, secrets, logs, or exploit steps.

When reporting, include:

- A short summary.
- Affected component or file path.
- Reproduction steps using fictional data.
- Potential impact.
- Suggested fix, if known.

Do not include real resumes, private interview notes, tokens, cookies, or personal job-search data in the report.

## Security-Sensitive Areas

OfferPilot contributors should be especially careful with:

- Authentication and session handling.
- File upload and parsing.
- Voice upload, storage, and transcription.
- Resume and interview-note storage.
- Third-party LLM, search, and speech-to-text providers.
- Logging, telemetry, and prompt capture.
- Daily reminders and notification channels.
- Export and deletion workflows.
- Evidence report sharing.

## Secret Handling

- Never commit API keys, OAuth tokens, cookies, or provider credentials.
- Keep `.env` files local unless a file is explicitly a redacted template.
- Redact secrets from logs and bug reports.
- Rotate exposed credentials immediately.

## Privacy Incidents

Treat accidental exposure of candidate data as a security issue. This includes public commits or logs containing:

- Names paired with private job-search history.
- Resume content.
- Interview feedback.
- Recruiter messages.
- Compensation expectations.
- Raw voice recordings or transcripts.

## Responsible Fixes

Security fixes should:

- Minimize data exposure first.
- Add regression tests when possible.
- Update docs if the security boundary changes.
- Preserve the evidence-first reporting contract without leaking private inputs into external search queries.
