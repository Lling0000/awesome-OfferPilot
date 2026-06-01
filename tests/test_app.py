from fastapi.testclient import TestClient

from offerpilot.app import create_app


def test_app_dashboard_renders(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OFFERPILOT_DATABASE_URL", f"sqlite:///{tmp_path}/offerpilot.db")
    client = TestClient(create_app())
    response = client.get("/")
    assert response.status_code == 200
    assert "OfferPilot" in response.text
    assert "Evidence-first job search command center" in response.text
    assert "Pasted JD" in response.text


def test_job_link_intake_creates_application_report_and_reminders(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OFFERPILOT_DATABASE_URL", f"sqlite:///{tmp_path}/offerpilot.db")
    client = TestClient(create_app())

    response = client.post(
        "/intake/job-link",
        data={"url": "https://www.zhipin.com/job_detail/example-backend-intern.html"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/applications/")

    dashboard = client.get("/")
    assert "Example Robotics" in dashboard.text
    assert "Example Robotics Backend Engineer Intern 面经 面试题" in dashboard.text
    assert "P0 跟进 Example Robotics 的下一步动作" in dashboard.text


def test_pasted_jd_intake_creates_application_report_and_reminders(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OFFERPILOT_DATABASE_URL", f"sqlite:///{tmp_path}/offerpilot.db")
    client = TestClient(create_app())

    jd_text = """Company: Example Analytics
Role: Backend Platform Intern
City: Shanghai

Build Python services with FastAPI, SQL, Redis, and async workflows.
"""
    response = client.post(
        "/intake/job-description",
        data={"jd_text": jd_text},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/applications/")

    application = client.get(response.headers["location"])
    assert "Example Analytics" in application.text
    assert "Backend Platform Intern" in application.text
    assert "Reports" in application.text

    dashboard = client.get("/")
    assert "Example Analytics Backend Platform Intern 面经 面试题" in dashboard.text
    assert "source URLs" in dashboard.text


def test_api_pasted_jd_intake_returns_source_urls(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OFFERPILOT_DATABASE_URL", f"sqlite:///{tmp_path}/offerpilot.db")
    client = TestClient(create_app())

    response = client.post(
        "/api/job-descriptions",
        json={
            "jd_text": (
                "Company: Example Analytics\n"
                "Role: Backend Platform Intern\n"
                "Build Python FastAPI services with SQL and Redis."
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["input_type"] == "pasted_jd"
    assert payload["application_id"]
    assert payload["search_report_id"]
    assert payload["sourceUrls"]

    apps = client.get("/api/applications").json()
    assert apps[0]["company_name"] == "Example Analytics"


def test_api_interview_intake_creates_summary(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OFFERPILOT_DATABASE_URL", f"sqlite:///{tmp_path}/offerpilot.db")
    client = TestClient(create_app())

    app_response = client.post(
        "/api/applications",
        json={"company_name": "Example Robotics", "job_title": "Backend Engineer Intern"},
    )
    app_id = app_response.json()["id"]

    response = client.post(
        f"/api/applications/{app_id}/interviews",
        json={
            "stage": "technical",
            "typed_note": "The interviewer asked about SQL indexes and API design.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["questions"]
    assert "database" in " ".join(payload["questions"]).lower()


def test_api_interview_intake_requires_artifact(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OFFERPILOT_DATABASE_URL", f"sqlite:///{tmp_path}/offerpilot.db")
    client = TestClient(create_app())

    app_response = client.post(
        "/api/applications",
        json={"company_name": "Example Robotics", "job_title": "Backend Engineer Intern"},
    )
    app_id = app_response.json()["id"]

    response = client.post(f"/api/applications/{app_id}/interviews", json={})

    assert response.status_code == 422
    assert "audio file or typed notes" in response.text


def test_api_daily_intelligence_creates_source_backed_items(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OFFERPILOT_DATABASE_URL", f"sqlite:///{tmp_path}/offerpilot.db")
    client = TestClient(create_app())

    response = client.post(
        "/api/intelligence/daily",
        json={"role_family": "backend", "city": "Shanghai"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 4
    assert len(payload["sourceUrls"]) == 4
    assert payload["digest"]["by_company_scale"]["大厂"] == 1

    listed = client.get("/api/intelligence").json()
    assert len(listed["items"]) == 4
    assert listed["sourceUrls"]


def test_web_daily_intelligence_visible_on_dashboard(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OFFERPILOT_DATABASE_URL", f"sqlite:///{tmp_path}/offerpilot.db")
    client = TestClient(create_app())

    response = client.post(
        "/intelligence/daily",
        data={"role_family": "backend", "city": "Shanghai"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/intelligence/")
    page = client.get("/")
    assert "Daily Intelligence" in page.text
    assert "大厂后端经理面更关注项目 owner 感和跨团队协作" in page.text
    assert "https://example.com/intelligence/big-tech-manager-round-2026" in page.text


def test_web_intelligence_list_filters_findings(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OFFERPILOT_DATABASE_URL", f"sqlite:///{tmp_path}/offerpilot.db")
    client = TestClient(create_app())
    client.post("/api/intelligence/daily", json={"role_family": "backend", "city": "Shanghai"})

    response = client.get("/intelligence?company_scale=大厂&signal_type=manager_round")

    assert response.status_code == 200
    assert "Public Interview Signals" in response.text
    assert "大厂后端经理面更关注项目 owner 感和跨团队协作" in response.text
    assert "中厂技术面继续深挖缓存" not in response.text
    assert "needs verification" in response.text


def test_web_intelligence_detail_shows_agent_coverage(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OFFERPILOT_DATABASE_URL", f"sqlite:///{tmp_path}/offerpilot.db")
    client = TestClient(create_app())
    payload = client.post(
        "/api/intelligence/daily",
        json={"role_family": "backend", "city": "Shanghai"},
    ).json()

    response = client.get(f"/intelligence/{payload['agent_run_id']}")

    assert response.status_code == 200
    assert "Agent Coverage" in response.text
    assert "intel_big-tech-scout" in response.text
    assert "大厂后端经理面更关注项目 owner 感和跨团队协作" in response.text
    assert "https://example.com/intelligence/big-tech-manager-round-2026" in response.text


def test_api_intelligence_run_detail_includes_child_agents(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OFFERPILOT_DATABASE_URL", f"sqlite:///{tmp_path}/offerpilot.db")
    client = TestClient(create_app())
    payload = client.post(
        "/api/intelligence/daily",
        json={"role_family": "backend", "city": "Shanghai"},
    ).json()

    response = client.get(f"/api/intelligence/{payload['agent_run_id']}")

    assert response.status_code == 200
    detail = response.json()
    assert len(detail["agentRuns"]) == 4
    assert len(detail["items"]) == 4
    assert detail["sourceUrls"]
    assert detail["agentRuns"][0]["query"]["query"]

    runs = client.get("/api/intelligence/runs").json()
    assert runs["runs"]
    assert runs["runs"][0]["sourceUrls"]


def test_web_intelligence_detail_not_found(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OFFERPILOT_DATABASE_URL", f"sqlite:///{tmp_path}/offerpilot.db")
    client = TestClient(create_app())

    response = client.get("/intelligence/not-a-run")

    assert response.status_code == 200
    assert "Intelligence brief not found." in response.text


def test_web_interview_upload_renders_summary(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OFFERPILOT_DATABASE_URL", f"sqlite:///{tmp_path}/offerpilot.db")
    client = TestClient(create_app())

    intake = client.post(
        "/intake/job-link",
        data={"url": "https://www.zhipin.com/job_detail/example-backend-intern.html"},
        follow_redirects=False,
    )
    app_path = intake.headers["location"]
    app_id = app_path.rsplit("/", 1)[-1]

    response = client.post(
        f"/applications/{app_id}/interviews",
        data={
            "stage": "technical",
            "typed_note": "I need to review Redis caching and project depth.",
        },
        files={"audio_file": ("interview.m4a", b"fake audio", "audio/mp4")},
        follow_redirects=False,
    )

    assert response.status_code == 303

    page = client.get(app_path)
    assert "Interview Summaries" in page.text
    assert "The interview centered on project depth" in page.text
    assert "Walk through your most relevant backend project." in page.text
