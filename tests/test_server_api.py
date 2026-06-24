from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agentlens.demo import run_demo
from agentlens.server.app import create_app
from agentlens.tracer import shutdown


@pytest.fixture
def client(tmp_path):
    db = str(tmp_path / "api.db")
    run_demo(db_path=db, runs=2, seed=7)
    shutdown()  # close the writer connection; data is committed to disk
    app = create_app(db)
    return TestClient(app)


class TestHealth:
    def test_health(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["db_exists"] is True


class TestRunsList:
    def test_list(self, client):
        r = client.get("/api/runs")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 2
        assert len(body["runs"]) == 2
        run = body["runs"][0]
        assert run["span_count"] >= 5
        assert run["error_count"] == 1  # demo has one deliberate error
        assert run["total_tokens"] > 0
        assert isinstance(run["models"], dict)

    def test_pagination(self, client):
        r = client.get("/api/runs?limit=1&offset=0")
        assert len(r.json()["runs"]) == 1

    def test_limit_validation(self, client):
        assert client.get("/api/runs?limit=0").status_code == 422
        assert client.get("/api/runs?limit=99999").status_code == 422


class TestRunDetail:
    def test_tree_structure(self, client):
        run_id = client.get("/api/runs").json()["runs"][0]["run_id"]
        r = client.get(f"/api/runs/{run_id}")
        assert r.status_code == 200
        body = r.json()
        assert "window" in body and "start" in body["window"]
        assert len(body["spans"]) >= 5  # flat list
        # tree: single root (research_agent) with several children
        assert len(body["tree"]) == 1
        root = body["tree"][0]
        assert root["name"] == "research_agent"
        assert len(root["children"]) >= 3
        # the web_search child has a nested summarize llm_call
        web = next(c for c in root["children"] if c["name"] == "web_search")
        assert any(gc["name"] == "summarize" for gc in web["children"])
        # one child errored
        assert any(c["status"] == "error" for c in root["children"])

    def test_missing_run_404(self, client):
        assert client.get("/api/runs/deadbeef").status_code == 404


class TestSpanDetail:
    def test_get_span(self, client):
        run_id = client.get("/api/runs").json()["runs"][0]["run_id"]
        detail = client.get(f"/api/runs/{run_id}").json()
        span_id = detail["spans"][0]["span_id"]
        r = client.get(f"/api/runs/{run_id}/spans/{span_id}")
        assert r.status_code == 200
        assert r.json()["span_id"] == span_id

    def test_missing_span_404(self, client):
        run_id = client.get("/api/runs").json()["runs"][0]["run_id"]
        assert client.get(f"/api/runs/{run_id}/spans/nope").status_code == 404


class TestDelete:
    def test_delete(self, client):
        run_id = client.get("/api/runs").json()["runs"][0]["run_id"]
        assert client.delete(f"/api/runs/{run_id}").json()["deleted"] is True
        assert client.get(f"/api/runs/{run_id}").status_code == 404
        assert client.delete(f"/api/runs/{run_id}").status_code == 404


class TestStaticServing:
    def test_root_serves_something(self, client):
        # Either the built SPA (if frontend/dist exists) or the placeholder.
        r = client.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]

    def test_api_not_shadowed_by_static_mount(self, client):
        assert client.get("/api/health").status_code == 200
