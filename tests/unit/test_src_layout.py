from pathlib import Path

from imageset_generator.app import app
from imageset_generator.constants import BASE_CATALOGS


def test_static_folder_points_to_repo_frontend_build():
    expected = Path(__file__).resolve().parents[2] / "frontend" / "build"
    assert Path(app.static_folder) == expected


def test_unknown_api_route_returns_404():
    app.testing = True
    client = app.test_client()

    response = client.get("/api/does-not-exist")

    assert response.status_code == 404


def test_available_catalogs_endpoint_returns_base_catalogs(monkeypatch):
    app.testing = True
    client = app.test_client()

    class CompletedProcess:
        returncode = 0
        stderr = ""

    def fake_run(cmd, capture_output, text, timeout):
        assert cmd[:4] == ["oc-mirror", "list", "operators", "--catalogs"]
        assert timeout == 120
        return CompletedProcess()

    monkeypatch.setattr("imageset_generator.app.subprocess.run", fake_run)

    response = client.get("/api/operators/catalogs")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "success"
    assert payload["count"] == len(BASE_CATALOGS)
    assert [catalog["url"] for catalog in payload["catalogs"]] == [
        catalog["base_url"] for catalog in BASE_CATALOGS
    ]


def test_packaged_automation_modules_import():
    from imageset_generator.automation.engine import AutomationEngine, load_config
    from imageset_generator.automation.scheduler import AutomationScheduler

    assert AutomationEngine is not None
    assert AutomationScheduler is not None
    assert load_config is not None
