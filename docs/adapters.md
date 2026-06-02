# Adapter Guide

OfferPilot is built around replaceable adapters. The default adapters are deterministic so every contributor can run the project without accounts, API keys, or paid search credits. Production adapters can replace them as long as they preserve the evidence contract.

The guiding rule is simple: adapters collect and structure facts; they do not pretend to know what they did not retrieve.

## Adapter Map

| Adapter | Current default | Production direction | Contract boundary |
| --- | --- | --- | --- |
| `JobLinkParser` | `MockJobLinkParser` | Boss Zhipin-style links, company career pages, mirrored job-board links, mobile/shared redirect links, LinkedIn-style public links, pasted JD text | Parse user input into company, role, location, JD text, skills, canonical URL, and confidence. |
| `SearchProvider` | `MockSearchProvider` | Search API orchestration, site-specific search, forum/social retrieval | Execute the query plan and return raw source candidates plus retrieval coverage. |
| `SearchSource` | `LocalFixtureSearchSource` | Official-site crawler, forum adapter, social-search adapter, commercial SERP API adapter | Return raw candidates for one query-plan item. |
| `TranscriptionProvider` | `MockTranscriptionProvider` | Local or hosted speech-to-text | Turn voice notes or interview recordings into reviewable transcript text. |
| `InterviewAnalyzer` | `MockInterviewAnalyzer` | LLM-backed report writer with source references | Generate summaries, risks, unknowns, questions, and next actions from structured context. |

`EvidenceNormalizer` is currently implemented by `offerpilot.search.normalize_evidence_items`. It should stay inside the core pipeline because all search sources need the same URL canonicalization, dedupe, source typing, and source-quality scoring.

## Choose A Contribution Path

Start from the thing you know how to retrieve or structure:

| I want to... | Start with | First useful contribution |
| --- | --- | --- |
| Parse hiring-platform links | `JobLinkParser` | Convert a shared job URL, mobile redirect, public job-board link, or pasted JD into structured opportunity fields without claiming those fields are external evidence. |
| Add a searchable source | `SearchSource` | Return raw linked candidates for one query-plan item, then let the normalizer score and dedupe them. |
| Add voice or transcription | `TranscriptionProvider` | Convert a local voice note or interview recording into transcript text with confidence and quality notes. |
| Improve report writing | `InterviewAnalyzer` | Produce summaries and next actions that cite existing evidence IDs and top-level `sourceUrls`. |

Hiring-platform parsing is valuable, but parsing is not evidence. A Boss Zhipin-style parser, company-careers parser, mirrored-job-board parser, shared/mobile redirect parser, or LinkedIn-style public parser can extract role title, company, location, JD text, visible salary range, and canonical URL when allowed, but interview claims, company facts, and hiring-manager details still need forced search and source URLs. Deterministic parser fixtures should keep `public_evidence=false`.

Voice and transcription adapters should treat transcripts as private user context. A transcript can help generate prep notes, but it is not public evidence and should not be packaged as a `sourceUrls` citation.

## SearchSource Contract

`SearchSource` is the smallest useful plugin surface. It is intentionally plain Python:

```python
class SearchSource(Protocol):
    name: str
    source_type: str

    def search(self, query: dict) -> list[dict]:
        ...
```

The `query` argument is one item from `offerpilot.search.build_query_plan`. It currently includes:

| Field | Meaning |
| --- | --- |
| `id` | Stable query ID. Copy this into each returned candidate's `query_ids`. |
| `query` | Search text that may be sent to the external source. |
| `intent` | Why this query exists. Useful for logging and source-specific routing. |
| `source_focus` | Desired source family, such as `forum`, `official`, `search_engine`, or `freshness`. |

A candidate should include these fields when available:

