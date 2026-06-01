import pytest

from offerpilot.reports import ReportValidationError, validate_source_urls


def test_source_urls_required() -> None:
    with pytest.raises(ReportValidationError):
        validate_source_urls([])


def test_source_urls_must_be_valid_http_urls() -> None:
    with pytest.raises(ReportValidationError):
        validate_source_urls(["not-a-url"])


def test_source_urls_accept_http_and_https() -> None:
    assert validate_source_urls([" https://example.com/a ", "http://example.com/b"]) == [
        "https://example.com/a",
        "http://example.com/b",
    ]
