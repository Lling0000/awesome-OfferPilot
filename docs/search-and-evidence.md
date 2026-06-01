# Search and Evidence

OfferPilot uses a forced-search workflow for job research. The core rule is simple: no source, no sourced claim.

This document defines the expected query-planning, evidence-normalization, scoring, and display contract for reports, examples, and future implementation.

## Provider Adapters

OfferPilot should keep evidence collection modular through provider adapters. Each adapter owns one job and returns structured data that can be inspected, tested, and replaced.

For implementation details and a runnable plugin example, see [Adapter Guide](adapters.md) and [`examples/search-source-plugin`](../examples/search-source-plugin).

| Adapter | Responsibility | Must return | Must not do |
| --- | --- | --- | --- |
| `JobLinkParser` | Parse a job URL, company careers page, or pasted JD into a normalized opportunity. | Job title, company, location, role text, canonical URL when available, parser confidence. | Invent public facts or claim that parsing is evidence. |
| `QueryPlanner` | Turn the parsed opportunity and user-approved context into a bounded search plan. | Query objects, intent labels, required source types, privacy notes, and execution priority. | Leak private resume, transcript, email, phone, or interview-note text into public queries without consent. |
| `SearchProvider` | Execute the approved query plan against external search providers or controlled mocks. | Raw search results, source URLs, snippets when available, query IDs, and retrieval timestamps. | Treat raw search snippets as normalized evidence or perform final report analysis. |
| `SearchSource` | A pluggable retrieval unit used by a `SearchProvider`. | Raw source candidates for one query-plan item, including `query_ids`, `retrieved_by`, URL, title, and snippet. | Pretend to search when credentials or network access are missing. |
| `EvidenceNormalizer` | Convert raw search results and parsed job data into canonical evidence records. | Deduplicated `EvidenceItem` records, canonical URLs, source types, score inputs, and normalization notes. | Merge conflicting facts silently or hide why a source was downgraded. |
| `TranscriptionProvider` | Convert voice notes, interview recordings, or uploaded audio into text. | Transcript text, timestamps when available, language hints, confidence or quality notes. | Treat transcript content as public evidence. |
| `InterviewAnalyzer` | Generate prep reports from the job, resume, notes, transcript, and evidence set. | Summary, risks, unknowns, recommended next actions, source references. | Produce sourced claims without `sourceIds` or top-level `sourceUrls`. |

The default implementation can be deterministic and mock-friendly. Production adapters should be swappable by configuration, but they must preserve the same evidence contract so the UI, CLI, tests, and reports do not depend on a single vendor.

## Forced Search Contract

When a user submits a job link or asks for role or company research, OfferPilot must:

1. Treat the user input as a lead, not a final truth.
2. Build an explicit query plan before running external search.
3. Run external search before producing a research report.
4. Preserve every useful source URL.
5. Normalize and deduplicate sources that repeat the same job post, company profile, or syndicated content.
6. Score relevance, freshness, and credibility for every retained source.
7. Separate sourced facts from user-provided context and model inference.
8. Return a report with a top-level `sourceUrls` field.

The model should not answer from memory alone when the task is job research.

## Query Plan

The query plan is the auditable bridge between a user's job lead and external search. It should be stored or returned with the report so reviewers can see what was searched, why it was searched, and what privacy constraints were applied.

A query plan should include:

- `queryId`: stable ID used to connect search results back to the planned query.
- `query`: the exact search text that may be sent to a provider.
- `intent`: why the query exists, such as `original_listing`, `company_official`, `recent_news`, `interview_process`, `role_topics`, or `risk_check`.
- `requiredSourceTypes`: preferred source categories for this query.
- `priority`: execution priority when search budget is limited.
- `privacyLevel`: whether the query uses only public job context or needs user consent.
- `notes`: short rationale, constraints, or known exclusions.

Example:

```json
{
  "queryId": "qry_001",
  "query": "ExampleCo backend platform intern careers 2026",
  "intent": "company_official",
  "requiredSourceTypes": ["company_site", "job_post"],
  "priority": 1,
  "privacyLevel": "public_job_context",
  "notes": "Find an official or near-official version of the pasted job lead."
}
```

The planner should generate multiple focused queries instead of one broad prompt-like query. A good plan normally covers the original listing, official company material, recent company context, interview process signals, role-specific technical topics, and risk checks for stale or duplicate postings.

## Source Types

Common source types include:

