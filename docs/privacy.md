# Privacy

OfferPilot handles sensitive career data. A job search command center can contain resumes, contact details, compensation expectations, interview feedback, rejection reasons, recruiter messages, voice recordings, and private files. Privacy must be part of the product design from the first commit.

## Privacy Principles

- Collect the minimum data needed for the user's workflow.
- Keep user-provided artifacts separate from generated reports.
- Do not send private data to search providers unless required and approved.
- Redact secrets and personal identifiers from logs.
- Make deletion and export understandable.
- Use examples and fixtures that never contain real candidate data.

## Sensitive Data

OfferPilot should treat these categories as sensitive:

- Resume content, portfolio links, phone numbers, email addresses, and addresses.
- Voice recordings and transcripts.
- Uploaded files and screenshots.
- Interview notes, feedback, and interviewer names.
- Application history, rejection reasons, offer details, and compensation.
- Authentication tokens, API keys, cookies, and provider credentials.

## Intake Privacy

### Text

Text input may contain recruiter messages, private notes, or pasted job descriptions. The system should detect obvious personal information and avoid placing it in telemetry.

### Voice

Voice input should be stored only when needed. If speech-to-text is enough, users should be able to keep the transcript and discard the raw recording.

Speech-to-text adapters must mark transcript output as `private_user_context`. The external transcription skeleton requires `TRANSCRIPTION_PROVIDER_API_KEY`, `TRANSCRIPTION_PROVIDER_ENDPOINT`, and an injected transport before it can return anything. Missing setup must fail closed instead of returning fake transcript text.

### Files

Files may include resumes, PDFs, screenshots, and offer letters. Store original files separately from extracted text, and mark them as user-private by default.

### Links

Job links can be shared with search and fetch systems, but they should not be bundled with private resume details unless the user asks for personalized research.

## Third-Party Services

OfferPilot may eventually call LLM, speech-to-text, search, extraction, storage, or email providers. For each provider integration, document:

- What data is sent.
- Why the data is needed.
- Whether the provider stores or trains on the data.
- How users can disable or replace the provider.
- How failures and retries are logged.

## Search Privacy

Forced search is required for evidence-linked job research, but search queries should be carefully scoped.

Do send:

- Company name.
- Role title.
- Public job link.
- Public location or work mode.
- Generic interview topics.

Do not send by default:

- Full resume text.
- Email address or phone number.
- Private interview notes.
- Compensation floor or personal constraints.
- Full voice transcript.

## Logging

Logs should be useful for debugging without becoming a second private database.

Recommended logging defaults:

- Use stable internal IDs instead of raw emails or names.
- Store event type, status, duration, and provider name.
- Truncate extracted text.
- Redact tokens, cookies, phone numbers, email addresses, and obvious secrets.
- Keep raw prompts and responses off by default in production.

## Retention

Users should be able to:

- Delete an intake artifact.
- Delete a job opportunity and its related reports.
- Delete voice recordings while keeping transcripts.
- Export their records and `sourceUrls`.
- Clear reminders and application history.

Default retention should favor user control over indefinite storage.

## Demo and Fixture Policy

Examples in this repository must be fictional. Do not commit:

- Real resumes.
- Real interview notes.
- Real recruiter messages.
- Private job-search spreadsheets.
- Access tokens or API keys.
- Screenshots containing personal data.

Use obvious placeholders such as `alex@example.com`, `ExampleCo`, and `https://example.com/...`.

### Interview Fixtures

Interview-note fixtures may be committed only when they are fictional and clearly labeled as private user context. They can be used to test typed-note intake, transcript-backed summaries, and follow-up extraction.

Uploaded audio fixtures should use metadata-only examples such as `examples/interview-notes/audio-upload-metadata.json`. Do not commit real recordings. A metadata fixture can include a pretend file name, content type, duration, stage, company, and role, but the recording itself must remain absent.

Interview transcripts, typed notes, and audio-derived text are not public evidence. They must not appear in `sourceUrls`, and they should not be sent to search providers by default.

Provider-returned transcript metadata should keep `sourceUrls: []`. A transcript can support a private interview summary and next-focus list, but public report claims still need external evidence URLs.

## Security Relationship

Privacy and security overlap. Vulnerabilities that expose resumes, voice transcripts, files, application records, reminders, or evidence reports should be reported through the process in `SECURITY.md`.
