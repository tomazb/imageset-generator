#!/usr/bin/env python3
"""
Constants for ImageSet Generator

Centralized configuration constants for timeouts, ports, patterns, and defaults.
"""

import os
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent


def _looks_like_repo_root(path: Path) -> bool:
    """Return True when the given path looks like a repo checkout root."""
    return (
        (path / "pyproject.toml").exists()
        and (path / "src" / "imageset_generator").is_dir()
    )


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


def get_data_read_path(filename: str) -> Path:
    """Prefer the writable cache, then packaged seed data."""
    runtime_path = get_runtime_data_path(filename)
    if runtime_path.exists():
        return runtime_path
    return get_packaged_data_path(filename)


def get_data_write_path(filename: str) -> Path:
    """Return a writable cache file path, creating the directory if needed."""
    RUNTIME_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return get_runtime_data_path(filename)

# Network Timeouts (seconds)
TIMEOUT_OC_MIRROR_SHORT = 30      # For list operations
TIMEOUT_OC_MIRROR_MEDIUM = 120    # For catalog listings
TIMEOUT_OC_MIRROR_LONG = 180      # For render operations
TIMEOUT_OPM_RENDER = 180          # For opm render commands
TIMEOUT_CATALOG_DISCOVERY = 300   # For catalog discovery

# Server Configuration
DEFAULT_PORT = 5000
DEBUG_MODE = os.environ.get('DEBUG_MODE', 'False').lower() == 'true'

# Version Patterns
VERSION_PATTERN = r'^\d+\.\d+$'                    # X.Y format
CHANNEL_PATTERN = r'^[a-zA-Z][a-zA-Z0-9\-]*\d+\.\d+$'  # stable-X.Y format

# Catalog Configuration
CATALOG_REGISTRY = "registry.redhat.io"
CATALOG_ORG = "redhat"

# Base Catalogs
BASE_CATALOGS = [
    {
        "name": "Red Hat Operators",
        "base_url": f"{CATALOG_REGISTRY}/{CATALOG_ORG}/redhat-operator-index",
        "description": "Official Red Hat certified operators",
        "default": True
    },
    {
        "name": "Community Operators",
        "base_url": f"{CATALOG_REGISTRY}/{CATALOG_ORG}/community-operator-index",
        "description": "Community-maintained operators",
        "default": False
    },
    {
        "name": "Certified Operators",
        "base_url": f"{CATALOG_REGISTRY}/{CATALOG_ORG}/certified-operator-index",
        "description": "Third-party certified operators",
        "default": False
    },
    {
        "name": "Red Hat Marketplace",
        "base_url": f"{CATALOG_REGISTRY}/{CATALOG_ORG}/redhat-marketplace-index",
        "description": "Commercial operators from Red Hat Marketplace",
        "default": False
    }
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
    "kiali": "kiali-ossm"
}

# File Paths
DATA_DIR = "data"
FRONTEND_BUILD_DIR = str(
    _prefer_existing(
        PROJECT_ROOT / "frontend" / "build",
        PACKAGED_FRONTEND_BUILD_DIR,
    )
)

# Cache File Names
CACHE_OCP_VERSIONS = "ocp-versions.json"
CACHE_OCP_CHANNELS = "ocp-channels.json"
CACHE_CHANNEL_RELEASES = "channel-releases.json"

# TLS Configuration
TLS_VERIFY = True  # Set to False to skip TLS verification (not recommended)

# API Response Metadata
API_VERSION = "1.0.0"
API_NAME = "ImageSet Generator API"