- `job_post`: the original job post or mirrored listing.
- `company_site`: official company website, careers page, blog, or press page.
- `professional_profile`: LinkedIn-like or public profile pages where allowed.
- `interview_report`: public interview experience or forum thread.
- `news`: reputable news, funding, acquisition, or layoff reporting.
- `community`: forum, social post, or candidate discussion.
- `registry`: public company, funding, or legal registry.
- `other`: source that does not fit another type.

Source type is not the same as trust. A source still needs relevance, freshness, and credibility scoring.

## Evidence Normalizer

The Evidence Normalizer converts raw search results into report-safe `EvidenceItem` records. Its job is to make source handling consistent before analysis starts.

The normalizer should:

- Canonicalize URLs by removing tracking parameters where safe.
- Group duplicates, mirrors, and syndicated copies under one canonical source.
- Preserve `rawUrl` or `alternateUrls` when the original retrieval path matters.
- Assign `sourceType` from observable properties, not from model guesswork alone.
- Extract or estimate `publishedAt` only when the page or provider supplies a credible date.
- Attach the `queryIds` that found the source.
- Keep normalization notes for conflicts, stale pages, missing titles, or low-confidence classification.
- Produce scoring inputs but avoid writing final prose claims.

If two sources conflict, the normalizer should preserve both records and mark the conflict for the analyzer. It should not collapse disagreement into a single averaged fact.

## Evidence Object

Future reports should use an evidence object close to this shape:

```json
{
  "id": "src_001",
  "url": "https://example.com/jobs/backend-platform-intern",
  "canonicalUrl": "https://example.com/jobs/backend-platform-intern",
  "alternateUrls": [],
  "title": "Backend Platform Intern",
  "sourceType": "job_post",
  "retrievedAt": "2026-06-01T09:00:00Z",
  "publishedAt": null,
  "queryIds": ["qry_001"],
  "scores": {
    "relevance": 0.91,
    "freshness": 0.76,
    "credibility": 0.82,
    "overall": 0.84
  },
  "scoreReasons": {
    "relevance": "Exact role family and company match.",
    "freshness": "Retrieved today, but no publication date was found.",
    "credibility": "Original job-post-like source with a stable URL."
  },
  "qualityLabel": "strong",
  "notes": "Original job-post-like source used for sample evidence."
}
```

Report sections can then reference evidence by ID:

```json
{
  "claim": "The role emphasizes backend APIs and data pipelines.",
  "sourceIds": ["src_001", "src_002"],
  "confidence": "medium"
}
```

## Required Report Fields

A research report should include:

- `generatedAt`
- `input`
- `queryPlan`
- `forcedSearch`
- `sourceUrls`
- `evidenceItems`
- `summary`
- `risks`
- `unknowns`
- `recommendedNextActions`

The `sourceUrls` field should be easy to find at the top level. Other sections may use source IDs to avoid repeating long URLs.

## Source Scoring

OfferPilot uses three primary source scores. Each score is a number from `0.00` to `1.00`, where higher means stronger evidence for this report.

| Score | Meaning | High signal | Low signal |
| --- | --- | --- | --- |
| `relevance` | How directly the source answers this user's job, company, role, location, or interview question. | Exact company and role match, original listing, role-family interview details. | Generic career advice, unrelated office, different seniority, old role family. |
| `freshness` | How likely the information is still current. | Recently published, recently retrieved official page, active listing, current news. | Old interview reports, expired posts, no dates, stale mirrors. |
| `credibility` | How much trust the source deserves for the specific claim being made. | Official company pages, reputable reporting, direct public artifacts, corroborated sources. | Anonymous claims, scraped mirrors, affiliate pages, unsupported social posts. |

`overall` can be computed for sorting and display, but it should not hide the three component scores. A source can be highly credible but stale, or fresh but weakly relevant. The UI and report page should make those differences visible.

Suggested labels:

- `excellent`: overall score is at least `0.90`, with no weak component.
- `strong`: overall score is at least `0.75`, and the source can support normal report claims.
- `limited`: overall score is at least `0.50`, but the source needs cautious wording or corroboration.
- `background`: overall score is below `0.50`; use only for context, not central claims.
- `do_not_use`: severe credibility, privacy, spam, or mismatch issues.

The analyzer should use score reasons when wording claims. For example, an older interview report can support a historical note, but it should not be phrased as the current interview process unless newer sources corroborate it.

## Source Quality Display

The report page should show source quality in a way that helps users inspect the evidence quickly. For each evidence item, display:

- Source title and domain.
- Source type.
- Retrieval date and publication date when available.
- Relevance, freshness, and credibility scores.
- Overall quality label.
- Short score reasons or warnings.
- Source URL.

