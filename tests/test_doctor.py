from pathlib import Path

from offerpilot.db import reset_db
from offerpilot.doctor import STRICT_FILES, _strict_file_checks, checks_ok, run_doctor


def test_doctor_passes_after_schema_init(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path}/offerpilot.db"
    reset_db(db_url)
    checks = run_doctor(database_url=db_url)
    assert checks_ok(checks)


def test_doctor_detects_missing_schema(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path}/missing.db"
    checks = run_doctor(database_url=db_url)
    assert not checks_ok(checks)
    assert any(check.name == "database_schema" and not check.ok for check in checks)


def test_strict_publish_checks_adapter_docs_and_examples() -> None:
    assert "pyproject.toml" in STRICT_FILES
    assert "MANIFEST.in" in STRICT_FILES
    assert ".github/workflows/ci.yml" in STRICT_FILES
    assert "SUPPORT.md" in STRICT_FILES
    assert "CODE_OF_CONDUCT.md" in STRICT_FILES
    assert "CHANGELOG.md" in STRICT_FILES
    assert "docs/adapters.md" in STRICT_FILES
    assert "docs/intelligence.md" in STRICT_FILES
    assert "docs/demo-script.md" in STRICT_FILES
    assert "docs/launch-checklist.md" in STRICT_FILES
    assert ".env.example" in STRICT_FILES
    assert "examples/search-source-plugin/README.md" in STRICT_FILES
    assert "examples/search-source-plugin/example_source.py" in STRICT_FILES
    assert "examples/search-source-plugin/run_example.py" in STRICT_FILES
    assert "examples/interview-notes/README.md" in STRICT_FILES
    assert "examples/interview-notes/phone-screen.md" in STRICT_FILES
    assert "examples/interview-notes/technical-round.md" in STRICT_FILES
    assert "examples/interview-notes/audio-upload-metadata.json" in STRICT_FILES
    assert "examples/reports/daily-intelligence-with-sourceUrls.json" in STRICT_FILES
    assert "examples/job-links/boss-zhipin.txt" in STRICT_FILES
    assert "examples/job-links/boss-zhipin.jsonl" in STRICT_FILES
    assert "examples/job-links/company-careers.txt" in STRICT_FILES
    assert "examples/job-links/company-careers.jsonl" in STRICT_FILES
    assert "examples/job-links/shared-links.txt" in STRICT_FILES
    assert "examples/job-links/shared-links.jsonl" in STRICT_FILES
    assert "examples/job-descriptions/backend-platform-jd.txt" in STRICT_FILES
    assert "examples/job-descriptions/frontend-growth-jd.txt" in STRICT_FILES
    assert "examples/job-descriptions/data-analytics-jd.txt" in STRICT_FILES
    assert "examples/job-descriptions/product-operations-jd.txt" in STRICT_FILES
    assert "examples/job-descriptions/pasted-jds.jsonl" in STRICT_FILES
    assert "assets/screenshots/dashboard.png" in STRICT_FILES
    assert "assets/screenshots/report.png" in STRICT_FILES
    assert "assets/screenshots/intelligence.png" in STRICT_FILES
    assert ".github/PULL_REQUEST_TEMPLATE.md" in STRICT_FILES
    assert ".github/ISSUE_TEMPLATE/bug_report.yml" in STRICT_FILES
    assert ".github/ISSUE_TEMPLATE/feature_request.yml" in STRICT_FILES
    assert ".github/ISSUE_TEMPLATE/provider_adapter.yml" in STRICT_FILES


def test_strict_publish_checks_required_content_markers() -> None:
    checks = list(_strict_file_checks(root=Path(".")))
    content_checks = [check for check in checks if check.name.startswith("content:")]
    assert content_checks
    assert checks_ok(content_checks)


def test_strict_publish_rejects_placeholder_publish_files(tmp_path) -> None:
    for rel in STRICT_FILES:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("placeholder\n", encoding="utf-8")

    checks = {check.name: check for check in _strict_file_checks(tmp_path)}

    assert not checks["content:pyproject.toml"].ok
    assert "package discovery metadata" in checks["content:pyproject.toml"].detail
    assert not checks["content:.github/workflows/ci.yml"].ok
    assert "Python version matrix" in checks["content:.github/workflows/ci.yml"].detail
    assert not checks["content:examples/job-links/boss-zhipin.jsonl"].ok
    assert (
        "structured Boss-style fixture metadata"
        in checks["content:examples/job-links/boss-zhipin.jsonl"].detail
    )
    assert not checks["content:examples/job-links/company-careers.jsonl"].ok
    assert (
        "structured company and mirror fixture metadata"
        in checks["content:examples/job-links/company-careers.jsonl"].detail
    )
    assert not checks["content:examples/job-links/shared-links.jsonl"].ok
    assert (
        "structured job-link fixture metadata"
        in checks["content:examples/job-links/shared-links.jsonl"].detail
    )
    assert not checks["content:examples/job-descriptions/pasted-jds.jsonl"].ok
    assert (
        "structured pasted JD fixture metadata"
        in checks["content:examples/job-descriptions/pasted-jds.jsonl"].detail
    )
