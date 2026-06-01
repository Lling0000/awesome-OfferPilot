from datetime import datetime
from typing import Iterable, List
from urllib.parse import urlparse, urlunparse

KNOWN_SKILLS = [
    "Python",
    "FastAPI",
    "SQL",
    "Redis",
    "MySQL",
    "Java",
    "Go",
    "Kubernetes",
    "React",
    "LLM",
]

CREDIBILITY_BY_SOURCE = {
    "official": 0.95,
    "job_board": 0.82,
    "news": 0.78,
    "forum": 0.68,
    "social": 0.58,
    "unknown": 0.5,
}


def extract_skill_terms(jd_text: str) -> List[str]:
    haystack = jd_text.lower()
    return [skill for skill in KNOWN_SKILLS if skill.lower() in haystack]


def build_query_plan(company_name: str, job_title: str, jd_text: str) -> List[dict]:
    skills = extract_skill_terms(jd_text)
    skill_query = " ".join(skills[:3]) if skills else "interview"
    return [
        {
            "id": "company-role-interview",
            "query": f"{company_name} {job_title} 面经 面试题",
            "intent": "Find public interview reports for the exact company and role.",
            "source_focus": "forum",
        },
        {
            "id": "company-official-stack",
            "query": f"{company_name} engineering blog {skill_query}",
            "intent": "Validate technology stack and business context from official sources.",
            "source_focus": "official",
        },
        {
            "id": "role-skills-questions",
            "query": f"{job_title} {skill_query} interview questions",
            "intent": "Find similar-role questions when exact company evidence is sparse.",
            "source_focus": "search_engine",
        },
        {
            "id": "freshness",
            "query": f"{company_name} {job_title} 2026 最近 面试",
            "intent": "Prioritize recent interview changes and current hiring signals.",
            "source_focus": "freshness",
        },
    ]


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    path = parsed.path.rstrip("/") or "/"
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            "",
            parsed.query,
            "",
        )
    )


def normalize_evidence_items(
    raw_items: Iterable[dict],
    company_name: str,
    job_title: str,
    skills: Iterable[str],
) -> List[dict]:
    normalized_by_url = {}
    for item in raw_items:
        url = str(item.get("url", "")).strip()
        if not url:
            continue
        canonical_url = item.get("canonical_url") or canonicalize_url(url)
        if canonical_url in normalized_by_url:
            existing = normalized_by_url[canonical_url]
            existing["query_ids"] = sorted(
                set(existing.get("query_ids", [])) | set(item.get("query_ids", []))
            )
            continue
        source_type = item.get("source_type") or infer_source_type(url)
        relevance = round(
            float(
                item.get("relevance_score")
                or score_relevance(item, company_name, job_title, skills)
            ),
            2,
        )
        freshness = round(float(item.get("freshness_score") or score_freshness(item)), 2)
        credibility = round(
            float(item.get("credibility_score") or CREDIBILITY_BY_SOURCE.get(source_type, 0.5)),
            2,
        )
        overall = round(relevance * 0.5 + credibility * 0.3 + freshness * 0.2, 2)
        enriched = {
            **item,
            "url": url,
            "canonical_url": canonical_url,
            "source_type": source_type,
            "relevance_score": relevance,
            "freshness_score": freshness,
            "credibility_score": credibility,
            "overall_score": overall,
            "quality_label": quality_label(overall),
            "score_reasons": score_reasons(source_type, relevance, freshness, credibility),
        }
        normalized_by_url[canonical_url] = enriched
    return sorted(
        normalized_by_url.values(),
        key=lambda item: (
            item["relevance_score"],
            item["overall_score"],
            item["credibility_score"],
            item["freshness_score"],
        ),
        reverse=True,
    )


def infer_source_type(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if any(name in host for name in ["zhipin", "liepin", "linkedin", "jobs"]):
        return "job_board"
    if any(name in host for name in ["xiaohongshu", "xhs"]):
        return "social"
    if any(name in host for name in ["nowcoder", "zhihu", "csdn", "juejin", "v2ex"]):
        return "forum"
    if any(name in host for name in ["news", "36kr", "techcrunch"]):
        return "news"
    if "example.com" in host:
        return "official"
    return "unknown"


def score_relevance(item: dict, company_name: str, job_title: str, skills: Iterable[str]) -> float:
    text = f"{item.get('title', '')} {item.get('snippet', '')}".lower()
    score = 0.2
    if company_name.lower() in text:
        score += 0.3
    role_tokens = [token for token in job_title.lower().split() if len(token) > 2]
    if role_tokens and any(token in text for token in role_tokens):
        score += 0.2
    matched_skills = [skill for skill in skills if skill.lower() in text]
    score += min(0.25, len(matched_skills) * 0.08)
    return min(score, 0.98)


def score_freshness(item: dict) -> float:
    raw = item.get("published_at")
    if not raw:
        return 0.62
    try:
        published_at = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return 0.55
    age_days = max((datetime.utcnow() - published_at.replace(tzinfo=None)).days, 0)
    if age_days <= 90:
        return 0.95
    if age_days <= 365:
        return 0.78
    if age_days <= 730:
        return 0.58
    return 0.35


def quality_label(overall_score: float) -> str:
    if overall_score >= 0.82:
        return "high"
    if overall_score >= 0.62:
        return "medium"
    return "low"


def score_reasons(
    source_type: str,
    relevance_score: float,
    freshness_score: float,
    credibility_score: float,
) -> List[str]:
    reasons = [f"{source_type} source"]
    if relevance_score >= 0.75:
        reasons.append("strong company/role/skill match")
    elif relevance_score >= 0.5:
        reasons.append("partial match to the target role")
    else:
        reasons.append("weak direct match")

    if freshness_score >= 0.78:
        reasons.append("recent evidence")
    elif freshness_score < 0.5:
        reasons.append("older evidence")

    if credibility_score >= 0.9:
        reasons.append("high-trust publisher")
    elif credibility_score < 0.65:
        reasons.append("requires extra verification")
    return reasons
