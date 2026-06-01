# Search Source Plugin Example

This directory shows the smallest useful `SearchSource` plugin for OfferPilot.

It does not call a live search API. Instead, it searches a tiny in-memory dataset so contributors can understand the adapter contract without signing up for external services.

## Run It

From the repository root:

```bash
python examples/search-source-plugin/run_example.py
```

Expected behavior:

- `ExampleSearchSource` receives each query-plan item.
- It returns raw candidates with URLs, snippets, source types, publisher names, dates, adapter name, and `query_ids`.
- `MockSearchProvider(sources=[ExampleSearchSource()])` normalizes, deduplicates, scores, and returns source-backed evidence.

## Contract

A search source should expose:

```python
name = "example-source"
source_type = "forum"

def search(self, query: dict) -> list[dict]:
    ...
```

Each returned candidate should include:

- `title`
- `url`
- `snippet`
- `source_type`
- `publisher`
- `published_at`
- `retrieved_by`
- `query_ids`

For a real external provider, raise `SearchSourceNotConfigured` when credentials or network setup are missing. Do not return fake links just to keep a report flowing.

See `docs/adapters.md` for the full adapter guide.
