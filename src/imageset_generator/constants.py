#!/usr/bin/env python3
"""
Constants for ImageSet Generator

Centralized configuration constants for timeouts, ports, patterns, and defaults.
"""

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

PACKAGE_ROOT = Path(__file__).resolve().parent


def _looks_like_repo_root(path: Path) -> bool:
    """Return True when the given path looks like a repo checkout root."""
    return (path / "pyproject.toml").exists() and (
        path / "src" / "imageset_generator"
    ).is_dir()


def _resolve_project_root() -> Path | None:
    """Resolve a checkout root when available, allowing runtime overrides."""
    env_root = os.environ.get("IMAGESET_GENERATOR_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()

    candidate = PACKAGE_ROOT.parents[1]
    if _looks_like_repo_root(candidate):
        return candidate

    return None


def _resolve_runtime_root(project_root: Path | None) -> Path:
    """Resolve the writable runtime root."""
    if project_root is not None:
        return project_root
    return Path.cwd().resolve()


def _prefer_existing(*paths: Path) -> Path:
    """Return the first existing path, or the final fallback."""
    for path in paths:
        if path.exists():
            return path
    return paths[-1]


_CHECKOUT_ROOT = _resolve_project_root()
RUNTIME_ROOT = _resolve_runtime_root(_CHECKOUT_ROOT)
PROJECT_ROOT = _CHECKOUT_ROOT or PACKAGE_ROOT

PACKAGED_DATA_DIR = PACKAGE_ROOT / "data"
PACKAGED_FRONTEND_BUILD_DIR = PACKAGE_ROOT / "frontend" / "build"
PACKAGED_AUTOMATION_CONFIG_PATH = PACKAGE_ROOT / "automation" / "config.yaml"
RUNTIME_DATA_DIR = RUNTIME_ROOT / "data"
AUTOMATION_CONFIG_PATH = _prefer_existing(
    PROJECT_ROOT / "automation" / "config.yaml",
    PACKAGED_AUTOMATION_CONFIG_PATH,
)


def get_packaged_data_path(filename: str) -> Path:
    """Return the packaged read-only data file path."""
    return PACKAGED_DATA_DIR / filename


def get_runtime_data_path(filename: str) -> Path:
    """Return the writable runtime data file path."""
    return RUNTIME_DATA_DIR / filename


# Cache reliability settings
CACHE_FILE_MAX_AGE_SECONDS = int(
    os.environ.get("CACHE_FILE_MAX_AGE_SECONDS", str(24 * 3600))
)  # Default: 24 hours

# Minimum entry counts for cache files to be considered plausible.
# Keys are filename prefixes (matched via str.startswith).
CACHE_MIN_COUNTS: dict[str, int] = {
    "ocp-versions": 3,
    "ocp-channels": 1,
    "channel-releases": 1,
}


def _cache_file_is_fresh(path: Path) -> bool:
    """Return True if the cache file's embedded timestamp is within max age."""
    try:
        with open(path) as f:
            data = json.load(f)
        ts_str = data.get("timestamp")
        if not ts_str:
            return False
        ts = datetime.fromisoformat(ts_str)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - ts).total_seconds()
        return age < CACHE_FILE_MAX_AGE_SECONDS
    except Exception:
        return False


def _cache_file_is_plausible(path: Path) -> bool:
    """Return True if the cache file meets minimum completeness thresholds."""
    stem = path.stem  # e.g. "ocp-versions" or "ocp-versions-arm64"
    min_count = None
    for prefix, threshold in CACHE_MIN_COUNTS.items():
        if stem.startswith(prefix):
            min_count = threshold
            break
    if min_count is None:
        return True  # no threshold defined — accept

    try:
        with open(path) as f:
            data = json.load(f)
        # Check common payload keys for entry count
        for key in ("releases", "channels", "channel_releases"):
            value = data.get(key)
            if isinstance(value, (list, dict)) and len(value) >= min_count:
                return True
        return False
    except Exception:
        return False


def get_data_read_path(filename: str) -> Path:
    """Prefer a fresh, plausible writable cache, then packaged seed data."""
    runtime_path = get_runtime_data_path(filename)
    if runtime_path.exists():
        if not _cache_file_is_fresh(runtime_path):
            logger.warning(
                "Runtime cache %s is stale (older than %ds), falling through to seed data",
                runtime_path,
                CACHE_FILE_MAX_AGE_SECONDS,
            )
        elif not _cache_file_is_plausible(runtime_path):
            logger.warning(
                "Runtime cache %s has too few entries, falling through to seed data",
                runtime_path,
            )
        else:
            return runtime_path
    return get_packaged_data_path(filename)


def get_data_write_path(filename: str) -> Path:
    """Return a writable cache file path, creating the directory if needed."""
    RUNTIME_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return get_runtime_data_path(filename)


