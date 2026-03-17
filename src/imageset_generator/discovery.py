"""
Cincinnati API client for OCP version and channel discovery.

Replaces oc-mirror v1 `list releases` and `list operators` subcommands
which were removed in oc-mirror v2.
"""

import logging
from typing import Optional

import requests

from .constants import (
    CINCINNATI_API_URL,
    CINCINNATI_CHANNEL_PREFIXES,
    OCP_MINOR_PROBE_RANGE,
    TIMEOUT_CINCINNATI,
    TLS_VERIFY,
)

logger = logging.getLogger(__name__)

_session: Optional[requests.Session] = None


def _get_session() -> requests.Session:
    """Return a module-level requests session for connection pooling."""
    global _session
    if _session is None:
        _session = requests.Session()
        _session.verify = TLS_VERIFY
        _session.headers.update({
            "Accept": "application/json",
        })
    return _session


def _query_cincinnati(channel: str, arch: str = "amd64") -> Optional[dict]:
    """
    Query the Cincinnati API for a given channel and architecture.

    Returns the parsed JSON response or None on failure.
    """
    params = {"channel": channel, "arch": arch}
    try:
        resp = _get_session().get(
            CINCINNATI_API_URL,
            params=params,
            timeout=TIMEOUT_CINCINNATI,
        )
        if resp.status_code == 200:
            return resp.json()
        logger.debug(
            "Cincinnati returned %d for channel=%s arch=%s",
            resp.status_code, channel, arch,
        )
        return None
    except requests.RequestException as exc:
        logger.warning("Cincinnati request failed for channel=%s: %s", channel, exc)
        return None


def discover_ocp_versions(arch: str = "amd64") -> list[str]:
    """
    Probe Cincinnati for available OCP minor versions.

    Tries ``stable-4.X`` for X in the configured probe range.
    Returns sorted list like ``["4.14", "4.15", "4.16"]``.
    """
    versions: list[str] = []
    for minor in OCP_MINOR_PROBE_RANGE:
        channel = f"stable-4.{minor}"
        data = _query_cincinnati(channel, arch)
        if data and data.get("nodes"):
            versions.append(f"4.{minor}")
    versions.sort(key=lambda v: tuple(int(p) for p in v.split(".")))
    return versions


def discover_channels_for_version(version: str, arch: str = "amd64") -> list[str]:
    """
    Discover which channels exist for a given OCP version.

    Probes ``{prefix}-{version}`` for each prefix in CINCINNATI_CHANNEL_PREFIXES.
    Returns list like ``["candidate-4.16", "fast-4.16", "stable-4.16"]``.
    """
    channels: list[str] = []
    for prefix in CINCINNATI_CHANNEL_PREFIXES:
        channel = f"{prefix}-{version}"
        data = _query_cincinnati(channel, arch)
        if data and data.get("nodes"):
            channels.append(channel)
    return channels


def _version_sort_key(version: str) -> tuple:
    """Parse a version string into a sort key, handling prerelease tags like 4.18.0-rc.0."""
    base, _, prerelease = version.partition("-")
    parts = []
    for segment in base.split("."):
        try:
            parts.append(int(segment))
        except ValueError:
            parts.append(segment)
    if prerelease:
        pre_parts = []
        for seg in prerelease.split("."):
            try:
                pre_parts.append((0, int(seg)))
            except ValueError:
                pre_parts.append((1, seg))
        return (*parts, 0, *pre_parts)
    return (*parts, 1)


def discover_channel_releases(channel: str, arch: str = "amd64") -> list[str]:
    """
    Get all release versions available in a Cincinnati channel.

    Returns sorted list like ``["4.16.0", "4.16.1", "4.16.2"]``.
    """
    data = _query_cincinnati(channel, arch)
    if not data or not data.get("nodes"):
        return []
    releases = [node["version"] for node in data["nodes"] if "version" in node]
    releases.sort(key=lambda v: _version_sort_key(v))
    return releases


def get_latest_ocp_version(arch: str = "amd64") -> Optional[str]:
    """Return the highest available OCP minor version, or None."""
    versions = discover_ocp_versions(arch)
    return versions[-1] if versions else None
