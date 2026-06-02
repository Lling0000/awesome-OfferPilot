import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from sqlalchemy import inspect, text

from offerpilot.db import make_engine
from offerpilot.reports import ReportValidationError, validate_source_urls


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class ContentRequirement:
    label: str
    markers: tuple[str, ...]


REQUIRED_TABLES = {
    "users",
    "resumes",
    "job_links",
    "applications",
    "interviews",
    "reminders",
    "agent_runs",
    "search_reports",
    "evidence_items",
    "intelligence_items",
}

STRICT_FILES = [
    "pyproject.toml",
    "MANIFEST.in",
    "README.md",
    "LICENSE",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "SUPPORT.md",
    "CODE_OF_CONDUCT.md",
    "CHANGELOG.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/ISSUE_TEMPLATE/provider_adapter.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/workflows/ci.yml",
    ".env.example",
    "examples/reports/job-report-with-sourceUrls.json",
    "examples/reports/daily-intelligence-with-sourceUrls.json",
    "examples/interview-notes/README.md",
    "examples/interview-notes/phone-screen.md",
    "examples/interview-notes/technical-round.md",
    "examples/interview-notes/audio-upload-metadata.json",
    "examples/job-links/boss-zhipin.txt",
    "examples/job-links/company-careers.txt",
    "examples/job-descriptions/backend-platform-jd.txt",
    "examples/job-descriptions/frontend-growth-jd.txt",
    "examples/job-descriptions/data-analytics-jd.txt",
    "examples/job-descriptions/product-operations-jd.txt",
    "docs/architecture.md",
    "docs/demo-script.md",
    "docs/launch-checklist.md",
    "docs/search-and-evidence.md",
    "docs/intelligence.md",
    "docs/adapters.md",
    "docs/privacy.md",
    "assets/architecture.svg",
    "assets/social-card.svg",
    "assets/screenshots/dashboard.png",
    "assets/screenshots/report.png",
    "assets/screenshots/intelligence.png",
    "examples/search-source-plugin/README.md",
    "examples/search-source-plugin/example_source.py",
    "examples/search-source-plugin/run_example.py",
    "examples/transcription-provider-plugin/README.md",
    "examples/transcription-provider-plugin/example_transport.py",
    "examples/transcription-provider-plugin/run_example.py",
]

STRICT_CONTENT_REQUIREMENTS = {
    "pyproject.toml": [
        ContentRequirement(
            "package discovery metadata",
            (
                "keywords = [",
                "classifiers = [",
                "[project.urls]",
                'license = "MIT"',
                'license-files = ["LICENSE"]',
            ),
        ),
        ContentRequirement(
            "supported Python classifiers",
            (
                'requires-python = ">=3.9"',
                "Programming Language :: Python :: 3.9",
                "Programming Language :: Python :: 3.12",
            ),
        ),
    ],
    "MANIFEST.in": [
        ContentRequirement(
            "source distribution asset coverage",
            (
                "recursive-include docs *.md",
                "recursive-include assets *.svg *.png",
                "recursive-include examples *.md *.json *.py *.txt",
            ),
        ),
    ],
    ".github/workflows/ci.yml": [
        ContentRequirement(
            "least-privilege permissions",
            (
                "permissions:",
                "contents: read",
            ),
        ),
        ContentRequirement(
            "Python version matrix",
            (
                "strategy:",
                "matrix:",
                "python-version:",
            ),
        ),
        ContentRequirement(
            "pip cache",
            (
                'cache: "pip"',
                "cache-dependency-path: pyproject.toml",
            ),
        ),
        ContentRequirement(
            "package build validation",
            (
                "python -m build",
                "python -m twine check dist/*",
            ),
        ),
        ContentRequirement(
            "strict publish gate",
            ("offerpilot doctor --strict-publish",),
        ),
    ],
    ".github/PULL_REQUEST_TEMPLATE.md": [
        ContentRequirement(
            "evidence and privacy checklist",
            (
                "sourceUrls",
                "Privacy",
                "offerpilot doctor --strict-publish",
            ),
        ),
    ],
    ".github/ISSUE_TEMPLATE/bug_report.yml": [
        ContentRequirement(
            "safe bug report fields",
            (
                "OfferPilot Version Or Commit",
                "Local Checks",
                "Privacy Check",
            ),
        ),
    ],
    ".github/ISSUE_TEMPLATE/feature_request.yml": [
        ContentRequirement(
            "evidence-aware feature request fields",
            (
                "Success Criteria",
                "Evidence And Source URLs",
                "unsupported claims",
            ),
        ),
    ],
    ".github/ISSUE_TEMPLATE/provider_adapter.yml": [
        ContentRequirement(
            "adapter contract fields",
            (
                "Required Setup",
                "Fail-Closed Behavior",
                "Tests Or Fixtures",
                "sourceUrls",
            ),
        ),
    ],
    ".github/ISSUE_TEMPLATE/config.yml": [
        ContentRequirement(
            "support and private security links",
            (
                "Support and troubleshooting",
                "/security/advisories/new",
            ),
        ),
    ],
    "SUPPORT.md": [
        ContentRequirement(
            "support diagnostics",
            (
                "offerpilot doctor --strict-publish",
                "sourceUrls",
                "Do not include real resumes",
            ),
        ),
    ],
    "CODE_OF_CONDUCT.md": [
        ContentRequirement(
            "community and privacy standards",
            (
                "Expected behavior",
                "Unacceptable behavior",
                "private candidate data",
            ),
        ),
    ],
    "CHANGELOG.md": [
        ContentRequirement(
            "release tracking sections",
            (
                "## [Unreleased]",
                "## [0.1.0] - 2026-06-01",
            ),
        ),
    ],
    "SECURITY.md": [
        ContentRequirement(
            "private vulnerability reporting",
            (
                "Please do not open a public issue",
                "Do not include real resumes",
                "Privacy Incidents",
            ),
        ),
    ],
    "CONTRIBUTING.md": [
        ContentRequirement(
            "evidence-first contribution rules",
            (
                "sourceUrls",
                "Privacy Rules",
                "Run `offerpilot doctor --strict-publish`",
            ),
        ),
    ],
    ".env.example": [
        ContentRequirement(
            "provider setup placeholders",
            (
                "SEARCH_PROVIDER_API_KEY=",
                "SEARCH_PROVIDER_ENDPOINT=",
                "TRANSCRIPTION_PROVIDER_API_KEY=",
                "TRANSCRIPTION_PROVIDER_ENDPOINT=",
            ),
        ),
    ],
    "docs/adapters.md": [
        ContentRequirement(
            "external provider skeletons",
            (
                "ExternalSearchAPISource",
                "SEARCH_PROVIDER_API_KEY",
                "SEARCH_PROVIDER_ENDPOINT",
                "ExternalTranscriptionProvider",
                "TRANSCRIPTION_PROVIDER_API_KEY",
                "TRANSCRIPTION_PROVIDER_ENDPOINT",
            ),
        ),
    ],
    "docs/search-and-evidence.md": [
        ContentRequirement(
            "evidence display and unknowns guidance",
            (
                "Source Quality Display",
                "Unsupported claims should become `unknowns`",
                "score reasons",
            ),
        ),
    ],
    "examples/search-source-plugin/README.md": [
        ContentRequirement(
            "fixture-backed search source example",
            (
                "It does not call a live search API",
                "at least two deterministic raw candidates",
                "query_ids",
            ),
        ),
    ],
    "examples/interview-notes/README.md": [
        ContentRequirement(
            "safe interview fixture policy",
            (
                "fictional and safe to commit",
                "metadata for a pretend uploaded audio file",
                "Interview transcripts must not appear in `sourceUrls`",
            ),
        ),
    ],
    "examples/transcription-provider-plugin/README.md": [
        ContentRequirement(
            "fixture-backed transcription provider example",
            (
                "ExternalTranscriptionProvider",
                "private_user_context",
                "sourceUrls: []",
            ),
        ),
    ],
    "docs/privacy.md": [
        ContentRequirement(
            "interview fixture privacy policy",
            (
                "Interview Fixtures",
                "metadata-only examples",
                "must not appear in `sourceUrls`",
            ),
        ),
    ],
}


