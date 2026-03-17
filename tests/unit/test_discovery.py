"""Unit tests for the Cincinnati API discovery module."""

from unittest.mock import MagicMock, patch

from imageset_generator.discovery import (
    _query_cincinnati,
    discover_channel_releases,
    discover_channels_for_version,
    discover_ocp_versions,
    get_latest_ocp_version,
)


def _make_response(nodes, status_code=200):
    """Build a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = {"nodes": nodes}
    return resp


def _make_nodes(versions):
    return [{"version": v} for v in versions]


class TestQueryCincinnati:
    @patch("imageset_generator.discovery._get_session")
    def test_success(self, mock_session_fn):
        session = MagicMock()
        mock_session_fn.return_value = session
        session.get.return_value = _make_response(_make_nodes(["4.16.0"]))

        result = _query_cincinnati("stable-4.16")

        assert result == {"nodes": [{"version": "4.16.0"}]}
        session.get.assert_called_once()

    @patch("imageset_generator.discovery._get_session")
    def test_non_200_returns_none(self, mock_session_fn):
        session = MagicMock()
        mock_session_fn.return_value = session
        session.get.return_value = _make_response([], status_code=404)

        result = _query_cincinnati("stable-4.99")

        assert result is None

    @patch("imageset_generator.discovery._get_session")
    def test_request_exception_returns_none(self, mock_session_fn):
        import requests

        session = MagicMock()
        mock_session_fn.return_value = session
        session.get.side_effect = requests.ConnectionError("fail")

        result = _query_cincinnati("stable-4.16")

        assert result is None


class TestDiscoverOcpVersions:
    @patch("imageset_generator.discovery._query_cincinnati")
    def test_returns_valid_versions(self, mock_query):
        def side_effect(channel, arch="amd64"):
            if channel in ("stable-4.14", "stable-4.15", "stable-4.16"):
                return {"nodes": [{"version": f"{channel.split('-')[1]}.0"}]}
            return None

        mock_query.side_effect = side_effect

        result = discover_ocp_versions()

        assert "4.14" in result
        assert "4.15" in result
        assert "4.16" in result

    @patch("imageset_generator.discovery._query_cincinnati")
    def test_returns_empty_when_nothing_found(self, mock_query):
        mock_query.return_value = None

        result = discover_ocp_versions()

        assert result == []

    @patch("imageset_generator.discovery._query_cincinnati")
    def test_finds_version_on_candidate_only(self, mock_query):
        """A version only on candidate (not stable) should still be discovered."""

        def side_effect(channel, arch="amd64"):
            # 4.19 only exists on candidate, not stable/fast/eus
            if channel == "candidate-4.19":
                return {"nodes": [{"version": "4.19.0"}]}
            if channel == "stable-4.16":
                return {"nodes": [{"version": "4.16.0"}]}
            return None

        mock_query.side_effect = side_effect

        result = discover_ocp_versions()

        assert "4.16" in result
        assert "4.19" in result


class TestDiscoverChannelsForVersion:
    @patch("imageset_generator.discovery._query_cincinnati")
    def test_returns_valid_channels(self, mock_query):
        def side_effect(channel, arch="amd64"):
            if channel in ("candidate-4.16", "stable-4.16"):
                return {"nodes": [{"version": "4.16.0"}]}
            return None

        mock_query.side_effect = side_effect

        result = discover_channels_for_version("4.16")

        assert "candidate-4.16" in result
        assert "stable-4.16" in result
        assert "fast-4.16" not in result
        assert "eus-4.16" not in result


class TestDiscoverChannelReleases:
    @patch("imageset_generator.discovery._query_cincinnati")
    def test_returns_sorted_releases(self, mock_query):
        mock_query.return_value = {"nodes": _make_nodes(["4.16.2", "4.16.0", "4.16.1"])}

        result = discover_channel_releases("stable-4.16")

        assert result == ["4.16.0", "4.16.1", "4.16.2"]

    @patch("imageset_generator.discovery._query_cincinnati")
    def test_returns_sorted_prerelease_versions(self, mock_query):
        mock_query.return_value = {
            "nodes": _make_nodes(
                [
                    "4.18.0-rc.10",
                    "4.18.0-rc.2",
                    "4.18.0-ec.0",
                    "4.18.0",
                    "4.18.0-rc.1",
                ]
            )
        }

        result = discover_channel_releases("candidate-4.18")

        assert result == [
            "4.18.0-ec.0",
            "4.18.0-rc.1",
            "4.18.0-rc.2",
            "4.18.0-rc.10",
            "4.18.0",
        ]

    @patch("imageset_generator.discovery._query_cincinnati")
    def test_returns_empty_on_failure(self, mock_query):
        mock_query.return_value = None

        result = discover_channel_releases("stable-4.99")

        assert result == []


class TestGetLatestOcpVersion:
    @patch("imageset_generator.discovery.discover_ocp_versions")
    def test_returns_highest(self, mock_discover):
        mock_discover.return_value = ["4.14", "4.15", "4.16"]

        result = get_latest_ocp_version()

        assert result == "4.16"

    @patch("imageset_generator.discovery.discover_ocp_versions")
    def test_returns_none_when_empty(self, mock_discover):
        mock_discover.return_value = []

        result = get_latest_ocp_version()

        assert result is None