def atomic_json_dump(data: dict, path: Path) -> None:
    """Write *data* as JSON to *path* atomically via temp-file + rename.

    This prevents readers from ever seeing a truncated or partially-written
    cache file.  The temp file is created in the same directory so the rename
    is guaranteed to be atomic on POSIX systems.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        # Clean up the temp file on any failure
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# Network Timeouts (seconds)
TIMEOUT_OC_MIRROR_SHORT = 30  # For list operations
TIMEOUT_OC_MIRROR_MEDIUM = 120  # For catalog listings
TIMEOUT_OC_MIRROR_LONG = 180  # For render operations
TIMEOUT_OPM_RENDER = 180  # For opm render commands
TIMEOUT_CATALOG_DISCOVERY = 300  # For catalog discovery
TIMEOUT_CINCINNATI = 15  # For Cincinnati API requests
TIMEOUT_SKOPEO = 30  # For skopeo inspect commands
TIMEOUT_JQ = 60  # For jq filter commands
TIMEOUT_NOTIFICATION_REQUEST = 10  # For outbound notification webhooks

# Cincinnati API Configuration
CINCINNATI_API_URL = "https://api.openshift.com/api/upgrades_info/v1/graph"
CINCINNATI_CHANNEL_PREFIXES = ["candidate", "fast", "stable", "eus"]
OCP_MINOR_PROBE_RANGE = range(12, 30)

# Server Configuration
DEFAULT_PORT = 5000
DEBUG_MODE = os.environ.get("DEBUG_MODE", "False").lower() == "true"
MAX_CONTENT_LENGTH_BYTES = 16 * 1024 * 1024

# Version Patterns
VERSION_PATTERN = r"^\d+\.\d+$"  # X.Y format
CHANNEL_PATTERN = r"^[a-zA-Z][a-zA-Z0-9\-]*\d+\.\d+$"  # stable-X.Y format

# Catalog Configuration
CATALOG_REGISTRY = "registry.redhat.io"
CATALOG_ORG = "redhat"
DEFAULT_OCP_VERSION = "4.18"
DEFAULT_OCP_CHANNEL = "stable-4.14"
DEFAULT_OPERATOR_CATALOG = f"{CATALOG_REGISTRY}/{CATALOG_ORG}/redhat-operator-index"

# Base Catalogs
BASE_CATALOGS = [
    {
        "name": "Red Hat Operators",
        "base_url": f"{CATALOG_REGISTRY}/{CATALOG_ORG}/redhat-operator-index",
        "description": "Official Red Hat certified operators",
        "default": True,
    },
    {
        "name": "Community Operators",
        "base_url": f"{CATALOG_REGISTRY}/{CATALOG_ORG}/community-operator-index",
        "description": "Community-maintained operators",
        "default": False,
    },
    {
        "name": "Certified Operators",
        "base_url": f"{CATALOG_REGISTRY}/{CATALOG_ORG}/certified-operator-index",
        "description": "Third-party certified operators",
        "default": False,
    },
    {
        "name": "Red Hat Marketplace",
        "base_url": f"{CATALOG_REGISTRY}/{CATALOG_ORG}/redhat-marketplace-index",
        "description": "Commercial operators from Red Hat Marketplace",
        "default": False,
    },
]

# Operator Name Mappings
OPERATOR_MAPPINGS = {
    "logging": "cluster-logging",
    "logging-operator": "cluster-logging",
    "monitoring": "cluster-monitoring-operator",
    "cluster-monitoring": "cluster-monitoring-operator",
    "service-mesh": "servicemeshoperator",
    "istio": "servicemeshoperator",
    "serverless": "serverless-operator",
    "knative": "serverless-operator",
    "pipelines": "openshift-pipelines-operator-rh",
    "tekton": "openshift-pipelines-operator-rh",
    "gitops": "openshift-gitops-operator",
    "argocd": "openshift-gitops-operator",
    "storage": "odf-operator",
    "ocs": "odf-operator",
    "ceph": "odf-operator",
    "elasticsearch": "elasticsearch-operator",
    "jaeger": "jaeger-product",
    "kiali": "kiali-ossm",
}

# File Paths
DATA_DIR = "data"
FRONTEND_BUILD_DIR = str(PACKAGED_FRONTEND_BUILD_DIR)

# Cache File Names
CACHE_OCP_VERSIONS = "ocp-versions.json"
CACHE_OCP_CHANNELS = "ocp-channels.json"
CACHE_CHANNEL_RELEASES = "channel-releases.json"

# TLS Configuration
TLS_VERIFY = True  # Set to False to skip TLS verification (not recommended)

# API Response Metadata
API_VERSION = "1.0.0"
API_NAME = "ImageSet Generator API"