| Field | Required | Notes |
| --- | --- | --- |
| `title` | Yes | Human-readable source title. |
| `url` | Yes | Must be `http://` or `https://` for completed reports. |
| `snippet` | Strongly recommended | Short extract returned by the source or adapter. |
| `source_type` | Strongly recommended | Use `official`, `job_board`, `news`, `forum`, `social`, or `unknown` until richer categories land. |
| `publisher` | Recommended | Site, company, community, or source name. |
| `published_at` | Optional | ISO-8601 string when the source exposes a credible date. |
| `retrieved_by` | Recommended | Adapter name, usually `self.name`. |
| `query_ids` | Yes | Include the input query ID so evidence can be traced back to the query plan. |
| `canonical_url` | Optional | Provide only when the source can confidently normalize mirrors or tracking links. |

The normalizer will infer missing source types, canonicalize URLs, deduplicate repeated results, and compute `relevance_score`, `freshness_score`, `credibility_score`, `overall_score`, `quality_label`, and `score_reasons`.

## Fail-Closed Behavior

Search adapters must fail closed when they cannot perform real retrieval. This matters for trust: a missing API key should never become fake source-backed evidence.

Recommended behavior:

```python
from offerpilot.providers.search_sources import SearchSourceNotConfigured

if not api_key:
    raise SearchSourceNotConfigured("my-search-source requires MY_SEARCH_API_KEY")
```

This error is better than returning an empty report that looks successful, and much better than fabricating plausible links. The CLI and UI can then tell the user that the adapter needs setup.

## External Search API Skeleton

`ExternalSearchAPISource` is the starter class for real search providers. It does not make network calls by itself. Instead, it checks setup, builds a minimal provider payload, and calls an injected `transport` function. That keeps tests deterministic and makes missing setup fail before any report can pretend to be source-backed.

Required environment variables:

| Variable | Meaning |
| --- | --- |
| `SEARCH_PROVIDER_API_KEY` | Credential used by the provider transport. Missing values raise `SearchSourceNotConfigured`. |
| `SEARCH_PROVIDER_ENDPOINT` | Provider endpoint URL. Missing values raise `SearchSourceNotConfigured`. |

Minimal shape:

```python
from offerpilot.providers import ExternalSearchAPISource, MockSearchProvider


def transport(endpoint: str, payload: dict, headers: dict) -> dict:
    # Replace this with a provider SDK or HTTP request.
    return {"results": []}


source = ExternalSearchAPISource(transport=transport)
provider = MockSearchProvider(sources=[source])
```

The transport should return either a list of candidates or a dict containing `results`, `items`, or `organic_results`. Returned candidates should use provider-native fields when possible:

| Provider field | OfferPilot field |
| --- | --- |
| `title` or `name` | `title` |
| `url` or `link` | `url` |
| `snippet` or `description` | `snippet` |
| `publisher`, `source`, or `displayed_link` | `publisher` |
| `published_at` or `date` | `published_at` |
| `source_type` | `source_type` |
| `canonical_url` | `canonical_url` |

Candidates without a URL are dropped. OfferPilot never invents URLs to keep a report flowing; if no linked candidates remain, the completed-report validator will still require valid top-level `sourceUrls`.

When the provider does not expose a reliable candidate `source_type`, leave it unset and let the evidence normalizer infer the type from the URL.

## External Transcription Provider Skeleton

`ExternalTranscriptionProvider` is the starter class for real speech-to-text providers. It does not read audio bytes or call a provider by itself. It checks setup, sends a minimal private-context payload to an injected `transport`, and normalizes the provider response into transcript text.

Required environment variables:

| Variable | Meaning |
| --- | --- |
| `TRANSCRIPTION_PROVIDER_API_KEY` | Credential used by the transcription transport. Missing values raise `TranscriptionProviderNotConfigured`. |
| `TRANSCRIPTION_PROVIDER_ENDPOINT` | Provider endpoint URL. Missing values raise `TranscriptionProviderNotConfigured`. |

Minimal shape:

