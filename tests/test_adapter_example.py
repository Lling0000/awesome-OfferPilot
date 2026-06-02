import importlib.util
import subprocess
import sys
from pathlib import Path

from offerpilot.providers import MockSearchProvider
from offerpilot.reports import validate_source_urls
from offerpilot.search import normalize_evidence_items

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_DIR = ROOT / "examples" / "search-source-plugin"


def load_example_source():
    module_path = EXAMPLE_DIR / "example_source.py"
    spec = importlib.util.spec_from_file_location("example_source", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ExampleSearchSource


def test_example_search_source_returns_traceable_candidates() -> None:
    ExampleSearchSource = load_example_source()
    source = ExampleSearchSource()

    results = source.search(
        {
            "id": "company-role-interview",
            "query": "Example Robotics Backend Engineer Intern 面经",
            "source_focus": "forum",
        }
    )

    assert len(results) >= 2
    for item in results:
        assert item["title"]
        assert item["url"].startswith("https://")
        assert item["snippet"]
        assert item["publisher"]
        assert item["published_at"]
        assert validate_source_urls([item["url"]])
        assert item["retrieved_by"] == "example-source"
        assert item["query_ids"] == ["company-role-interview"]
        assert item["source_type"] in {"forum", "official"}


def test_example_candidates_can_be_normalized_and_scored() -> None:
    ExampleSearchSource = load_example_source()
    source = ExampleSearchSource()
    raw_items = source.search(
        {
            "id": "company-role-interview",
            "query": "Example Robotics Backend Engineer Intern 面经",
            "intent": "Find public interview reports.",
            "source_focus": "forum",
        }
    )

    evidence = normalize_evidence_items(
        raw_items,
        company_name="Example Robotics",
        job_title="Backend Engineer Intern",
        skills=["Python", "FastAPI", "SQL"],
    )

    assert evidence
    assert evidence[0]["canonical_url"]
    assert evidence[0]["relevance_score"] > 0
    assert evidence[0]["freshness_score"] > 0
    assert evidence[0]["credibility_score"] > 0
    assert evidence[0]["overall_score"] > 0
    assert evidence[0]["quality_label"] in {
        "excellent",
        "strong",
        "limited",
        "background",
        "do_not_use",
    }
    assert evidence[0]["score_reasons"]
    assert evidence[0]["usage_guidance"]


def test_example_source_works_with_mock_search_provider() -> None:
    ExampleSearchSource = load_example_source()

    result = MockSearchProvider(sources=[ExampleSearchSource()]).search(
        "Example Robotics",
        "Backend Engineer Intern",
        "Python FastAPI SQL Redis async workflows",
    )

    assert result["source_urls"]
    assert result["search_coverage"]["search_sources"] == ["example-source"]
    assert result["evidence"][0]["overall_score"] > 0
    assert result["evidence"][0]["query_ids"]


def test_example_runner_outputs_source_urls() -> None:
    completed = subprocess.run(
        [sys.executable, str(EXAMPLE_DIR / "run_example.py")],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    assert "sourceUrls" in completed.stdout
    assert "example-source" in completed.stdout
