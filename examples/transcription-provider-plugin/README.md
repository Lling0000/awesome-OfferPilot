# Transcription Provider Plugin Example

This directory shows the smallest useful `ExternalTranscriptionProvider` transport example for OfferPilot.

It does not read a real audio file, call a live speech-to-text API, or require credentials. Instead, it uses a deterministic transport that returns fictional transcript text so contributors can understand the adapter contract without sending private audio anywhere.

## Run It

From the repository root:

```bash
python examples/transcription-provider-plugin/run_example.py
```

Expected behavior:

- `ExternalTranscriptionProvider` receives a fake API key, fake endpoint, and injected transport.
- The transport sees only a file path reference, privacy marker, and empty `sourceUrls`.
- The normalized output keeps `privacy: "private_user_context"`.
- The normalized output keeps `sourceUrls: []`, even if a provider response includes URL-like metadata.

## Contract

A transcription transport should accept:

```python
def transport(endpoint: str, payload: dict, headers: dict) -> dict:
    ...
```

The payload includes:

- `file_path`
- `privacy: "private_user_context"`
- `sourceUrls: []`

The response should include transcript text through one of:

- `transcript`
- `text`
- `content`

Optional response fields include:

- `confidence`
- `language`
- `duration_seconds`
- `quality_notes`

For a real provider, replace `fixture_transcription_transport` with a provider SDK or HTTP request, then pass real credentials through `TRANSCRIPTION_PROVIDER_API_KEY` and `TRANSCRIPTION_PROVIDER_ENDPOINT`. Do not commit real recordings, transcripts, API keys, or provider responses containing private interview data.

See `docs/adapters.md` and `docs/privacy.md` for the full adapter and privacy boundary.
