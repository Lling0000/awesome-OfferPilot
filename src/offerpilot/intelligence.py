from datetime import datetime
from typing import Dict, Iterable, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from offerpilot.models import AgentRun, IntelligenceItem, User
from offerpilot.reports import validate_source_urls

COMPANY_SCALES = ["国央企", "大厂", "中厂", "小厂"]


def build_intelligence_query_plan(
    role_family: str = "backend", city: str = "Shanghai"
) -> List[dict]:
    role = role_family.strip() or "backend"
    location = city.strip() or "Shanghai"
    return [
        {
            "id": "state-owned-gd",
            "agent": "state-owned-scout",
            "company_scale": "国央企",
            "query": f"国央企 {role} 实习 秋招 GD 群面 经理面 {location} 2026",
            "focus": ["group_discussion", "manager_round", "stability_signal"],
        },
        {
            "id": "big-tech-manager",
            "agent": "big-tech-scout",
            "company_scale": "大厂",
            "query": f"大厂 {role} 校招 面经 经理面 业务面 {location} 2026",
            "focus": ["manager_round", "technical_interview", "business_context"],
        },
        {
            "id": "mid-market-process",
            "agent": "mid-market-scout",
            "company_scale": "中厂",
            "query": f"中厂 {role} 面试流程 项目深挖 技术面 {location} 2026",
            "focus": ["technical_interview", "project_review", "hiring_signal"],
        },
        {
            "id": "small-team-founder",
            "agent": "small-team-scout",
            "company_scale": "小厂",
            "query": f"小厂 {role} 创始人面 业务理解 面试题 {location} 2026",
            "focus": ["founder_round", "business_context", "role_fit"],
        },
    ]


def run_daily_intelligence(
    session: Session,
    user: User,
    role_family: str = "backend",
    city: str = "Shanghai",
    now: Optional[datetime] = None,
) -> Dict[str, object]:
    """Run deterministic multi-agent interview intelligence collection."""

    collected_at = now or datetime.utcnow()
    query_plan = build_intelligence_query_plan(role_family, city)
    run = AgentRun(
        user_id=user.id,
        run_type="daily_intelligence",
        status="succeeded",
        input_json={"role_family": role_family, "city": city, "query_plan": query_plan},
        output_json={},
        started_at=collected_at,
        ended_at=collected_at,
    )
    session.add(run)
    session.flush()

    created_count = 0
    items = []
    child_runs = []
    candidates = _mock_multi_agent_collect(query_plan, role_family, city, collected_at)
    for query, candidate in zip(query_plan, candidates):
        validate_source_urls([candidate["source_url"]])
        child_run = AgentRun(
            user_id=user.id,
            run_type=f"intel_{query['agent']}",
            status="succeeded",
            input_json=query,
            output_json={"sourceUrls": [candidate["source_url"]], "found": 1},
            parent_run_id=run.id,
            started_at=collected_at,
            ended_at=collected_at,
        )
        session.add(child_run)
        session.flush()
        child_runs.append(child_run)
        existing = session.scalar(
            select(IntelligenceItem).where(
                IntelligenceItem.user_id == user.id,
                IntelligenceItem.source_url == candidate["source_url"],
            )
        )
        if existing is None:
            item = IntelligenceItem(user_id=user.id, agent_run_id=child_run.id)
            created_count += 1
            session.add(item)
        else:
            item = existing
            item.agent_run_id = child_run.id
        _apply_candidate(item, candidate, collected_at)
        items.append(item)

    session.flush()
    source_urls = [item.source_url for item in items]
    digest = build_intelligence_digest(items)
    run.output_json = {
        "item_ids": [item.id for item in items],
        "child_run_ids": [child.id for child in child_runs],
        "sourceUrls": source_urls,
        "digest": digest,
        "query_plan": query_plan,
    }
    return {
        "agent_run_id": run.id,
        "created": created_count,
        "items": [intelligence_item_to_dict(item) for item in items],
        "sourceUrls": source_urls,
        "digest": digest,
    }


def latest_intelligence_items(
    session: Session,
    user_id: str,
    limit: int = 8,
) -> List[IntelligenceItem]:
    return session.scalars(
        select(IntelligenceItem)
        .where(IntelligenceItem.user_id == user_id)
        .order_by(IntelligenceItem.retrieved_at.desc(), IntelligenceItem.created_at.desc())
        .limit(limit)
    ).all()


def latest_intelligence_runs(
    session: Session,
    user_id: str,
    limit: int = 10,
) -> List[AgentRun]:
    return session.scalars(
        select(AgentRun)
        .where(AgentRun.user_id == user_id, AgentRun.run_type == "daily_intelligence")
        .order_by(AgentRun.created_at.desc())
        .limit(limit)
    ).all()


def intelligence_items_for_run(
    session: Session,
    user_id: str,
    run: AgentRun,
) -> List[IntelligenceItem]:
    item_ids = (run.output_json or {}).get("item_ids", [])
    if not item_ids:
        return []
    return session.scalars(
        select(IntelligenceItem).where(
            IntelligenceItem.user_id == user_id,
            IntelligenceItem.id.in_(item_ids),
        )
    ).all()


def intelligence_child_runs(
    session: Session,
    user_id: str,
    parent_run_id: str,
) -> List[AgentRun]:
    return session.scalars(
        select(AgentRun)
        .where(
            AgentRun.user_id == user_id,
            AgentRun.parent_run_id == parent_run_id,
        )
        .order_by(AgentRun.created_at.asc())
    ).all()


