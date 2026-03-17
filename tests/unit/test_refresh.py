#!/usr/bin/env python3
"""Tests for Cincinnati-based version/channel refresh."""

import json
from unittest.mock import patch, MagicMock

import pytest

from imageset_generator.app import app


@pytest.fixture
def client():
    app.testing = True
    return app.test_client()


def _mock_cincinnati_response(versions):
    """Build a Cincinnati-style response with the given version strings."""
    return {"nodes": [{"version": v} for v in versions]}


@patch("imageset_generator.app.discover_ocp_versions")
def test_refresh_versions_success(mock_discover, client):
    mock_discover.return_value = ["4.14", "4.15", "4.16"]

    response = client.post("/api/versions/refresh")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "success"
    assert payload["releases"] == ["4.14", "4.15", "4.16"]
    assert payload["source"] == "cincinnati"


@patch("imageset_generator.app.discover_ocp_versions")
def test_refresh_versions_empty(mock_discover, client):
    mock_discover.return_value = []

    response = client.post("/api/versions/refresh")

    assert response.status_code == 500
    payload = response.get_json()
    assert payload["status"] == "error"


@patch("imageset_generator.app.discover_channel_releases")
def test_refresh_releases_success(mock_releases, client):
    """Test refresh_ocp_releases called internally (version/channel are function kwargs)."""
    mock_releases.return_value = ["4.16.0", "4.16.1", "4.16.2"]

    from imageset_generator.app import refresh_ocp_releases

    with app.test_request_context():
        response = refresh_ocp_releases(version="4.16", channel="stable-4.16")

    payload = response.get_json()
    assert payload["status"] == "success"
    assert "stable-4.16" in payload["channel_releases"]
    assert payload["source"] == "cincinnati"


