# Reminder Fixtures

These fixtures are fictional workflow metadata for daily follow-ups. They describe which missing job-search fields should trigger reminders without storing private resumes, transcripts, recruiter messages, or evidence URLs.

- `daily-reminders.jsonl`: structured reminder cases with application state, optional interview state, missing fields, expected reminder category, priority, title/body snippets, and the source URL boundary.

Privacy and evidence contract:

- Reminder metadata sets `safe_without_private_sourceUrls` when it is safe to show without private `sourceUrls`, but it is not public evidence.
- `sourceUrls` must stay `[]` because reminders are workflow prompts, not completed reports.
- Completed reports still require external source URLs from search or intelligence evidence.
- The `missing_fields` list names the workflow fields the user should fill next.
- Daily reminders may ask users to fill next-action fields such as resume status, interview date, next step owner, follow-up due date, and missing evidence links.
