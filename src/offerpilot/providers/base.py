from typing import Protocol


class JobLinkParser(Protocol):
    def parse(self, url: str) -> dict:
        """Extract company, role, JD, platform, and skills from a job URL."""


class SearchProvider(Protocol):
    def search(self, company_name: str, job_title: str, jd_text: str) -> dict:
        """Return source-backed search evidence and a concise report draft."""


class TranscriptionProvider(Protocol):
    def transcribe(self, file_path: str) -> dict:
        """Turn an uploaded audio/video artifact into transcript text."""


class InterviewAnalyzer(Protocol):
    def analyze(self, transcript: str) -> dict:
        """Extract questions, summary, and next preparation focus from interview text."""
