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
