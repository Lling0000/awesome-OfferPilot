from datetime import datetime
from typing import Iterable

from offerpilot.providers.search_sources import LocalFixtureSearchSource, SearchSource
from offerpilot.search import build_query_plan, extract_skill_terms, normalize_evidence_items


class MockJobLinkParser:
    def parse(self, url: str) -> dict:
        platform = "boss" if "zhipin" in url or "boss" in url else "company_site"
        return {
            "platform": platform,
            "company_name": "Example Robotics",
            "job_title": "Backend Engineer Intern",
            "city": "Shanghai",
            "jd_text": (
                "Build Python services for interview scheduling, candidate analytics, "
                "and evidence-backed job recommendations. Familiarity with FastAPI, "
                "SQL, Redis, and async workflows is preferred."
            ),
            "skills": ["Python", "FastAPI", "SQL", "Redis", "async workflows"],
            "parsed_at": datetime.utcnow().isoformat(),
        }


class MockSearchProvider:
    def __init__(self, sources: Iterable[SearchSource] = None) -> None:
        self.sources = list(sources) if sources is not None else [LocalFixtureSearchSource()]

    def search(self, company_name: str, job_title: str, jd_text: str) -> dict:
        query_plan = build_query_plan(company_name, job_title, jd_text)
        raw_evidence = []
        for query in query_plan:
            for source in self.sources:
                raw_evidence.extend(source.search(query))
        skills = extract_skill_terms(jd_text)
        evidence = normalize_evidence_items(raw_evidence, company_name, job_title, skills)
        source_urls = [item["url"] for item in evidence]
        query = query_plan[0]["query"]
        summary_md = f"""## Position Snapshot

Company: {company_name}
Role: {job_title}

## Public Evidence

- Official role evidence suggests Python service work and backend fundamentals.
- Community notes repeatedly mention API design, SQL indexes, Redis caching, and project review.
- Evidence was normalized, deduplicated, and scored before this report was written.

## Likely Interview Questions

1. Explain an API you designed and how you handled failure modes.
2. How would you choose indexes for a high-read application table?
3. What Redis caching risks matter for user-facing job workflows?

## Preparation Priority

High: JD skills and questions repeated by multiple sources.
Medium: adjacent backend fundamentals from similar internship notes.
Low: content inferred only from the JD.
"""
        return {
            "query": query,
            "summary_md": summary_md,
            "source_urls": source_urls,
            "evidence": evidence,
            "query_plan": query_plan,
            "search_coverage": {
                "searched_platforms": sorted({item["source_type"] for item in evidence}),
                "query_count": len(query_plan),
                "found_useful_links": len(evidence),
                "search_sources": [source.name for source in self.sources],
            },
            "confidence_score": 0.78,
        }


class MockTranscriptionProvider:
    def transcribe(self, file_path: str) -> dict:
        return {
            "file_path": file_path,
            "transcript": (
                "The interviewer asked about backend projects, SQL indexes, "
                "and how I would prepare for the next round."
            ),
            "confidence": 0.7,
        }


class MockInterviewAnalyzer:
    def analyze(self, transcript: str) -> dict:
        return {
            "questions": [
                "Walk through your most relevant backend project.",
                "How did you debug a slow database query?",
                "What would you improve in your resume for this role?",
            ],
            "summary": (
                "The interview centered on project depth, database fundamentals, and role fit."
            ),
            "next_focus": [
                "Prepare one project story",
                "Review SQL indexing",
                "Tighten resume evidence",
            ],
        }


class MockProviderBundle:
    def __init__(self) -> None:
        self.job_link_parser = MockJobLinkParser()
        self.search_provider = MockSearchProvider()
        self.transcription_provider = MockTranscriptionProvider()
        self.interview_analyzer = MockInterviewAnalyzer()
