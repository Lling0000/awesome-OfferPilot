# Demo Script

This is the copy-paste smoke path for evaluating OfferPilot from a fresh clone. It uses deterministic mock providers, local fixtures, and fictional data, so it does not require API keys, live scraping, or real candidate information.

Use two terminals from the repository root.

## Terminal 1: Seed And Serve

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e ".[dev]"
offerpilot demo --reset
offerpilot serve --host 127.0.0.1 --port 8000
```

Expected demo output before the server starts:

```text
Demo ready:
  user_id: ...
  resume_id: ...
  application_id: ...
  search_report_id: ...
  intelligence_items: 4
  reminders_created: 2
```

`offerpilot serve` is long-running. Leave Terminal 1 open while you use the app; stop it with `Ctrl-C` when the smoke test is done. The server log should show that Uvicorn is running on `http://127.0.0.1:8000`.

## Browser: Inspect The UI

Open:

```text
http://127.0.0.1:8000
```

Expected UI outcomes:

- `/` shows the OfferPilot dashboard with a demo application, Today reminders, a Daily Intelligence section, and Evidence Reports.
- `/applications` shows the demo `Example Robotics` application in the interview pipeline.
- `/applications/{application_id}` shows interview details plus an Interview Intake form for uploading a recording or pasting notes.
- `/reports/{search_report_id}` shows a source-backed report, top-level source URLs, evidence quality labels, and relevance/freshness/credibility scores.
- `/intelligence` shows four mock public interview signals with company-scale filters.
- `/intelligence/{run_id}` shows worker coverage and retained source URLs for the daily intelligence run.
- `/doctor` shows local readiness checks.

The Daily Intelligence and search evidence in this demo are fixture-backed. They prove the source-backed contract and UI flow; they are not live hiring intelligence.

## Terminal 2: Exercise The CLI

With Terminal 1 still serving the app, activate the same virtual environment in Terminal 2:

```bash
source .venv/bin/activate
curl -s http://127.0.0.1:8000/api/health
offerpilot analyze-link "https://www.zhipin.com/job_detail/example-backend-intern.html"
offerpilot intelligence --role-family backend --city Shanghai
offerpilot doctor --strict-publish
```

Expected command outcomes:

```text
{"ok":true,"service":"offerpilot"}

Job link analyzed:
  company: Example Robotics
  job_title: Backend Engineer Intern
  application_id: ...
  search_report_id: ...
  reminders_created: ...
  sourceUrls:
    - https://example.com/careers/backend-intern
    - https://example.com/blog/backend-intern-interview-notes

Daily intelligence ready:
  agent_run_id: ...
  items: 4
  sourceUrls: 4
```

`offerpilot analyze-link` should create another mock-backed application, forced-search report, source URLs, and reminders. Refresh `/applications`, `/reports/{search_report_id}`, and `/intelligence` in the browser to confirm the new records are visible.

## Optional: Interview Intake Smoke

Open any application page and use Interview Intake. Upload a small recording fixture or paste typed notes such as:

```text
The interviewer asked about SQL indexes, API design, and project tradeoffs.
```

Expected UI outcome: the application page stores transcript text, extracted questions, a single-interview summary, and next-focus items. The mock transcription/analyzer flow is deterministic and local.

## Verify Before Sharing

```bash
ruff format --check .
ruff check .
pytest
offerpilot doctor --strict-publish
```

A shareable demo should keep these green.