def run_doctor(
    database_url: Optional[str] = None,
    strict_publish: bool = False,
    root: Path = Path("."),
) -> List[Check]:
    checks = [
        Check(
            "python_version",
            sys.version_info >= (3, 9),
            f"Python {sys.version_info.major}.{sys.version_info.minor}",
        )
    ]

    try:
        engine = make_engine(database_url)
        with engine.connect() as conn:
            conn.execute(text("select 1"))
        checks.append(Check("sqlite_connectivity", True, "SQLite connection works."))
        tables = set(inspect(engine).get_table_names())
        missing = sorted(REQUIRED_TABLES - tables)
        checks.append(
            Check(
                "database_schema",
                not missing,
                "All required tables exist."
                if not missing
                else "Missing tables: " + ", ".join(missing),
            )
        )
    except Exception as exc:
        checks.append(Check("sqlite_connectivity", False, f"Database error: {exc}"))
        checks.append(Check("database_schema", False, "Could not inspect database schema."))

    try:
        validate_source_urls(["https://example.com/evidence"])
        try:
            validate_source_urls([])
            checks.append(Check("source_urls_required", False, "Empty sourceUrls were accepted."))
        except ReportValidationError:
            checks.append(
                Check("source_urls_required", True, "Completed reports require at least one URL.")
            )
    except Exception as exc:
        checks.append(Check("source_urls_required", False, f"Validation failed: {exc}"))

    if strict_publish:
        checks.extend(_strict_file_checks(root))

    return checks


def _strict_file_checks(root: Path) -> Iterable[Check]:
    for rel in STRICT_FILES:
        path = root / rel
        ok = path.exists() and path.stat().st_size > 0
        yield Check(f"file:{rel}", ok, "present" if ok else "missing or empty")
    for rel, requirements in STRICT_CONTENT_REQUIREMENTS.items():
        path = root / rel
        if not path.exists():
            yield Check(f"content:{rel}", False, "missing file")
            continue
        try:
            contents = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            yield Check(f"content:{rel}", False, f"could not read UTF-8 content: {exc}")
            continue
        missing = [
            requirement.label
            for requirement in requirements
            if not all(marker in contents for marker in requirement.markers)
        ]
        detail = (
            "required publish markers present"
            if not missing
            else "missing publish markers: " + ", ".join(missing)
        )
        yield Check(f"content:{rel}", not missing, detail)


def format_checks(checks: Iterable[Check]) -> str:
    lines = []
    for check in checks:
        mark = "OK" if check.ok else "FAIL"
        lines.append(f"[{mark}] {check.name}: {check.detail}")
    return "\n".join(lines)


def checks_ok(checks: Iterable[Check]) -> bool:
    return all(check.ok for check in checks)
