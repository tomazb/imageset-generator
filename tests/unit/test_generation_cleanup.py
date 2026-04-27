import json

import pytest
import yaml

from imageset_generator.app import app


def _operator_cache(tmp_path):
    cache_file = tmp_path / "operators-redhat-operator-index-4.16.json"
    cache_file.write_text(
        json.dumps(
            {
                "operators": [
                    {
                        "name": "cluster-logging",
                        "version": "5.8.0",
                        "channel": "stable-5.8",
                    },
                    {
                        "name": "cluster-logging",
                        "version": "5.8.1",
                        "channel": "stable-5.8",
                    },
                    {
                        "name": "cluster-logging",
                        "version": "5.9.0",
                        "channel": "stable-5.9",
                    },
                ]
            }
        )
    )
    return cache_file


def test_generate_download_matches_preview_for_operator_version_range(monkeypatch, tmp_path):
    app.testing = True
    client = app.test_client()
    cache_file = _operator_cache(tmp_path)

    def fake_data_read_file(filename):
        if filename == "operators-redhat-operator-index-4.16.json":
            return cache_file
        return tmp_path / filename

    monkeypatch.setattr("imageset_generator.app._data_read_file", fake_data_read_file)

    payload = {
        "ocp_versions": ["4.16"],
        "ocp_channel": "stable-4.16",
        "operators": [
            {
                "name": "cluster-logging",
                "catalog": "registry.redhat.io/redhat/redhat-operator-index",
                "minVersion": "5.8.0",
                "maxVersion": "5.8.1",
            }
        ],
    }

    preview = client.post("/api/generate/preview", json=payload)
    download = client.post("/api/generate/download", json=payload)

    assert preview.status_code == 200
    assert download.status_code == 200

    preview_yaml = yaml.safe_load(preview.get_json()["yaml"])
    download_yaml = yaml.safe_load(download.data.decode())
    assert download_yaml["mirror"] == preview_yaml["mirror"]

    package = download_yaml["mirror"]["operators"][0]["packages"][0]
    assert package["channels"] == [{"name": "stable-5.8"}]
    assert package["defaultChannel"] == "stable-5.8"


@pytest.mark.parametrize(
    "endpoint",
    ["/api/generate/preview", "/api/generate/download"],
)
def test_generation_invalid_catalog_errors_keep_standard_and_legacy_fields(endpoint):
    app.testing = True
    client = app.test_client()

    response = client.post(
        endpoint,
        json={
            "operators": [
                {"name": "test-operator", "catalog": "evil.registry.io/malicious/index"}
            ]
        },
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["status"] == "error"
    assert "Invalid catalog URL" in payload["message"]
    assert payload["error"] == payload["message"]
    assert payload["success"] is False
    assert "timestamp" in payload


def test_normalize_ocp_minor_version_uses_major_minor():
    from imageset_generator.validation import normalize_ocp_minor_version

    assert normalize_ocp_minor_version("4.17") == "4.17"
    assert normalize_ocp_minor_version("4.17.9") == "4.17"
    assert normalize_ocp_minor_version("v4.17") == "v4.17"
