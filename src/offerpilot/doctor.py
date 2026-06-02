import json
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


@dataclass(frozen=True)
class JsonlFixtureSpec:
    required_fields: tuple[str, ...]
    expected_values: dict
    url_fields: tuple[str, ...] = ()
    empty_source_urls: bool = False
    references: tuple[tuple[str, str], ...] = ()
    count_pairs: tuple[tuple[str, str], ...] = ()


JSONL_URL_FIELDS = ("sourceUrls", "retained_sourceUrls")
JSONL_FIXTURE_SPECS = {
    "examples/reports/report-fixtures.jsonl": JsonlFixtureSpec(
        required_fields=(
            "id",
            "fixture_type",
            "report_fixture",
            "report_type",
            "retained_sourceUrls",
            "requires_top_level_sourceUrls",
            "expected_evidence_quality_labels",
            "weak_or_missing_evidence_policy",
            "sourceUrls_refresh_required",
            "public_evidence",
            "completed_report_requirement",
        ),
        expected_values={
            "fixture_type": "source_backed_report_case",
            "requires_top_level_sourceUrls": True,
            "sourceUrls_refresh_required": True,
            "public_evidence": True,
        },
        url_fields=("retained_sourceUrls",),
        references=(("report_fixture", ""),),
        count_pairs=(("retained_sourceUrls_count", "retained_sourceUrls"),),
    ),
    "examples/intelligence/daily-intelligence.jsonl": JsonlFixtureSpec(
        required_fields=(
            "id",
            "fixture_type",
            "query_id",
            "agent",
            "company_scale",
            "signal_type",
            "source_type",
            "sourceUrls",
            "privacy",
            "public_evidence",
            "completed_report_requirement",
        ),
        expected_values={
            "fixture_type": "daily_intelligence_case",
            "privacy": "public_source_signal",
            "public_evidence": True,
            "sourceUrls_refresh_required": True,
        },
        url_fields=("sourceUrls",),
    ),
    "examples/interview-notes/interview-notes.jsonl": JsonlFixtureSpec(
        required_fields=(
            "id",
            "file_path",
            "input_type",
            "source_type",
            "privacy",
            "public_evidence",
            "sourceUrls",
            "completed_report_requirement",
        ),
        expected_values={
            "input_type": "typed_interview_note",
            "source_type": "interview_note",
            "privacy": "private_user_context",
            "public_evidence": False,
        },
        empty_source_urls=True,
        references=(("file_path", ""),),
    ),
    "examples/reminders/daily-reminders.jsonl": JsonlFixtureSpec(
        required_fields=(
            "id",
            "fixture_type",
            "application_state",
            "missing_fields",
            "expected_reminder_type",
            "safe_without_private_sourceUrls",
            "privacy",
            "public_evidence",
            "sourceUrls",
            "completed_report_requirement",
        ),
        expected_values={
            "fixture_type": "daily_reminder_case",
            "privacy": "workflow_metadata",
            "public_evidence": False,
            "safe_without_private_sourceUrls": True,
        },
        empty_source_urls=True,
    ),
    "examples/job-links/boss-zhipin.jsonl": JsonlFixtureSpec(
        required_fields=(
            "id",
            "input_url",
            "platform",
            "source_type",
            "company_name",
            "job_title",
            "city",
            "jd_text",
            "skills",
            "public_evidence",
            "completed_report_requirement",
        ),
        expected_values={"public_evidence": False},
        empty_source_urls=True,
    ),
    "examples/job-links/company-careers.jsonl": JsonlFixtureSpec(
        required_fields=(
            "id",
            "input_url",
            "platform",
            "source_type",
            "company_name",
            "job_title",
            "city",
            "jd_text",
            "skills",
            "public_evidence",
            "completed_report_requirement",
        ),
        expected_values={"public_evidence": False},
        empty_source_urls=True,
    ),
    "examples/job-links/shared-links.jsonl": JsonlFixtureSpec(
        required_fields=(
            "id",
            "input_url",
            "platform",
            "source_type",
            "company_name",
            "job_title",
            "city",
            "jd_text",
            "skills",
            "public_evidence",
            "completed_report_requirement",
        ),
        expected_values={"public_evidence": False},
        empty_source_urls=True,
    ),
    "examples/job-descriptions/pasted-jds.jsonl": JsonlFixtureSpec(
        required_fields=(
            "id",
            "jd_fixture",
            "input_type",
            "source_type",
            "privacy",
            "public_evidence",
            "completed_report_requirement",
        ),
        expected_values={
            "input_type": "pasted_jd",
            "source_type": "pasted_jd",
            "privacy": "private_user_context",
            "public_evidence": False,
        },
        empty_source_urls=True,
        references=(("jd_fixture", "examples/job-descriptions"),),
    ),
}


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
    "examples/reports/README.md",
    "examples/reports/report-fixtures.jsonl",
    "examples/reports/job-report-with-sourceUrls.json",
    "examples/reports/daily-intelligence-with-sourceUrls.json",
    "examples/intelligence/README.md",
    "examples/intelligence/daily-intelligence.jsonl",
    "examples/interview-notes/README.md",
    "examples/interview-notes/interview-notes.jsonl",
    "examples/interview-notes/phone-screen.md",
    "examples/interview-notes/technical-round.md",
    "examples/interview-notes/audio-upload-metadata.json",
    "examples/reminders/README.md",
    "examples/reminders/daily-reminders.jsonl",
    "examples/job-links/boss-zhipin.txt",
    "examples/job-links/boss-zhipin.jsonl",
    "examples/job-links/company-careers.txt",
    "examples/job-links/company-careers.jsonl",
    "examples/job-links/shared-links.txt",
    "examples/job-links/shared-links.jsonl",
    "examples/job-descriptions/backend-platform-jd.txt",
    "examples/job-descriptions/frontend-growth-jd.txt",
    "examples/job-descriptions/data-analytics-jd.txt",
    "examples/job-descriptions/product-operations-jd.txt",
    "examples/job-descriptions/pasted-jds.jsonl",
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
                "recursive-include examples *.md *.json *.jsonl *.py *.txt",
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
        ContentRequirement(
            "interview note fixture contract",
            (
                "Interview Note Fixture Contract",
                "interview-notes.jsonl",
                "typed_interview_note",
                "interview_note",
                "sourceUrls: []",
            ),
        ),
        ContentRequirement(
            "job-link parser fixture contract",
            (
                "JobLinkParser Fixture Contract",
                "examples/job-links/*.jsonl",
                "boss-zhipin.jsonl",
                "company-careers.jsonl",
                "shared-links.jsonl",
                "pasted-jds.jsonl",
                "JSONL",
                "public_evidence=false",
                "private_user_context",
                "mobile/shared redirect",
                "LinkedIn-style public",
                "sourceUrls",
            ),
        ),
    ],
    "examples/job-links/boss-zhipin.txt": [
        ContentRequirement(
            "Boss-style lead context markers",
            (
                "zhipin.com/job_detail",
                "boss-zhipin.jsonl",
                "public_evidence=false",
                "sourceUrls",
            ),
        ),
    ],
    "examples/job-links/company-careers.txt": [
        ContentRequirement(
            "company and mirror lead context markers",
            (
                "careers.example-retail.test",
                "jobs.example-mirror.test",
                "company-careers.jsonl",
                "public_evidence=false",
                "sourceUrls",
            ),
        ),
    ],
    "examples/job-links/shared-links.txt": [
        ContentRequirement(
            "shared-link lead context markers",
            (
                "shared-links.jsonl",
                "mobile/shared redirect",
                "LinkedIn-style public",
                "public_evidence=false",
                "sourceUrls",
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
        ContentRequirement(
            "report fixture metadata contract",
            (
                "Report Fixture Metadata Contract",
                "report-fixtures.jsonl",
                "top-level `sourceUrls`",
                "claim `sourceIds`",
                "expected_evidence",
                "evidence quality labels",
                "expected_unknown_sourceIds",
                "sourceUrls_refresh_required=true",
                "unknowns",
            ),
        ),
    ],
    "examples/reports/README.md": [
        ContentRequirement(
            "source-backed report fixture policy",
            (
                "report-fixtures.jsonl",
                "top-level `sourceUrls`",
                "sourceIds",
                "expected_evidence",
                "evidence quality",
                "unknowns",
                "sourceUrls_refresh_required",
            ),
        ),
    ],
    "docs/launch-checklist.md": [
        ContentRequirement(
            "strict JSONL fixture validation",
            (
                "structured JSONL fixture metadata",
                "valid JSON lines",
                "unique IDs",
                "required fixture type fields",
                "sourceUrls/privacy boundaries",
                "offerpilot doctor --strict-publish",
            ),
        ),
    ],
    "docs/intelligence.md": [
        ContentRequirement(
            "daily intelligence fixture contract",
            (
                "Daily Intelligence Fixture Contract",
                "daily-intelligence.jsonl",
                "public-source signals",
                "private interview notes",
                "needs_corroboration=true",
                "needs_verification=true",
                "sourceUrls_refresh_required=true",
                "sourceUrls",
            ),
        ),
    ],
    "examples/intelligence/README.md": [
        ContentRequirement(
            "source-backed intelligence fixture policy",
            (
                "daily-intelligence.jsonl",
                "public-source signals",
                "private interview notes",
                "needs_verification",
                "needs_corroboration",
                "sourceUrls_refresh_required",
                "sourceUrls",
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
                "interview-notes.jsonl",
                "metadata for a pretend uploaded audio file",
                "Interview transcripts must not appear in `sourceUrls`",
            ),
        ),
    ],
    "examples/reminders/README.md": [
        ContentRequirement(
            "safe reminder fixture policy",
            (
                "daily-reminders.jsonl",
                "missing_fields",
                "safe_without_private_sourceUrls",
                "sourceUrls",
                "next step owner",
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
                "interview-notes.jsonl",
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
    yield from _jsonl_fixture_checks(root)


def _structured_jsonl_fixture_files(root: Path = Path(".")) -> list[str]:
    examples_root = root / "examples"
    if not examples_root.exists():
        return []
    return sorted(
        str(path.relative_to(root)) for path in examples_root.rglob("*.jsonl") if path.is_file()
    )


def _jsonl_fixture_checks(root: Path) -> Iterable[Check]:
    discovered = set(_structured_jsonl_fixture_files(root))
    registered = set(JSONL_FIXTURE_SPECS)
    missing_specs = sorted(discovered - registered)
    missing_files = sorted(registered - discovered)
    registry_errors = []
    if missing_specs:
        registry_errors.append("missing specs for: " + ", ".join(missing_specs))
    if missing_files:
        registry_errors.append("missing files for specs: " + ", ".join(missing_files))
    yield Check(
        "jsonl:fixture_registry",
        not registry_errors,
        "all example JSONL fixtures are registered"
        if not registry_errors
        else "; ".join(registry_errors),
    )

    id_locations = {}
    duplicate_errors = []
    for rel in sorted(discovered):
        spec = JSONL_FIXTURE_SPECS.get(rel)
        if spec is None:
            yield Check(f"jsonl:{rel}", False, "unregistered JSONL fixture metadata file")
            continue
        check, row_ids = _validate_jsonl_fixture_file(root / rel, rel, spec, root)
        yield check
        for row_id in row_ids:
            if row_id in id_locations:
                duplicate_errors.append(f"{row_id} in {id_locations[row_id]} and {rel}")
            else:
                id_locations[row_id] = rel

    yield Check(
        "jsonl:fixture_ids",
        not duplicate_errors,
        "all JSONL fixture IDs are globally unique"
        if not duplicate_errors
        else "duplicate JSONL fixture IDs: " + "; ".join(duplicate_errors[:5]),
    )


def _validate_jsonl_fixture_metadata(
    path: Path,
    rel: str,
    root: Path = Path("."),
) -> Check:
    spec = JSONL_FIXTURE_SPECS.get(rel)
    if spec is None:
        spec = JsonlFixtureSpec(
            required_fields=(
                "id",
                "fixture_type",
                "public_evidence",
                "completed_report_requirement",
            ),
            expected_values={},
        )
    check, _ = _validate_jsonl_fixture_file(path, rel, spec, root)
    return check


def _validate_jsonl_fixture_file(
    path: Path,
    rel: str,
    spec: JsonlFixtureSpec,
    root: Path,
) -> tuple[Check, list[str]]:
    if not path.exists():
        return Check(f"jsonl:{rel}", False, "missing file"), []

    rows = []
    row_ids = []
    file_ids = set()
    errors = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as exc:
        return Check(f"jsonl:{rel}", False, f"could not read UTF-8 content: {exc}"), []

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_number}: invalid JSON ({exc.msg})")
            continue
        if not isinstance(row, dict):
            errors.append(f"line {line_number}: row must be a JSON object")
            continue

        rows.append(row)
        row_id = row.get("id")
        if not isinstance(row_id, str) or not row_id.strip():
            errors.append(f"line {line_number}: missing non-empty id")
        elif row_id in file_ids:
            errors.append(f"line {line_number}: duplicate id {row_id}")
        else:
            file_ids.add(row_id)
            row_ids.append(row_id)

        _validate_jsonl_required_fields(row, spec, line_number, errors)
        _validate_jsonl_expected_values(row, spec, line_number, errors)
        _validate_jsonl_source_boundary(row, spec, line_number, errors)
        _validate_jsonl_references(row, spec, root, line_number, errors)
        _validate_jsonl_count_pairs(row, spec, line_number, errors)

    if not rows:
        errors.append("file has no JSONL rows")

    detail = (
        "valid structured JSONL fixture metadata"
        if not errors
        else "invalid structured JSONL fixture metadata: " + "; ".join(errors[:8])
    )
    return Check(f"jsonl:{rel}", not errors, detail), row_ids


def _validate_jsonl_required_fields(
    row: dict,
    spec: JsonlFixtureSpec,
    line_number: int,
    errors: list[str],
) -> None:
    for field in spec.required_fields:
        if field not in row:
            errors.append(f"line {line_number}: missing required field {field}")


def _validate_jsonl_expected_values(
    row: dict,
    spec: JsonlFixtureSpec,
    line_number: int,
    errors: list[str],
) -> None:
    for field, expected in spec.expected_values.items():
        if row.get(field) != expected:
            errors.append(f"line {line_number}: expected {field}={expected!r}")


def _validate_jsonl_source_boundary(
    row: dict,
    spec: JsonlFixtureSpec,
    line_number: int,
    errors: list[str],
) -> None:
    if "public_evidence" not in row or not isinstance(row["public_evidence"], bool):
        errors.append(f"line {line_number}: public_evidence must be a boolean")

    privacy = row.get("privacy")
    if privacy is not None and (not isinstance(privacy, str) or not privacy.strip()):
        errors.append(f"line {line_number}: privacy must be a non-empty string")

    for field in JSONL_URL_FIELDS:
        if field not in row:
            continue
        urls = row[field]
        if not isinstance(urls, list) or not all(isinstance(url, str) for url in urls):
            errors.append(f"line {line_number}: {field} must be a list of strings")
            continue
        if urls:
            try:
                validate_source_urls(urls)
            except ReportValidationError as exc:
                errors.append(f"line {line_number}: invalid {field}: {exc}")

    if row.get("public_evidence") is True:
        if not any(row.get(field) for field in spec.url_fields):
            errors.append(
                f"line {line_number}: public evidence rows must retain sourceUrls "
                "or retained_sourceUrls"
            )
    elif row.get("public_evidence") is False:
        if spec.empty_source_urls and "sourceUrls" in row and row["sourceUrls"] != []:
            errors.append(f"line {line_number}: private/non-public rows must keep sourceUrls=[]")
        requirement = row.get("completed_report_requirement", "")
        if "sourceUrls" not in str(requirement):
            errors.append(
                f"line {line_number}: completed_report_requirement must mention sourceUrls"
            )


def _validate_jsonl_references(
    row: dict,
    spec: JsonlFixtureSpec,
    root: Path,
    line_number: int,
    errors: list[str],
) -> None:
    for field, base_dir in spec.references:
        if field not in row:
            continue
        value = row[field]
        if not isinstance(value, str) or not value.strip():
            errors.append(f"line {line_number}: {field} must be a non-empty string")
            continue
        target = root / base_dir / value if base_dir else root / value
        if not target.exists():
            errors.append(f"line {line_number}: referenced {field} does not exist: {value}")


def _validate_jsonl_count_pairs(
    row: dict,
    spec: JsonlFixtureSpec,
    line_number: int,
    errors: list[str],
) -> None:
    for count_field, list_field in spec.count_pairs:
        if count_field not in row or list_field not in row:
            continue
        if not isinstance(row[list_field], list):
            continue
        if row[count_field] != len(row[list_field]):
            errors.append(f"line {line_number}: {count_field} must equal len({list_field})")


def format_checks(checks: Iterable[Check]) -> str:
    lines = []
    for check in checks:
        mark = "OK" if check.ok else "FAIL"
        lines.append(f"[{mark}] {check.name}: {check.detail}")
    return "\n".join(lines)


def checks_ok(checks: Iterable[Check]) -> bool:
    return all(check.ok for check in checks)
