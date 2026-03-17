import json
import os
from pathlib import Path
import subprocess
import sys

from imageset_generator.app import app
from imageset_generator.constants import BASE_CATALOGS, PACKAGE_ROOT


def test_static_folder_points_to_packaged_frontend_build():
    expected = PACKAGE_ROOT / "frontend" / "build"
    assert Path(app.static_folder) == expected


def test_packaged_frontend_build_contains_static_assets():
    assert (PACKAGE_ROOT / "frontend" / "build" / "static").is_dir()


def test_ocp_versions_endpoint_uses_packaged_seed_data_outside_repo_root(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    # Force the read path to the packaged seed data so the runtime cache
    # (which differs in a checkout) is bypassed — this simulates running
    # from an installed wheel where no repo-level data/ directory exists.
    from imageset_generator.constants import get_packaged_data_path
    monkeypatch.setattr(
        "imageset_generator.app._data_read_file",
        get_packaged_data_path,
    )

    app.testing = True
    client = app.test_client()

    response = client.get("/api/ocp-versions")

    assert response.status_code == 200
    payload = response.get_json()
    packaged_payload = json.loads((PACKAGE_ROOT / "data" / "ocp-versions.json").read_text())
    assert payload["status"] == "success"
    assert payload["releases"] == packaged_payload["releases"]


def test_checkout_mode_resolves_project_root_to_repo_root():
    project_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root / "src")
    env.pop("IMAGESET_GENERATOR_ROOT", None)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from imageset_generator.constants import PROJECT_ROOT, RUNTIME_ROOT; "
                "print(PROJECT_ROOT); print(RUNTIME_ROOT)"
            ),
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=project_root,
    )

    assert result.returncode == 0, result.stderr
    roots = result.stdout.strip().splitlines()
    assert roots == [str(project_root), str(project_root)]


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
        stdout = "{}"
        stderr = ""

    def fake_run(cmd, capture_output, text, timeout):
        assert cmd[:2] == ["skopeo", "list-tags"]
        assert timeout == 30
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


def test_version_catalog_list_filters_unvalidated_from_cache(monkeypatch, tmp_path):
    """Cached catalog files with validated: false entries must not leak to clients."""
    app.testing = True
    client = app.test_client()

    cached = {"4.17": [
        {"name": "good", "url": "reg/good:v4.17", "description": "ok", "default": True, "validated": True},
        {"name": "bad", "url": "reg/bad:v4.17", "description": "nope", "default": False, "validated": False},
        {"name": "missing", "url": "reg/missing:v4.17", "description": "no key", "default": False},
    ]}

    cache_file = tmp_path / "catalogs-4.17.json"
    cache_file.write_text(json.dumps(cached))

    monkeypatch.setattr(
        "imageset_generator.app._data_read_file",
        lambda filename: tmp_path / filename,
    )

    response = client.get("/api/operators/catalogs/4.17/list")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["source"] == "static_file"
    assert len(payload["catalogs"]) == 1
    assert payload["catalogs"][0]["name"] == "good"


def test_version_refresh_excludes_unvalidated_catalogs(monkeypatch):
    """refresh_catalogs_for_version must not include catalogs that fail skopeo inspect."""
    app.testing = True
    client = app.test_client()

    call_count = {"n": 0}

    class FailProcess:
        returncode = 1
        stdout = ""
        stderr = "not found"

    def fake_run(cmd, capture_output, text, timeout):
        call_count["n"] += 1
        return FailProcess()

    monkeypatch.setattr("imageset_generator.app.subprocess.run", fake_run)

    response = client.post("/api/operators/catalogs/9.99/refresh")

    assert response.status_code == 200
    payload = response.get_json()
    # All catalogs failed validation, so none should be returned
    assert payload["catalogs"]["9.99"] == []
    assert call_count["n"] == len(BASE_CATALOGS)


def test_get_operator_catalogs_fallback_uses_correct_key(monkeypatch, tmp_path):
    """get_operator_catalogs must extract catalogs from the version-keyed refresh response."""
    app.testing = True
    client = app.test_client()

    # Make static file not exist so we hit the refresh fallback
    monkeypatch.setattr(
        "imageset_generator.app._data_read_file",
        lambda filename: tmp_path / "nonexistent" / filename,
    )

    class OkProcess:
        returncode = 0
        stdout = "{}"
        stderr = ""

    def fake_run(cmd, capture_output, text, timeout):
        return OkProcess()

    monkeypatch.setattr("imageset_generator.app.subprocess.run", fake_run)

    # Mock _data_write_file to avoid writing to real data dir
    monkeypatch.setattr(
        "imageset_generator.app._data_write_file",
        lambda filename: tmp_path / filename,
    )

    response = client.get("/api/operators/catalogs/4.17")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "success"
    # Should be a list, not a version-keyed dict
    assert isinstance(payload["catalogs"], list)


def test_packaged_automation_modules_import():
    from imageset_generator.automation.engine import AutomationEngine, load_config
    from imageset_generator.automation.scheduler import AutomationScheduler

    assert AutomationEngine is not None
    assert AutomationScheduler is not None
    assert load_config is not None