@patch("imageset_generator.app.discover_channels_for_version")
def test_refresh_channels_success(mock_channels, client, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    mock_channels.return_value = ["candidate-4.16", "fast-4.16", "stable-4.16"]

    response = client.post("/api/channels/refresh?version=4.16")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "success"
    assert payload["source"] == "cincinnati"


@patch("imageset_generator.app.discover_ocp_versions")
def test_refresh_versions_passes_arch(mock_discover, client):
    """Verify that arch query param is forwarded to discover_ocp_versions."""
    mock_discover.return_value = ["4.16"]

    response = client.post("/api/versions/refresh?arch=arm64")

    assert response.status_code == 200
    mock_discover.assert_called_once_with(arch="arm64")


@patch("imageset_generator.app.discover_ocp_versions")
def test_refresh_versions_defaults_to_amd64(mock_discover, client):
    """Omitting arch should default to amd64."""
    mock_discover.return_value = ["4.16"]

    response = client.post("/api/versions/refresh")

    assert response.status_code == 200
    mock_discover.assert_called_once_with(arch="amd64")


@patch("imageset_generator.app.discover_channels_for_version")
def test_refresh_channels_passes_arch(mock_channels, client, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    mock_channels.return_value = ["stable-4.16"]

    response = client.post("/api/channels/refresh?version=4.16&arch=s390x")

    assert response.status_code == 200
    mock_channels.assert_called_once_with("4.16", arch="s390x")


@patch("imageset_generator.app.discover_channel_releases")
def test_refresh_releases_passes_arch(mock_releases, client):
    """Verify arch is forwarded to discover_channel_releases."""
    mock_releases.return_value = ["4.16.0"]

    from imageset_generator.app import refresh_ocp_releases

    with app.test_request_context("/?arch=ppc64le"):
        response = refresh_ocp_releases(version="4.16", channel="stable-4.16")

    payload = response.get_json()
    assert payload["status"] == "success"
    mock_releases.assert_called_once_with("stable-4.16", arch="ppc64le")


def test_arch_scoped_filename_helper():
    """_arch_scoped_filename scopes cache files by architecture."""
    from imageset_generator.app import _arch_scoped_filename

    # amd64 (default) keeps the original filename for seed-data compat
    assert _arch_scoped_filename("ocp-versions.json", "amd64") == "ocp-versions.json"
    assert _arch_scoped_filename("channel-releases.json", "amd64") == "channel-releases.json"

    # Non-amd64 architectures get a scoped filename
    assert _arch_scoped_filename("ocp-versions.json", "arm64") == "ocp-versions-arm64.json"
    assert _arch_scoped_filename("channel-releases.json", "s390x") == "channel-releases-s390x.json"
    assert _arch_scoped_filename("ocp-channels.json", "ppc64le") == "ocp-channels-ppc64le.json"


@patch("imageset_generator.app._data_write_file")
@patch("imageset_generator.app.discover_ocp_versions")
def test_refresh_versions_writes_arch_scoped_file(mock_discover, mock_write, client):
    """Refreshing for arm64 should write to ocp-versions-arm64.json, not ocp-versions.json."""
    from pathlib import Path
    mock_discover.return_value = ["4.16"]
    mock_write.return_value = Path("/tmp/fake-ocp-versions-arm64.json")

    response = client.post("/api/versions/refresh?arch=arm64")

    assert response.status_code == 200
    mock_write.assert_called_once_with("ocp-versions-arm64.json")


@patch("imageset_generator.app._data_write_file")
@patch("imageset_generator.app.discover_channel_releases")
def test_refresh_releases_writes_arch_scoped_file(mock_releases, mock_write, client):
    """Refreshing releases for s390x should write to channel-releases-s390x.json."""
    from pathlib import Path
    mock_releases.return_value = ["4.16.0"]
    mock_write.return_value = Path("/tmp/fake-channel-releases-s390x.json")

    from imageset_generator.app import refresh_ocp_releases

    with app.test_request_context("/?arch=s390x"):
        response = refresh_ocp_releases(version="4.16", channel="stable-4.16")

    assert response.get_json()["status"] == "success"
    mock_write.assert_called_once_with("channel-releases-s390x.json")


@patch("imageset_generator.app._data_write_file")
@patch("imageset_generator.app.discover_channels_for_version")
def test_refresh_channels_writes_arch_scoped_file(mock_channels, mock_write, client):
    """Refreshing channels for ppc64le should write to ocp-channels-ppc64le.json."""
    from pathlib import Path
    mock_channels.return_value = ["stable-4.16"]
    mock_write.return_value = Path("/tmp/fake-ocp-channels-ppc64le.json")

    response = client.post("/api/channels/refresh?version=4.16&arch=ppc64le")

    assert response.status_code == 200
    mock_write.assert_called_once_with("ocp-channels-ppc64le.json")


@patch("imageset_generator.app._data_read_file")
def test_get_releases_reads_arch_scoped_file(mock_read, client, tmp_path):
    """GET /api/releases/<v>/<ch>?arch=arm64 should read channel-releases-arm64.json."""
    import json
    cache_file = tmp_path / "channel-releases-arm64.json"
    cache_file.write_text(json.dumps({
        "channel_releases": {"stable-4.16": ["4.16.0", "4.16.1"]}
    }))
    mock_read.return_value = cache_file

    response = client.get("/api/releases/4.16/stable-4.16?arch=arm64")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["releases"] == ["4.16.0", "4.16.1"]
    mock_read.assert_called_once_with("channel-releases-arm64.json")


@patch("imageset_generator.app._data_read_file")
def test_get_channels_reads_arch_scoped_file(mock_read, client, tmp_path):
    """GET /api/channels/<v>?arch=ppc64le should read ocp-channels-ppc64le.json."""
    import json
    cache_file = tmp_path / "ocp-channels-ppc64le.json"
    cache_file.write_text(json.dumps({
        "channels": {"4.16": ["stable-4.16", "fast-4.16"]}
    }))
    mock_read.return_value = cache_file

    response = client.get("/api/channels/4.16?arch=ppc64le")

    assert response.status_code == 200
    payload = response.get_json()
    assert "stable-4.16" in payload["channels"]
    mock_read.assert_called_once_with("ocp-channels-ppc64le.json")


@patch("imageset_generator.app.load_operators_from_file")
def test_operators_list_cache_miss_returns_refreshed_operators(
    mock_load, client
):
    """When cached operators file is empty, /api/operators/list should call
    _refresh_operators_data and return the operator list as JSON."""
    expected_operators = [
        {"name": "elasticsearch-operator", "channels": ["stable"]},
        {"name": "cluster-logging", "channels": ["stable-5.8"]},
    ]
    mock_load.return_value = None

    with patch("imageset_generator.app._refresh_operators_data") as mock_refresh:
        mock_refresh.return_value = expected_operators

        response = client.get(
            "/api/operators/list"
            "?catalog=registry.redhat.io/redhat/redhat-operator-index"
            "&version=4.17"
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "success"
    assert len(payload["operators"]) == 2
    assert payload["operators"][0]["name"] == "elasticsearch-operator"


def test_channels_endpoint_returns_sorted_channels(client, tmp_path):
    """Channels for /api/channels/<version> should be sorted:
    selected version first, then ascending by version,
    within each version: stable > fast > eus > candidate."""
    # Prepare a static ocp-channels.json with unsorted data
    channels_data = {
        "channels": {
            "4.20": [
                "candidate-4.22",
                "eus-4.20",
                "stable-4.21",
                "fast-4.18",
                "fast-4.19",
                "stable-4.20",
                "candidate-4.18",
                "eus-4.18",
                "candidate-4.19",
                "stable-4.19",
                "candidate-4.20",
                "stable-4.18",
                "fast-4.20",
                "candidate-4.21",
                "fast-4.21",
            ]
        }
    }

    with patch("imageset_generator.app._data_read_file") as mock_path:
        static_file = tmp_path / "ocp-channels.json"
        static_file.write_text(json.dumps(channels_data))
        mock_path.return_value = static_file

        response = client.get("/api/channels/4.20")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["channels"] == [
        # selected version (4.20) first
        "stable-4.20",
        "fast-4.20",
        "eus-4.20",
        "candidate-4.20",
        # then ascending by version
        "stable-4.18",
        "fast-4.18",
        "eus-4.18",
        "candidate-4.18",
        "stable-4.19",
        "fast-4.19",
        "candidate-4.19",
        "stable-4.21",
        "fast-4.21",
        "candidate-4.21",
        "candidate-4.22",
    ]