```python
from offerpilot.providers import ExternalTranscriptionProvider


def transport(endpoint: str, payload: dict, headers: dict) -> dict:
    # Replace this with a provider SDK or HTTP request.
    return {"transcript": "The interviewer asked about SQL indexes.", "confidence": 0.86}


provider = ExternalTranscriptionProvider(transport=transport)
result = provider.transcribe("interview.m4a")
```

The normalized result always includes:

- `privacy: "private_user_context"`
- `sourceUrls: []`
- `provider`
- `file_path`
- `transcript`

Provider-returned `sourceUrls` are discarded. Interview transcripts can help summarize a user's own interview, but they are not public evidence and must not be cited as report sources.

## Minimal Examples

The runnable example in `examples/search-source-plugin` shows a tiny source that searches an in-memory dataset:

```bash
python examples/search-source-plugin/run_example.py
```

The example intentionally avoids network calls. It proves the plugin shape, returned candidate fields, and `MockSearchProvider(sources=[...])` replacement path without requiring credentials.

The runnable example in `examples/transcription-provider-plugin` shows a tiny transcription transport:

```bash
python examples/transcription-provider-plugin/run_example.py
```

The example intentionally avoids real audio files, API keys, and network calls. It proves the `ExternalTranscriptionProvider(transport=...)` replacement path and shows that normalized transcripts stay `private_user_context` with `sourceUrls: []`. For a real provider, replace `fixture_transcription_transport` with a provider SDK or HTTP request, then pass credentials through `TRANSCRIPTION_PROVIDER_API_KEY` and `TRANSCRIPTION_PROVIDER_ENDPOINT`.

## JobLinkParser Fixture Contract

Structured parser fixture metadata lives in `examples/job-links/*.jsonl`, including `boss-zhipin.jsonl`, `company-careers.jsonl`, and `shared-links.jsonl`. Each line is one JSONL object so contributors can append a new deterministic input without rewriting a large fixture file.

Each parser fixture should define `id`, `input_url`, `platform`, `source_type`, `company_name`, `job_title`, optional `city`, inline `jd_text` or a `jd_fixture` reference, extracted `skills`, and `public_evidence=false`.

Use fictional `.test` domains or clearly non-sensitive public-style examples. Do not commit real private job leads, cookies, screenshots, recruiter messages, or tokens.

Shared/mobile redirect fixtures should prove canonicalization only when it is deterministic. Otherwise preserve the raw URL and keep the parsed job post as lead context.

Structured parser fixture metadata is not completed-report evidence. Parsed job posts must never satisfy report `sourceUrls`; the intake flow still has to run forced search and attach external public links.

## Adapter Implementation Checklist

- Keep public search queries separate from private resume, transcript, phone, email, and interview-note content unless the user explicitly approves sharing it.
- Return raw candidates only; do not write final summaries inside a retrieval adapter.
- Preserve `query_ids` so the report can explain which query found each source.
- Include stable URLs and avoid sources that cannot be linked.
- Include `published_at` only when it comes from the source or provider metadata.
- Raise `SearchSourceNotConfigured` when credentials, network access, or required setup are missing.
- Raise `TranscriptionProviderNotConfigured` when speech-to-text credentials, endpoint, or transport setup are missing.
- Add a deterministic fixture or mocked test so CI can validate the adapter without live internet access.
- Keep external provider-specific fields under clear names if they are useful for debugging, but do not make the core report depend on one vendor.

## What To Build Next

Good first adapter contributions are small and inspectable:

- More provider-specific parser fixtures with structured expected metadata for each input shape.
- A Boss Zhipin-style parser that extracts stable public fields from shared links when available.
- A `SearchSource` wrapper around a real search API that returns title, URL, snippet, publisher, date, and query IDs.
- A forum or community source that can retrieve interview-report links while respecting platform terms.
- A local transcription adapter that turns short voice notes into text without sending private audio to a remote service.

Each adapter should come with a short README note, a deterministic test, and at least one example result that contains real-looking but non-sensitive source metadata.