def filtered_intelligence_items(
    session: Session,
    user_id: str,
    company_scale: str = "",
    signal_type: str = "",
) -> List[IntelligenceItem]:
    stmt = select(IntelligenceItem).where(IntelligenceItem.user_id == user_id)
    if company_scale:
        stmt = stmt.where(IntelligenceItem.company_scale == company_scale)
    if signal_type:
        stmt = stmt.where(IntelligenceItem.signal_type == signal_type)
    return session.scalars(
        stmt.order_by(IntelligenceItem.relevance_score.desc(), IntelligenceItem.retrieved_at.desc())
    ).all()


def build_intelligence_digest(items: Iterable[IntelligenceItem]) -> dict:
    by_scale = {scale: 0 for scale in COMPANY_SCALES}
    by_signal = {}
    manager_or_gd = []
    source_urls = []
    for item in items:
        by_scale[item.company_scale] = by_scale.get(item.company_scale, 0) + 1
        by_signal[item.signal_type] = by_signal.get(item.signal_type, 0) + 1
        source_urls.append(item.source_url)
        tags = item.tags_json or []
        if any(tag in {"manager_round", "group_discussion", "gd", "mentor_match"} for tag in tags):
            manager_or_gd.append(item.title)
    return {
        "by_company_scale": by_scale,
        "by_signal_type": by_signal,
        "manager_or_gd_matches": manager_or_gd,
        "sourceUrls": source_urls,
    }


def intelligence_item_to_dict(item: IntelligenceItem) -> dict:
    return {
        "id": item.id,
        "company_name": item.company_name,
        "company_scale": item.company_scale,
        "role_family": item.role_family,
        "signal_type": item.signal_type,
        "title": item.title,
        "summary": item.summary,
        "source_url": item.source_url,
        "source_type": item.source_type,
        "publisher": item.publisher,
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "retrieved_at": item.retrieved_at.isoformat() if item.retrieved_at else None,
        "relevance_score": item.relevance_score,
        "tags": item.tags_json or [],
    }


def _apply_candidate(item: IntelligenceItem, candidate: dict, retrieved_at: datetime) -> None:
    item.company_name = candidate["company_name"]
    item.company_scale = candidate["company_scale"]
    item.role_family = candidate["role_family"]
    item.signal_type = candidate["signal_type"]
    item.title = candidate["title"]
    item.summary = candidate["summary"]
    item.source_url = candidate["source_url"]
    item.source_type = candidate["source_type"]
    item.publisher = candidate["publisher"]
    item.published_at = candidate["published_at"]
    item.retrieved_at = retrieved_at
    item.relevance_score = candidate["relevance_score"]
    item.tags_json = candidate["tags"]
    item.raw_json = {
        **candidate,
        "published_at": candidate["published_at"].isoformat()
        if candidate.get("published_at")
        else None,
    }


def _mock_multi_agent_collect(
    query_plan: List[dict],
    role_family: str,
    city: str,
    now: datetime,
) -> List[dict]:
    role = role_family.strip() or "backend"
    location = city.strip() or "Shanghai"
    published_at = datetime(now.year, max(now.month - 1, 1), 18)
    fixture_by_scale = {
        "国央企": {
            "company_name": "China Grid Digital",
            "signal_type": "group_discussion",
            "title": "国央企数字化岗 GD 讨论开始更多围绕稳定性与公共服务场景",
            "summary": (
                "Mock source notes that group discussion prompts emphasize reliability, "
                "public-service tradeoffs, and structured communication."
            ),
            "source_url": "https://example.com/intelligence/state-owned-gd-2026",
            "source_type": "forum",
            "publisher": "Example Campus Forum",
            "relevance_score": 0.82,
            "tags": ["gd", "group_discussion", "stability_signal", location],
        },
        "大厂": {
            "company_name": "ByteWave Cloud",
            "signal_type": "manager_round",
            "title": "大厂后端经理面更关注项目 owner 感和跨团队协作",
            "summary": (
                "Mock source highlights manager-round questions about ownership, "
                "incident review, metrics, and collaboration with product teams."
            ),
            "source_url": "https://example.com/intelligence/big-tech-manager-round-2026",
            "source_type": "social",
            "publisher": "Example Interview Notes",
            "relevance_score": 0.88,
            "tags": ["manager_round", "mentor_match", "project_review", location],
        },
        "中厂": {
            "company_name": "Moka Systems",
            "signal_type": "technical_interview",
            "title": "中厂技术面继续深挖缓存、SQL 索引和异步任务边界",
            "summary": (
                "Mock source repeats backend topics that overlap with OfferPilot demo: "
                "FastAPI services, Redis caching, SQL indexing, and async workflows."
            ),
            "source_url": "https://example.com/intelligence/mid-market-technical-2026",
            "source_type": "forum",
            "publisher": "Example Developer Community",
            "relevance_score": 0.9,
            "tags": ["technical_interview", "project_review", "hiring_signal", role],
        },
        "小厂": {
            "company_name": "Harbor Robotics",
            "signal_type": "founder_round",
            "title": "小团队终面常把业务理解、岗位弹性和快速交付放在一起问",
            "summary": (
                "Mock source suggests small-team interviews combine founder questions, "
                "role fit, product context, and shipping tradeoffs."
            ),
            "source_url": "https://example.com/intelligence/small-team-founder-2026",
            "source_type": "official",
            "publisher": "Example Robotics Blog",
            "relevance_score": 0.76,
            "tags": ["founder_round", "business_context", "role_fit", role],
        },
    }
    items = []
    for query in query_plan:
        fixture = fixture_by_scale[query["company_scale"]]
        items.append(
            {
                **fixture,
                "company_scale": query["company_scale"],
                "role_family": role,
                "published_at": published_at,
                "retrieved_by": query["agent"],
                "query_id": query["id"],
                "query": query["query"],
            }
        )
    return items
