import os
import pytest

if not os.environ.get("TEST_DATABASE_URL"):
    pytest.skip("TEST_DATABASE_URL not set", allow_module_level=True)


def test_pipeline_runs_returns_list(client):
    r = client.get("/pipeline/runs")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_pipeline_runs_one_seeded_run(client):
    r = client.get("/pipeline/runs")
    assert len(r.json()) == 1


def test_pipeline_run_response_shape(client):
    run = client.get("/pipeline/runs").json()[0]
    for key in ("id", "started_at", "completed_at", "status", "rows_loaded", "notes"):
        assert key in run


def test_pipeline_run_values(client):
    run = client.get("/pipeline/runs").json()[0]
    assert run["status"] == "success"
    assert run["rows_loaded"] == 50000
    assert run["notes"] is None
    assert run["started_at"] is not None
    assert run["completed_at"] is not None
