# Daily Intelligence

OfferPilot treats interview intelligence as scheduled forced search, not as an unsourced agent summary. A daily brief is complete only when it preserves the query plan, the worker coverage, the retained source URLs, and the labels used to organize the findings.

The current implementation is deterministic and mock-backed. It demonstrates the product and storage contract without pretending to perform live web collection.

## What It Collects

The daily brief sends narrow retrieval workers across four company-scale buckets:

| Company scale | Meaning in the MVP | Example signals |
| --- | --- | --- |
| `国央企` | State-owned or central-enterprise style opportunities in candidate language. | GD, stability questions, public-service scenarios, structured communication. |
| `大厂` | Large technology companies or big-platform hiring processes. | Manager round, project ownership, cross-team collaboration, metrics. |
| `中厂` | Mid-market companies with structured technical interviews. | Technical deep dives, caching, SQL indexes, async workflow questions. |
| `小厂` | Small teams, startups, or founder-led hiring loops. | Founder round, business understanding, role flexibility, shipping tradeoffs. |

These labels are job-search context labels, not legal or financial classifications. Production adapters should attach evidence and confidence to scale labels, and should use `unknown` when public evidence is weak.

## Worker Contract

Each daily intelligence run creates a parent `AgentRun` with `run_type="daily_intelligence"` and child runs for the narrow workers:

- `state-owned-scout`
- `big-tech-scout`
- `mid-market-scout`
- `small-team-scout`

Each worker returns linked findings only. A finding must include:

- `company_name`
- `company_scale`
- `role_family`
- `signal_type`
- `title`
- `summary`
- `source_url`
- `source_type`
- `publisher`
- `relevance_score`
- `tags`

Every completed finding must have a valid `http://` or `https://` `source_url`.

## Interview Process Signals

OfferPilot tracks process signals rather than making private or over-precise claims:

- `group_discussion`: GD or group discussion format.
- `manager_round`: hiring-manager or business-owner round.
- `technical_interview`: technical topics and project review.
- `founder_round`: founder or small-team final round.
- `business_context`: product, domain, or business scenario signal.
- `hiring_signal`: public evidence that changes preparation priority.

Public interviewer or manager information should appear only when it is explicitly available from source URLs. Otherwise it belongs in unknowns, not in final claims.

## Source Boundaries

Daily intelligence may use public job links, public company pages, public interview reports, news, and community posts where allowed. It must not leak private resume text, interview transcripts, phone numbers, email, recruiter messages, or private notes into public search queries without explicit user approval.

Social and forum findings are useful signals, but they are not automatically facts. Production scoring should downgrade weak or anonymous sources and mark them for corroboration.

## Current CLI And API

Run a local mock-backed brief:

```bash
offerpilot intelligence --role-family backend --city Shanghai
```

API:

```text
POST /api/intelligence/daily
GET  /api/intelligence
GET  /api/intelligence/runs
GET  /api/intelligence/{run_id}
```

Web:

```text
GET  /intelligence
GET  /intelligence/{run_id}
```

The list page supports company-scale and signal-type filters. The detail page shows the parent brief, worker coverage, retained findings, and source URLs.

## Example Output Shape

```json
{
  "agent_run_id": "run_123",
  "created": 4,
  "agentRuns": [
    {
      "name": "big-tech-scout",
      "status": "succeeded",
      "query": "大厂 backend 校招 面经 经理面 业务面 Shanghai 2026",
      "found": 1,
      "sourceUrls": [
        "https://example.com/intelligence/big-tech-manager-round-2026"
      ]
    }
  ],
  "sourceUrls": [
    "https://example.com/intelligence/state-owned-gd-2026"
  ],
  "digest": {
    "by_company_scale": {
      "国央企": 1,
      "大厂": 1,
      "中厂": 1,
      "小厂": 1
    },
    "unknowns": [
      "Fixture data cannot prove current live hiring process.",
      "Social/forum signals need corroboration before becoming preparation claims."
    ],
    "manager_or_gd_matches": [
      "国央企数字化岗 GD 讨论开始更多围绕稳定性与公共服务场景"
    ]
  }
}
```

This is a fixture contract. Real adapters must refresh source URLs before presenting a live brief.