Recommended UI behavior:

- Sort sources by `overall` score by default, with official and exact-match sources near the top.
- Show low freshness or low credibility warnings visibly.
- Keep `sourceUrls` accessible even when the report summary is collapsed.
- Let report sections reference source IDs so users can jump from a claim to its supporting evidence.
- Avoid hiding weak sources entirely; downgraded sources are useful for explaining uncertainty and conflicts.

## CLI: `analyze-link`

`offerpilot analyze-link` is the command-line expression of the forced-search workflow. It should be useful for demos, CI smoke checks, and power users who want the fastest path from job link to evidence-backed interview prep.

Example:

```bash
offerpilot analyze-link "https://example.com/jobs/backend-platform-intern"
offerpilot analyze-link "https://example.com/jobs/backend-platform-intern" --json
offerpilot analyze-link "https://example.com/jobs/backend-platform-intern" --resume-id "<resume_id from offerpilot demo output>"
```

Expected execution flow:

1. `JobLinkParser` normalizes the input into a structured opportunity.
2. `QueryPlanner` creates a privacy-aware query plan.
3. `SearchProvider` executes planned queries and returns raw results.
4. `EvidenceNormalizer` deduplicates, canonicalizes, types, and scores evidence.
5. OfferPilot stores the job/application context, query plan, evidence scores, and source URLs.
6. `InterviewAnalyzer` creates the prep report with explicit `sourceIds`.
7. The CLI prints a concise summary, risks, unknowns, next actions, source scores, and `sourceUrls`.

The command should fail closed when evidence is missing. A successful `analyze-link` run means the report is source-backed; a parser-only result is useful draft context, but it is not a completed research report.

## Search Source Plugins

`SearchSource` is the smallest retrieval extension point. A source receives one query-plan item and returns raw candidates. The default `LocalFixtureSearchSource` makes the project runnable without keys. Future sources can wrap a search API, forum adapter, social-search adapter, official-site crawler, or controlled local index.

A source should return raw data only:

- `title`
- `url`
- `snippet`
- `source_type`
- `publisher`
- `published_at`
- `retrieved_by`
- `query_ids`

It should not write final summaries, assign final evidence scores, or decide whether a report is complete. That belongs to the normalizer and report layer.

Unconfigured external sources must fail closed with a clear setup error. This keeps demos honest: missing credentials should never become fake source-backed evidence.

## Scoring Rubric

Score sources against these dimensions:

- Relevance: directly about this company, role, location, or hiring process.
- Freshness: recently published or still likely valid.
- Credibility: official source, reputable publication, direct participant, or corroborated public artifact.
- Specificity: concrete details beat generic advice.
- Corroboration: repeated by independent sources.
- Risk: unverified claims, anonymous reports, affiliate content, outdated posts, copied listings, or privacy-sensitive content.

Suggested scale:

- `0.90-1.00`: official or highly authoritative and directly relevant.
- `0.70-0.89`: useful, recent, and likely reliable.
- `0.50-0.69`: plausible but partial, old, or indirect.
- `0.20-0.49`: weak signal, treat as background only.
- `0.00-0.19`: do not use for claims.

## Conflict Handling

Job data often conflicts across sources. OfferPilot should keep the conflict visible.

Examples:

- If the job post says remote but the company page says hybrid, mark work mode as `conflicting`.
- If interview reports are older than one year, label them as historical.
- If compensation appears only in anonymous posts, label it as unverified and avoid strong claims.

## Generated Text Rules

Report prose should follow these rules:

- Use sourced facts only when evidence exists.
- Label user-provided facts as user-provided.
- Label model interpretations as inferences.
- Avoid fake precision.
- Prefer "unknown" over guessing.
- Preserve source URLs even if the final summary is short.

## Privacy During Search

External search should use the minimum necessary context. A query should not expose a user's full resume, phone number, email, private interview notes, or voice transcript unless the user explicitly approves that disclosure.

Good query:

```text
ExampleCo backend platform intern interview process 2026
```

Bad query:

```text
Alex Chen alex@example.com ExampleCo backend platform intern phone screen notes
```

## Example Search Plan

For a Boss Zhipin job link, a useful search plan might include:

- Original listing title and company query.
- Company official careers page query.
- Recent company news query.
- Public interview experiences query for the company and role family.
- Role-specific technical topics query.
- Risk-check query for duplicate, expired, or suspicious listings.

The final report should keep the input job link and all external evidence links in `sourceUrls`.
