#!/usr/bin/env python3
"""
OpenShift ImageSetConfiguration Generator - Flask API Backend

This Flask application provides a REST API for the OpenShift ImageSetConfiguration generator.
It serves as the backend for the React frontend application.
"""

import json
import os
import re
import subprocess
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path

import yaml
from flask import Flask, abort, jsonify, request, send_from_directory
from flask_cors import CORS
from packaging.version import Version as Version_Checker

from .constants import (
    AUTOMATION_CONFIG_PATH,
    BASE_CATALOGS,
    FRONTEND_BUILD_DIR,
    OPERATOR_MAPPINGS,
    TIMEOUT_OPM_RENDER,
    TIMEOUT_SKOPEO,
    TLS_VERIFY,
    atomic_json_dump,
    get_data_read_path,
    get_data_write_path,
)
from .discovery import (
    discover_channel_releases,
    discover_channels_for_version,
    discover_ocp_versions,
)
from .exceptions import CatalogError, CatalogRenderError
from .generator import ImageSetGenerator
from .validation import (
    ValidationError,
    validate_catalog_url,
    validate_channel,
    validate_version,
)


def build_opm_command(catalog_url, output_format="yaml", skip_tls=None):
    """
    Build OPM render command with configurable TLS verification.

    Args:
        catalog_url: Full catalog URL (e.g., registry.redhat.io/redhat/redhat-operator-index:v4.18)
        output_format: Output format for OPM (default: 'yaml', can be 'json')
        skip_tls: Override TLS verification (None uses TLS_VERIFY constant from constants.py)

    Returns:
        List of command arguments for subprocess
    """
    cmd = ["opm", "render"]

    # Use provided skip_tls value, or default to TLS_VERIFY constant
    should_skip_tls = skip_tls if skip_tls is not None else not TLS_VERIFY

    if should_skip_tls:
        cmd.append("--skip-tls")

    if output_format == "json":
        cmd.extend(["--output", "json"])

    cmd.append(catalog_url)
    return cmd


def build_skopeo_command(subcommand, image_ref, skip_tls=None, extra_args=None):
    """
    Build skopeo command with configurable TLS verification.

    Args:
        subcommand: skopeo subcommand (e.g., 'inspect', 'list-tags')
        image_ref: Image reference (e.g., 'docker://registry.redhat.io/redhat/redhat-operator-index:v4.18')
        skip_tls: Override TLS verification (None uses TLS_VERIFY constant from constants.py)
        extra_args: Additional arguments to pass before the image reference

    Returns:
        List of command arguments for subprocess
    """
    cmd = ["skopeo", subcommand]

    # Use provided skip_tls value, or default to TLS_VERIFY constant
    should_skip_tls = skip_tls if skip_tls is not None else not TLS_VERIFY

    if should_skip_tls:
        cmd.append("--tls-verify=false")

    if extra_args:
        cmd.extend(extra_args)

    cmd.append(image_ref)
    return cmd


def process_operator_data(operator):
    """Process operator data to handle selected versions and other parameters"""
    if isinstance(operator, str):
        return {
            "name": operator.strip(),
            "catalog": None,
            "channel": None,
            "version": None,
            "minVersion": None,
            "maxVersion": None,
            "selectedVersions": None,
            "fileName": None,
        }
    elif isinstance(operator, dict):
        return {
            "name": (
                operator.get("name", "").strip()
                if isinstance(operator.get("name"), str)
                else ""
            ),
            "catalog": (
                operator.get("catalog", "").strip()
                if isinstance(operator.get("catalog"), str)
                else None
            ),
            "channel": (
                operator.get("channel", "").strip()
                if isinstance(operator.get("channel"), str)
                else None
            ),
            "version": (
                operator.get("version", "").strip()
                if isinstance(operator.get("version"), str)
                else None
            ),
            "minVersion": (
                operator.get("minVersion", "").strip()
                if isinstance(operator.get("minVersion"), str)
                else None
            ),
            "maxVersion": (
                operator.get("maxVersion", "").strip()
                if isinstance(operator.get("maxVersion"), str)
                else None
            ),
            "selectedVersions": (
                operator.get("selectedVersions", [])
                if isinstance(operator.get("selectedVersions"), list)
                else None
            ),
            "fileName": operator.get("fileName") if operator.get("fileName") else None,
        }
    else:
        return None


def prepare_operator_entry(op_data):
    """Prepare operator entry for the generator from processed data"""
    if not op_data or not op_data["name"]:
        return None

    entry = {"name": op_data["name"]}

    if op_data["channel"]:
        entry["channel"] = op_data["channel"]

    if op_data["selectedVersions"]:
        entry["selectedVersions"] = op_data["selectedVersions"]
    else:
        if op_data["minVersion"]:
            entry["minVersion"] = op_data["minVersion"]
        if op_data["maxVersion"]:
            entry["maxVersion"] = op_data["maxVersion"]

    if op_data["fileName"]:
        entry["fileName"] = op_data["fileName"]

    return entry


app = Flask(__name__, static_folder=FRONTEND_BUILD_DIR)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB request size limit
CORS(app)  # Enable CORS for all routes

# Initialize automation (optional - only if config exists)
try:
    from .automation.api import automation_bp, init_automation

    # Register automation blueprint
    app.register_blueprint(automation_bp)

    # Initialize and start automation scheduler
    automation_config_path = str(AUTOMATION_CONFIG_PATH)
    if os.path.exists(automation_config_path):
        scheduler = init_automation(automation_config_path)
        if scheduler:
            app.logger.info("Automation scheduler initialized and started")
        else:
            app.logger.info("Automation scheduler is disabled in configuration")
    else:
        app.logger.info(
            f"Automation config not found at {automation_config_path}, skipping automation"
        )
except ImportError as e:
    app.logger.info(f"Automation module not available: {e}")
except Exception:
    app.logger.exception("Failed to initialize automation")


def return_base_catalog_info(catalog_url):
    for catalog in BASE_CATALOGS:
        if catalog_url.startswith(catalog["base_url"]):
            return dict(catalog)
    return None


def _frontend_build_exists():
    """Return True when the compiled frontend is available to serve."""
    return Path(app.static_folder, "index.html").exists()


def _not_found_response():
    """Return a consistent JSON 404 payload."""
    return (
        jsonify(
            {
                "status": "error",
                "message": "Resource not found",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ),
        404,
    )


def _data_read_file(filename: str) -> Path:
    """Return the cache file to read, preferring runtime overrides."""
    return get_data_read_path(filename)


def _data_write_file(filename: str) -> Path:
    """Return the cache file to write, creating the runtime cache dir."""
    return get_data_write_path(filename)


def _arch_scoped_filename(base_filename: str, arch: str) -> str:
    """Return an architecture-scoped cache filename.

    For the default architecture (amd64), returns the original filename
    so that bundled seed data continues to work.  For any other
    architecture the arch is inserted before the extension, e.g.
    ``ocp-versions.json`` becomes ``ocp-versions-arm64.json``.
    """
    if arch == "amd64":
        return base_filename
    stem, dot, ext = base_filename.rpartition(".")
    if not dot:
        return f"{base_filename}-{arch}"
    return f"{stem}-{arch}.{ext}"


def get_operators_from_opm(catalog_url, version_key):
    """Get operators from a catalog using opm render"""
    try:
        full_catalog = f"{catalog_url}:v{version_key}"
        cmd = build_opm_command(full_catalog)
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=TIMEOUT_OPM_RENDER
        )

        if result.returncode != 0:
            raise CatalogRenderError(
                f"opm render failed: {result.stderr}",
                catalog=full_catalog,
                version=version_key,
            )

        operators = set()
        docs = list(yaml.safe_load_all(result.stdout))
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            if doc.get("kind") == "ClusterServiceVersion":
                metadata = doc.get("metadata", {})
                name = metadata.get("name")
                if name:
                    op_name = name.split(".")[0]
                    operators.add(op_name)

        return sorted(list(operators))
    except CatalogRenderError:
        raise
    except Exception as e:
        raise CatalogError(
            "Error getting operators from opm",
            catalog=catalog_url,
            version=version_key,
            original_error=e,
        )


def get_cached_operators(cache_file):
    """Get operators from cache file if it exists and is not expired"""
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r") as f:
                data = json.load(f)
                return data.get("operators", [])
        except Exception:
            pass
    return None


def load_operators_from_file(catalog_key, version_key):
    """Load operators from cached JSON files"""
    try:
        # Try to load from cache file first
        catalog_index = (catalog_key.split("/")[-1]).split(":")[0]
        static_file_path = _data_read_file(
            f"operators-{catalog_index}-{version_key}.json"
        )

        if static_file_path.exists():
            with open(static_file_path, "r") as f:
                data = json.load(f)
                return data.get("operators", None)

        return None

    except Exception as e:
        app.logger.error(f"Error loading operators from file: {e}")
        return None


def load_catalogs_from_file(version_key):
    """Load catalog information from cached JSON files"""

    try:
        filename = f"catalogs-{version_key}.json"
        filepath = _data_read_file(filename)

        if filepath.exists():
            with open(filepath, "r") as f:
                catalogs = json.load(f)
                return catalogs

        return None

    except Exception as e:
        app.logger.error(f"Error loading catalogs from file: {e}")
        return None


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_react_app(path):
    """Serve React app"""
    if path.startswith("api/"):
        abort(404)

    if path.startswith("static/"):
        static_path = Path(app.static_folder, path)
        if static_path.exists():
            return send_from_directory(app.static_folder, path)
        abort(404)

    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)

    if _frontend_build_exists():
        return send_from_directory(app.static_folder, "index.html")

    abort(404)


@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify(
        {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "1.0.0",
        }
    )


@app.route("/api/versions/refresh", methods=["POST"])
def refresh_versions():
    """Refresh the list of available OCP releases"""
    # Logic to refresh the releases via Cincinnati API
    app.logger.debug("Refreshing OCP releases...")
    releases = []
    arch = request.args.get("arch", "amd64")
    static_file_path = _data_write_file(
        _arch_scoped_filename("ocp-versions.json", arch)
    )
    try:
        # Query Cincinnati API for available OCP versions
        app.logger.debug("Querying Cincinnati API to refresh releases...")
        releases = discover_ocp_versions(arch=arch)

        if not releases:
            app.logger.error("Cincinnati API returned no versions")
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Failed to refresh releases: no versions returned from Cincinnati API",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                ),
                500,
            )

        # Save to static file for future use (atomic write)
        app.logger.debug(f"Saving refreshed releases to {static_file_path}")
        atomic_json_dump(
            {
                "releases": releases,
                "count": len(releases),
                "source": "cincinnati",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            static_file_path,
        )

    except Exception as e:
        app.logger.error(f"Error refreshing releases: {e}")
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Failed to refresh releases. Check server logs for details.",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ),
            500,
        )

    return jsonify(
        {
            "status": "success",
            "releases": releases,
            "count": len(releases),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "cincinnati",
        }
    )


def _get_operator_file_paths(catalog_index, version):
    """
    Generate file paths for operator data storage.

    Args:
        catalog_index: Catalog index name (e.g., 'redhat-operator-index')
        version: Version string (e.g., 'v4.18')

    Returns:
        Tuple of (main_path, index_path, data_path, channel_path)
    """
    base_name = f"operators-{catalog_index}-{version}"
    return (
        str(_data_write_file(f"{base_name}.json")),
        str(_data_write_file(f"{base_name}-index.json")),
        str(_data_write_file(f"{base_name}-data.json")),
        str(_data_write_file(f"{base_name}-channel.json")),
    )


def _render_catalog_index(catalog, output_path):
    """
    Render catalog using OPM and save to file.

    Args:
        catalog: Full catalog URL
        output_path: Path to save rendered output

    Raises:
        subprocess.CalledProcessError: If OPM command fails
    """
    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        return  # File already exists and is not empty

    cmd = build_opm_command(catalog, output_format="json")
    tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(output_path), suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            subprocess.run(cmd, stdout=f, check=True, timeout=TIMEOUT_OPM_RENDER)
        os.replace(tmp_path, output_path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _extract_operator_data(index_path, output_path):
    """
    Extract operator field data using jq filter.

    Args:
        index_path: Path to catalog index file
        output_path: Path to save filtered data

    Raises:
        subprocess.CalledProcessError: If jq command fails
    """
    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        return  # File already exists and is not empty

    jq_filter = """
    select(.schema == "olm.bundle")
    | [
        .package,
        .name,
        (.properties[]? | select(.type == "olm.package") | .value.version),
        ((.properties[]? | select(.type == "olm.csv.metadata") | .value.keywords | join(",")) // ""),
        (.properties[]? | select(.type == "olm.csv.metadata") | .value.annotations.description),
        (.properties[]? | select(.schema == "olm.channel") | .name)
    ] | @tsv
    """

    cmd = ["jq", "-r", jq_filter]
    with open(index_path, "r") as infile, open(output_path, "w") as outfile:
        subprocess.run(cmd, stdin=infile, stdout=outfile, check=True, timeout=60)


def _extract_channel_data(index_path, output_path):
    """
    Extract operator channel data using jq filter.

    Args:
        index_path: Path to catalog index file
        output_path: Path to save channel data

    Raises:
        subprocess.CalledProcessError: If jq command fails
    """
    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        return  # File already exists and is not empty

    jq_filter = """
    select(.schema == "olm.channel")
    | [.package, .name, .entries[]?.name, .channelName] | @tsv
    """

    cmd = ["jq", "-r", jq_filter]
    with open(index_path, "r") as infile, open(output_path, "w") as outfile:
        subprocess.run(cmd, stdin=infile, stdout=outfile, check=True, timeout=60)


def _find_operator_channel(operator_name, channel_path):
    """
    Find the channel for a specific operator.

    Args:
        operator_name: Name of the operator to search for
        channel_path: Path to channel data file

    Returns:
        Channel name if found, empty string otherwise
    """
    try:
        with open(channel_path, "r") as f:
            for line in f:
                if operator_name in line:
                    fields = line.strip().split("\t")
                    if len(fields) > 1 and fields[1]:
                        return fields[1]
    except Exception as e:
        app.logger.warning(f"Could not find channel for {operator_name}: {e}")

    return ""


def _parse_operator_data(data_path, channel_path):
    """
    Parse TSV operator data and enrich with channel information.

    Args:
        data_path: Path to operator data TSV file
        channel_path: Path to channel data TSV file

    Returns:
        List of operator dictionaries
    """
    operators = []

    with open(data_path, "r") as f:
        lines = [line for line in f if line.strip()]

        for line in lines:
            fields = line.strip().split("\t")

            if len(fields) < 3:
                continue  # Skip malformed lines

            operator = {
                "package": fields[0],
                "name": fields[0],
                "version": fields[2] if len(fields) > 2 else "",
            }

            # Add optional fields if available
            if len(fields) >= 5:
                operator["keywords"] = fields[3].split(",") if fields[3] else []
                operator["description"] = fields[4]
                operator["channel"] = fields[5] if len(fields) > 5 else ""

            # Find channel from channel file if not set or to override
            if len(fields) > 1 and fields[1]:
                channel = _find_operator_channel(fields[1], channel_path)
                if channel:
                    operator["channel"] = channel

            operators.append(operator)

    return operators


def _cleanup_intermediate_files(*file_paths):
    """
    Remove intermediate processing files.

    Args:
        *file_paths: Variable number of file paths to remove
    """
    for path in file_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            app.logger.error(f"Error removing {path}: {e}")


def _refresh_operators_data(catalog, version):
    """Refresh operators from catalog via opm and return the operator list.

    Returns a list of operator dicts on success.
    Raises on failure (callers decide how to surface the error).
    """
    # Extract version from catalog if not provided
    if version is None or not version.strip():
        version = catalog.split(":")[-1]

    # Generate file paths
    catalog_index = (catalog.split("/")[-1]).split(":")[0]
    main_path, index_path, data_path, channel_path = _get_operator_file_paths(
        catalog_index, version
    )

    # Step 1: Render catalog index
    _render_catalog_index(catalog, index_path)

    # Step 2: Extract operator data
    _extract_operator_data(index_path, data_path)

    # Step 3: Extract channel data
    _extract_channel_data(index_path, channel_path)

    # Step 4: Parse and combine data
    operators = _parse_operator_data(data_path, channel_path)

    # Step 5: Write final output (atomic write)
    atomic_json_dump(
        {
            "operators": operators,
            "count": len(operators),
            "source": "opm",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        Path(main_path),
    )

    # Step 6: Cleanup intermediate files
    _cleanup_intermediate_files(index_path, data_path, channel_path)

    return operators


@app.route("/api/operators/refresh", methods=["POST"])
def refresh_ocp_operators(catalog=None, version=None):
    """Refresh the list of available OCP operators"""
    app.logger.debug("Refreshing OCP operators...")

    # Extract parameters from request when called via HTTP
    if catalog is None:
        if request and request.is_json:
            data = request.get_json(silent=True) or {}
            catalog = data.get("catalog")
            version = data.get("version", version)
        elif request:
            catalog = request.args.get("catalog")
            version = request.args.get("version", version)

    # Validate required parameters
    if catalog is None:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Catalog parameter is required",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ),
            400,
        )

    try:
        operators = _refresh_operators_data(catalog, version)
        return jsonify(
            {
                "status": "success",
                "data": operators,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
    except subprocess.CalledProcessError as e:
        app.logger.error(f"Error processing catalog: {e}")
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Failed to refresh operators. Check server logs for details.",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ),
            500,
        )
    except Exception as e:
        app.logger.error(f"Error refreshing operators: {e}")
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Failed to refresh operators. Check server logs for details.",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ),
            500,
        )


@app.route("/api/releases/refresh", methods=["POST"])
def refresh_ocp_releases(version=None, channel=None):
    """Refresh the list of available OCP releases for a specific version and channel"""
    app.logger.debug("Refreshing OCP releases...")
    if version is None or channel is None:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Version and channel parameter is required",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ),
            400,
        )

    # Validate version format using centralized validation
    try:
        version = validate_version(version)
    except ValidationError as e:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ),
            400,
        )

    # Validate channel format using centralized validation
    try:
        channel = validate_channel(channel)
    except ValidationError as e:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ),
            400,
        )

    channels_releases = {}
    arch = request.args.get("arch", "amd64")
    static_file_path = _data_write_file(
        _arch_scoped_filename("channel-releases.json", arch)
    )
    try:
        # Query Cincinnati API for channel releases
        app.logger.debug(
            f"Querying Cincinnati API for releases in channel {channel}..."
        )
        release_list = discover_channel_releases(channel, arch=arch)

        if release_list:
            channels_releases[channel] = release_list

        # Try to load from static file first
        old_channels_releases = {}
        try:
            if static_file_path.exists():
                with open(static_file_path, "r") as f:
                    data = json.load(f)
                old_channels_releases = data.get("channel_releases", {})
        except Exception as e:
            app.logger.warning(f"Could not load static OCP versions file: {e}")

        # Merge old channels with new ones
        old_channels_releases.update(channels_releases)

        # Save to static file for future use (atomic write)
        app.logger.debug(f"Saving refreshed releases to {static_file_path}")
        atomic_json_dump(
            {
                "channel_releases": old_channels_releases,
                "count": len(old_channels_releases),
                "source": "cincinnati",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            static_file_path,
        )

    except Exception as e:
        app.logger.error(f"Error refreshing releases: {e}")
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Failed to refresh releases. Check server logs for details.",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ),
            500,
        )

    return jsonify(
        {
            "status": "success",
            "channel_releases": channels_releases,
            "count": len(channels_releases),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "cincinnati",
        }
    )


@app.route("/api/channels/refresh", methods=["POST"])
def refresh_ocp_channels(version=None):
    """Refresh the list of available OCP channels for each version"""
    app.logger.debug("Refreshing OCP channels...")
    channels = {}

    arch = request.args.get("arch", "amd64")
    # When called as a route, version comes from query params
    if version is None:
        version = request.args.get("version")
    static_file_path = _data_write_file(
        _arch_scoped_filename("ocp-channels.json", arch)
    )
    version_list = []
    # Use Version if provided, or get available versions if not provided
    if version:
        app.logger.debug(f"Fetching channels for specific version: {version}")
        version_list.append(version)
    else:
        app.logger.debug("Fetching channels for all available versions")
        try:
            # Try to load from static file first
            versions_file_path = _data_read_file(
                _arch_scoped_filename("ocp-versions.json", arch)
            )
            if versions_file_path.exists():
                with open(versions_file_path, "r") as f:
                    data = json.load(f)
                    releases = data.get("releases", [])
                    app.logger.debug(
                        f"Loaded {len(releases)} releases from static file"
                    )
                    for release in releases:
                        if re.match(r"^\d+\.\d+$", release):
                            version_list.append(release)
        except Exception as e:
            app.logger.error(f"Error loading static OCP versions file: {e}")

    if not version_list:
        app.logger.error("No valid OCP versions found to refresh channels")
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "No valid OCP versions found to refresh channels",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ),
            400,
        )

    try:
        for version in version_list:
            app.logger.debug(
                f"Querying Cincinnati API for channels for version {version}..."
            )
            found_channels = discover_channels_for_version(version, arch=arch)
            if found_channels:
                channels[version] = found_channels

        # Try to load from static file first
        old_channels = {}
        try:
            if static_file_path.exists():
                with open(static_file_path, "r") as f:
                    data = json.load(f)
                old_channels = data.get("channels", {})
        except Exception as e:
            app.logger.warning(f"Could not load static OCP versions file: {e}")

        # Merge old channels with new ones
        for version in version_list:
            old_channels.update({version: channels.get(version, [])})

        # Save to static file for future use (atomic write)
        app.logger.debug(f"Saving refreshed channels to {static_file_path}")
        atomic_json_dump(
            {
                "channels": old_channels,
                "count": len(old_channels),
                "source": "cincinnati",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            static_file_path,
        )

    except Exception as e:
        app.logger.error(f"Error refreshing channels: {e}")
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Failed to refresh channels. Check server logs for details.",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ),
            500,
        )

    return jsonify(
        {
            "status": "success",
            "channels": channels,
            "count": len(channels),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "cincinnati",
        }
    )


@app.route("/api/operators/catalogs/<version>/refresh", methods=["POST"])
def refresh_catalogs_for_version(version=None):
    """Refresh available operator catalogs from BASE_CATALOGS constants"""
    version_list = []
    discovered_catalogs = {}

    try:
        if version is not None:
            # Extract major.minor version from version string
            version_list.append(version)
        else:
            # If no version provided, refresh for all available versions
            static_file_path = _data_read_file("ocp-versions.json")
            if static_file_path.exists():
                with open(static_file_path, "r") as f:
                    data = json.load(f)
                    releases = data.get("releases", [])
                    app.logger.debug(
                        f"Loaded {len(releases)} releases from static file"
                    )
                    for release in releases:
                        if re.match(r"^\d+\.\d+$", release):
                            version_list.append(release)

        for version in version_list:
            # Extract major.minor version from version string
            if "." in version:
                version_parts = version.split(".")
                major = version_parts[0]
                minor = version_parts[1]
                version_key = f"{major}.{minor}"
            else:
                version_key = version

            app.logger.info(f"Discovering catalogs for OCP version {version_key}...")

            try:
                app.logger.info(
                    f"Generating catalogs for OCP version {version_key} from BASE_CATALOGS..."
                )

                # Generate catalog entries from BASE_CATALOGS with the version tag
                if version_key not in discovered_catalogs:
                    discovered_catalogs[version_key] = []
                for catalog in BASE_CATALOGS:
                    catalog_url = f"{catalog['base_url']}:v{version_key}"
                    # Validate catalog image exists with skopeo
                    validated = False
                    try:
                        result = subprocess.run(
                            build_skopeo_command(
                                "inspect",
                                f"docker://{catalog_url}",
                                extra_args=["--no-tags"],
                            ),
                            capture_output=True,
                            text=True,
                            timeout=TIMEOUT_SKOPEO,
                        )
                        validated = result.returncode == 0
                    except (subprocess.TimeoutExpired, Exception):
                        app.logger.warning(f"Could not validate catalog {catalog_url}")

                    if validated:
                        discovered_catalogs[version_key].append(
                            {
                                "name": catalog["name"],
                                "url": catalog_url,
                                "description": catalog["description"],
                                "default": catalog["default"],
                                "validated": validated,
                            }
                        )
                    else:
                        app.logger.info(
                            f"Excluding unvalidated catalog {catalog_url} from version {version_key}"
                        )
            except Exception as e:
                app.logger.error(
                    f"Error generating catalogs for version {version_key}: {e}"
                )
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": f"Failed to generate catalogs for version {version_key}. Check server logs for details.",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    ),
                    500,
                )

    except Exception as e:
        app.logger.error(f"Error discovering catalogs: {e}")
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Failed to discover catalogs. Check server logs for details.",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ),
            500,
        )

    # Write Catalog info to File (use version_key = major.minor for consistent filenames)
    try:
        atomic_json_dump(
            discovered_catalogs,
            _data_write_file(f"catalogs-{version_key}.json"),
        )
    except Exception as e:
        app.logger.warning(f"Could not save catalog file: {e}")

    return jsonify(
        {
            "status": "success",
            "version": version,
            "catalogs": discovered_catalogs,
            "source": "base_catalogs",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


@app.route("/api/versions/", methods=["GET"])
def get_versions():
    # Get available OCP releases using static files or Cincinnati API
    app.logger.debug("Fetching OCP releases...")
    releases = []
    arch = request.args.get("arch", "amd64")

    try:
        # Try to load from static file first
        static_file_path = _data_read_file(
            _arch_scoped_filename("ocp-versions.json", arch)
        )
        if static_file_path.exists():
            with open(static_file_path, "r") as f:
                data = json.load(f)
                releases = data.get("releases", [])
                app.logger.debug(f"Loaded {len(releases)} releases from static file")
    except Exception as e:
        app.logger.error(f"Error loading static OCP versions file: {e}")

    # If static file does not exist, refresh via Cincinnati API
    if releases != []:
        app.logger.debug("Static file found, using cached releases")
        return jsonify(
            {
                "status": "success",
                "releases": releases,
                "count": len(releases),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "static_file",
            }
        )

    release_update = refresh_versions()

    # refresh_versions() returns (response, status_code) on error or response on success
    if isinstance(release_update, tuple):
        return release_update

    response_data = release_update.get_json()
    if response_data.get("status") == "success":
        releases = response_data.get("releases", [])
        return jsonify(
            {
                "status": "success",
                "releases": releases,
                "count": len(releases),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "cincinnati",
            }
        )
    else:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Failed to fetch releases from Cincinnati API",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ),
            500,
        )


@app.route("/api/releases/<version>/<channel>", methods=["GET"])
def get_ocp_releases(version, channel):
    """Get available OCP releases for a specific version and channel"""

    if version is None:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Version parameter is required",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ),
            400,
        )

    if channel is None:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Channel parameter is required",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ),
            400,
        )

    # Validate version format using centralized validation
    try:
        version = validate_version(version)
    except ValidationError as e:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ),
            400,
        )

    # Validate channel format using centralized validation
    try:
        channel = validate_channel(channel)
    except ValidationError as e:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ),
            400,
        )

    # Try to load from static file first
    arch = request.args.get("arch", "amd64")
    app.logger.debug(
        f"Checking static file for releases for version {version} and channel {channel}"
    )
    static_file_path = _data_read_file(
        _arch_scoped_filename("channel-releases.json", arch)
    )

    try:
        with open(static_file_path, "r") as f:
            data = json.load(f)
        channel_releases = data.get("channel_releases", {}).get(channel, [])
        if channel_releases:
            return jsonify(
                {
                    "status": "success",
                    "version": version,
                    "channel": channel,
                    "releases": channel_releases,
                    "source": "static_file",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
    except Exception as e:
        app.logger.warning(f"Could not load static channel releases file: {e}")

    # If static file does not exist, refresh via Cincinnati API
    try:
        release_data = refresh_ocp_releases(version, channel)
        if release_data.json.get("status") == "success":
            return jsonify(
                {
                    "status": "success",
                    "version": version,
                    "channel": channel,
                    "releases": release_data.json.get("channel_releases", []),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
        else:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": f"No releases found for version {version} and channel {channel}",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                ),
                404,
            )
    except Exception as e:
        app.logger.error(
            f"Error getting OCP releases for version {version} and channel {channel}: {e}"
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": f"Failed to get OCP releases for version {version} and channel {channel}. Check server logs for details.",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ),
            500,
        )


def _sort_channels(channel_list, selected_version):
    """Sort channels: selected version first, then ascending by version.
    Within each version: stable > fast > eus > candidate."""
    type_order = {"stable": 0, "fast": 1, "eus": 2, "candidate": 3}

    def sort_key(ch):
        # Split "stable-4.20" into ("stable", "4.20")
        parts = ch.rsplit("-", 1)
        ch_type = parts[0] if len(parts) == 2 else ch
        ch_ver = parts[1] if len(parts) == 2 else ""
        # Selected version sorts first (0), others sort second (1)
        ver_group = 0 if ch_ver == selected_version else 1
        # Parse version for numeric sorting
        try:
            ver_tuple = tuple(int(x) for x in ch_ver.split("."))
        except (ValueError, AttributeError):
            ver_tuple = (999,)
        return (ver_group, ver_tuple, type_order.get(ch_type, 99))

    return sorted(channel_list, key=sort_key)


@app.route("/api/channels/<version>", methods=["GET"])
def get_ocp_channels(version):
    """Get available OCP channels for a specific version"""

    if version is None:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Version parameter is required",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ),
            400,
        )

    # Validate version format using centralized validation
    try:
        version = validate_version(version)
    except ValidationError as e:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ),
            400,
        )

    arch = request.args.get("arch", "amd64")
    static_file_path = _data_read_file(_arch_scoped_filename("ocp-channels.json", arch))

    # Try to load from static file first
    try:
        if static_file_path.exists():
            with open(static_file_path, "r") as f:
                data = json.load(f)
            channels = data.get("channels", [])
            channel_data = channels.get(version, [])
            if channel_data:
                return jsonify(
                    {
                        "status": "success",
                        "version": version,
                        "channels": _sort_channels(channel_data, version),
                        "source": "static_file",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
    except Exception as e:
        app.logger.warning(f"Could not load static OCP versions file: {e}")

    # If static file does not exist, refresh via Cincinnati API
    try:
        channel_data = refresh_ocp_channels(version)
        if channel_data.json.get("status") == "success":
            channels = channel_data.json.get("channels", {})
            if version in channels:
                return jsonify(
                    {
                        "status": "success",
                        "version": version,
                        "channels": _sort_channels(channels[version], version),
                        "source": "cincinnati",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
            else:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": f"No channels found for version {version}",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    ),
                    404,
                )
    except Exception as e:
        app.logger.error(
            f"Error querying Cincinnati API for channels for version {version}: {e}"
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": f"Failed to get OCP channels for version {version}. Check server logs for details.",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ),
            500,
        )


@app.route("/api/operators/mappings", methods=["GET"])
def get_operator_mappings():
    """Get available operator mappings"""
    return jsonify(
        {"mappings": OPERATOR_MAPPINGS, "suggestions": list(OPERATOR_MAPPINGS.keys())}
    )


@app.route("/api/operators/catalogs/<version>", methods=["GET"])
def get_operator_catalogs(version):
    """Get operator catalog data for a specific OCP version from static file or refresh"""

    # Extract major.minor version from version string
    if "." in version:
        version_parts = version.split(".")
        major = version_parts[0]
        minor = version_parts[1]
        version_key = f"{major}.{minor}"
    else:
        version_key = version

    static_file = _data_read_file(f"catalogs-{version_key}.json")

    # Try to load from static file first
    if static_file.exists():
        try:
            with open(static_file, "r") as f:
                catalogs = json.load(f)
            return jsonify(
                {
                    "status": "success",
                    "version": version,
                    "catalogs": catalogs,
                    "source": "static_file",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
        except Exception as e:
            app.logger.warning(f"Could not load static catalog file: {e}")

    # If static file does not exist, refresh from BASE_CATALOGS
    catalogs = refresh_catalogs_for_version(version)
    if catalogs.json.get("status") != "success":
        app.logger.error(
            f"Failed to get catalogs for version {version}: {catalogs.json.get('message')}"
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": f'Failed to get operator catalogs for version {version}: {catalogs.json.get("message")}',
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ),
            500,
        )

    # Extract the catalog list for this version from the version-keyed dict
    # Normalize to major.minor since refresh_catalogs_for_version() uses that as key
    version_key = ".".join(version.split(".")[:2])
    all_catalogs = catalogs.json.get("catalogs", {})
    available_catalogs = (
        all_catalogs.get(version_key, [])
        if isinstance(all_catalogs, dict)
        else all_catalogs
    )
    if not available_catalogs:
        app.logger.warning(f"No catalogs found for version {version}")
        return (
            jsonify(
                {
                    "status": "error",
                    "message": f"No operator catalogs found for version {version}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ),
            404,
        )

    return jsonify(
        {
            "status": "success",
            "version": version,
            "catalogs": available_catalogs,
            "source": "opm",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


@app.route("/api/operators/catalogs", methods=["GET"])
def get_available_catalogs():
    """Get all available operator catalogs, validating via skopeo inspect"""
    try:
        validated_catalogs = []

        for catalog in BASE_CATALOGS:
            try:
                cmd = build_skopeo_command(
                    "list-tags", f'docker://{catalog["base_url"]}'
                )
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=TIMEOUT_SKOPEO,
                )

                catalog_info = {
                    "name": catalog["name"],
                    "url": catalog["base_url"],
                    "description": catalog["description"],
                    "default": catalog["default"],
                }
                if result.returncode == 0:
                    catalog_info["validated"] = True
                    app.logger.info(f"Validated catalog: {catalog['base_url']}")
                else:
                    catalog_info["validated"] = False
                    app.logger.warning(
                        f"Could not validate catalog: {catalog['base_url']}"
                    )

                validated_catalogs.append(catalog_info)

            except subprocess.TimeoutExpired:
                catalog_info = {
                    "name": catalog["name"],
                    "url": catalog["base_url"],
                    "description": catalog["description"],
                    "default": catalog["default"],
                }
                catalog_info["validated"] = False
                catalog_info["error"] = "Timeout while validating"
                validated_catalogs.append(catalog_info)
                app.logger.warning(f"Timeout validating catalog: {catalog['base_url']}")

            except Exception as e:
                catalog_info = {
                    "name": catalog["name"],
                    "url": catalog["base_url"],
                    "description": catalog["description"],
                    "default": catalog["default"],
                }
                catalog_info["validated"] = False
                catalog_info["error"] = "Validation failed"
                validated_catalogs.append(catalog_info)
                app.logger.warning(
                    f"Error validating catalog {catalog['base_url']}: {e}"
                )

        return jsonify(
            {
                "status": "success",
                "catalogs": validated_catalogs,
                "count": len(validated_catalogs),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    except Exception as e:
        app.logger.error(f"Error getting available catalogs: {e}")
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Failed to get available catalogs. Check server logs for details.",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ),
            500,
        )


@app.route("/api/operators/catalogs/<version>/list", methods=["GET"])
def list_catalogs_for_version(version):
    """List available catalogs for a specific OCP version from cache or refresh"""

    # Normalize to major.minor for consistent cache filenames and dict keys
    version_key = ".".join(version.split(".")[:2])

    # Check if catalogs for this version are cached
    cached_catalogs = load_catalogs_from_file(version_key)

    if cached_catalogs is not None:
        # Cache files are version-keyed dicts, e.g. {"4.17": [...]}.
        catalog_list = (
            cached_catalogs.get(version_key, [])
            if isinstance(cached_catalogs, dict)
            else cached_catalogs
        )
        # Filter out entries explicitly marked as invalid (validated=False).
        # Seed data has no "validated" key, so default to True for offline-first use.
        valid_catalogs = [c for c in catalog_list if c.get("validated", True)]
        return jsonify(
            {
                "status": "success",
                "version": version,
                "catalogs": valid_catalogs,
                "source": "static_file",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    # If not cached, discover catalogs dynamically
    return refresh_catalogs_for_version(version)


@app.route("/api/operators/list", methods=["GET"])
def get_operators_list():
    """Get list of available operators from cache files"""
    try:
        # Get parameters from query string return none if not provided
        catalog = request.args.get("catalog")
        version = request.args.get("version")

        if not catalog:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Catalog and version parameters are required",
                    }
                ),
                400,
            )

        # Extract version from catalog if empty
        if version is None:
            version = catalog.split(":")[-1]

        # if no version present in catalog append version value to catalog
        if version is not None:
            if re.match(r"^\d+\.\d+$", version):
                # If version is in X.Y format, append it to catalog
                if ":v" not in catalog:
                    catalog = f"{catalog}:v{version}"

        # Extract major.minor version from version string
        if "." in version:
            version_parts = version.split(".")
            major = version_parts[0]
            minor = version_parts[1]
            version_key = f"{major}.{minor}"
        else:
            version_key = version

        # Read static file path for operators
        operators = load_operators_from_file(catalog, version_key)

        if operators is None or operators == []:
            app.logger.info(
                f"No cached operators found for {catalog}:{version_key}, running refresh..."
            )
            operators = _refresh_operators_data(catalog, version_key)

        # Return the operators list
        return jsonify(
            {
                "status": "success",
                "operators": operators,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception as e:
        app.logger.error(f"Error loading operators from cache: {e}")
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Failed to load operators. Check server logs for details.",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ),
            500,
        )


@app.route("/api/operators/<operator_name>/channels", methods=["GET"])
def get_operator_channels(operator_name):
    """Get available channels for a specific operator using cached data or opm render"""
    try:
        # Get parameters from query string
        catalog = request.args.get(
            "catalog", "registry.redhat.io/redhat/redhat-operator-index"
        )
        version = request.args.get("version", "4.18")

        # Extract major.minor version from version string
        if "." in version:
            version_parts = version.split(".")
            major = version_parts[0]
            minor = version_parts[1]
            version_key = f"{major}.{minor}"
        else:
            version_key = version

        # Create versioned catalog URL if not already versioned
        if ":v" not in catalog:
            catalog_url = f"{catalog}:v{version_key}"
        else:
            catalog_url = catalog

        # Try loading from cached operator data first
        operators = load_operators_from_file(catalog, version_key)
        if operators:
            channels = []
            for op in operators:
                if (
                    op.get("package") == operator_name
                    or op.get("name") == operator_name
                ):
                    ch = op.get("channel")
                    if ch and ch not in [c["name"] for c in channels]:
                        channels.append({"name": ch, "default": False})
            if channels:
                # Mark "stable" as default if present, otherwise first channel
                default_channel = "stable"
                has_stable = any(c["name"] == "stable" for c in channels)
                if not has_stable:
                    default_channel = channels[0]["name"]
                for c in channels:
                    c["default"] = c["name"] == default_channel

                app.logger.info(
                    f"Returning {len(channels)} cached channels for operator {operator_name}"
                )
                return jsonify(
                    {
                        "status": "success",
                        "operator": operator_name,
                        "catalog": catalog_url,
                        "channels": channels,
                        "default_channel": default_channel,
                        "source": "cache",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )

        # Fall back to opm render
        app.logger.info(
            f"Fetching channels for operator {operator_name} from {catalog_url} via opm render"
        )

        cmd = build_opm_command(catalog_url, output_format="json")
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=TIMEOUT_OPM_RENDER
        )

        channels = []
        default_channel = "stable"

        if result.returncode != 0:
            app.logger.warning(
                f"opm render failed for operator channels: {result.stderr}"
            )
            return jsonify(
                {
                    "status": "success",
                    "operator": operator_name,
                    "catalog": catalog_url,
                    "channels": [{"name": "stable", "default": True}],
                    "default_channel": "stable",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

        # Parse opm render JSON output line by line (NDJSON format)
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Look for olm.channel schema entries matching our operator
            if (
                entry.get("schema") == "olm.channel"
                and entry.get("package") == operator_name
            ):
                channel_name = entry.get("name", "")
                if channel_name:
                    channel_info = {
                        "name": channel_name,
                        "default": channel_name == "stable",
                    }
                    if channel_info not in channels:
                        channels.append(channel_info)

            # Check for default channel in olm.package schema
            if (
                entry.get("schema") == "olm.package"
                and entry.get("name") == operator_name
            ):
                default_channel = entry.get("defaultChannel", "stable")

        # If no channels found, provide defaults
        if not channels:
            channels = [
                {"name": "stable", "default": True},
                {"name": "fast", "default": False},
            ]

        # Update default flag based on discovered default channel
        for ch in channels:
            ch["default"] = ch["name"] == default_channel

        return jsonify(
            {
                "status": "success",
                "operator": operator_name,
                "catalog": catalog_url,
                "channels": channels,
                "default_channel": default_channel,
                "source": "opm_render",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    except subprocess.TimeoutExpired:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Request timeout while fetching operator channels",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ),
            504,
        )
    except Exception as e:
        app.logger.error(f"Error fetching operator channels: {e}")
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Failed to fetch operator channels. Check server logs for details.",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ),
            500,
        )


@app.route("/api/generate/preview", methods=["POST"])
def generate_preview():
    """Generate YAML preview without saving"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Create generator instance
        generator = ImageSetGenerator()
        newest_channel = {}

        # Add OCP versions
        if (
            data.get("ocp_versions")
            or data.get("ocp_min_version")
            or data.get("ocp_max_version")
        ):
            # New approach with min/max versions
            channel = data.get("ocp_channel", "stable-4.14")
            min_version = data.get("ocp_min_version")
            max_version = data.get("ocp_max_version")
            graph = data.get("graph", True)

            # Support legacy versions list for backward compatibility
            legacy_versions = None
            if data.get("ocp_versions"):
                legacy_versions = [v.strip() for v in data["ocp_versions"] if v.strip()]

            generator.add_ocp_versions(
                versions=legacy_versions,
                channel=channel,
                min_version=min_version,
                max_version=max_version,
                graph=graph,
            )

        # Add operators
        if data.get("operators"):
            # Group operators by catalog and version
            catalog_to_operators = {}
            channels = {}

            for op in data["operators"]:
                # Process operator data using helper function
                op_data = process_operator_data(op)
                if not op_data:
                    continue

                # Prepare operator entry
                op_entry = prepare_operator_entry(op_data)
                if not op_entry:
                    continue

                # Filter versions when catalog and version range are available
                name = op_data.get("name")
                min_version = op_data.get("minVersion")
                max_version = op_data.get("maxVersion")
                catalog_name = (
                    op_data.get("catalog") or data.get("operator_catalog") or ""
                )
                channel_list = set([])

                if catalog_name and min_version and max_version:
                    version_key = data.get("ocp_versions", [None])[0]
                    catalog_index = (catalog_name.split("/")[-1]).split(":")[0]
                    static_file_path = _data_read_file(
                        f"operators-{catalog_index}-{version_key}.json"
                    )
                    temp_channel_version_map = {}
                    possible_versions = []

                    try:
                        with open(static_file_path, "r") as f:
                            operator_catalog_data = json.load(f)
                            for operator in operator_catalog_data.get("operators", []):
                                if operator.get("name") == name:
                                    possible_versions.append(
                                        operator.get("version", [])
                                    )
                                    temp_channel_version_map[
                                        operator.get("version")
                                    ] = operator.get("channel")
                    except FileNotFoundError:
                        app.logger.warning(
                            f"Static operator data not found: {static_file_path}"
                        )

                    for version in possible_versions:
                        try:
                            if Version_Checker(version) >= Version_Checker(
                                min_version
                            ) and Version_Checker(version) <= Version_Checker(
                                max_version
                            ):
                                channel_list.add(temp_channel_version_map.get(version))
                                if version == max_version:
                                    newest_channel[name] = temp_channel_version_map.get(
                                        version
                                    )
                                continue
                        except Exception as e:
                            app.logger.warning(
                                f"Version comparison error for {name} version {version} will try other method: {e}"
                            )

                        try:
                            temp_version = version.split("-")[0]
                            temp_max_version = max_version.split("-")[0]
                            temp_min_version = min_version.split("-")[0]
                            if Version_Checker(temp_version) >= Version_Checker(
                                temp_min_version
                            ) and Version_Checker(temp_version) <= Version_Checker(
                                temp_max_version
                            ):
                                channel_list.add(temp_channel_version_map.get(version))
                                if temp_version == temp_max_version:
                                    newest_channel[name] = temp_channel_version_map.get(
                                        version
                                    )
                                continue
                        except Exception as e:
                            app.logger.warning(
                                f"Version comparison error for {name} version {version} will try other method: {e}"
                            )

                        try:
                            temp_version = version.split("+")[0]
                            temp_max_version = max_version.split("+")[0]
                            temp_min_version = min_version.split("+")[0]
                            if Version_Checker(temp_version) >= Version_Checker(
                                temp_min_version
                            ) and Version_Checker(temp_version) <= Version_Checker(
                                temp_max_version
                            ):
                                channel_list.add(temp_channel_version_map.get(version))
                                if temp_version == temp_max_version:
                                    newest_channel[name] = temp_channel_version_map.get(
                                        version
                                    )
                                continue
                        except Exception as e:
                            app.logger.warning(
                                f"Version comparison error for {name} version {version} will try other method: {e}"
                            )

                channels[op_data["name"]] = channel_list

                # Group by catalog
                catalog = (
                    op_data["catalog"]
                    or "registry.redhat.io/redhat/redhat-operator-index"
                )
                try:
                    validate_catalog_url(catalog)
                except ValidationError:
                    return jsonify({"error": f"Invalid catalog URL: {catalog}"}), 400
                catalog_to_operators.setdefault(catalog, []).append(op_entry)
            # Add operators for each catalog, passing full operator dicts
            ocp_version = (
                data.get("ocp_versions", [None])[0]
                or data.get("ocp_min_version")
                or data.get("ocp_max_version")
            )
            for catalog, ops in catalog_to_operators.items():
                generator.add_operators(
                    ops,
                    catalog,
                    channels,
                    ocp_version=ocp_version,
                    newest_channel=newest_channel,
                )

        # Add additional images
        if data.get("additional_images"):
            images = []
            for img in data["additional_images"]:
                if isinstance(img, str):
                    img_val = img.strip()
                elif isinstance(img, dict):
                    img_val = (
                        img.get("name", "").strip()
                        if "name" in img and isinstance(img["name"], str)
                        else ""
                    )
                else:
                    img_val = ""
                if img_val:
                    images.append(img_val)
            generator.add_additional_images(images)

        # Add helm charts
        if data.get("helm_charts"):
            generator.add_helm_charts(data["helm_charts"])

        # Set KubeVirt container mirroring
        if data.get("kubevirt_container", False):
            generator.set_kubevirt_container(True)

        # Set archive size if provided
        if data.get("archive_size"):
            try:
                generator.set_archive_size(int(data["archive_size"]))
            except Exception:
                pass
        # Generate YAML
        yaml_content = generator.generate_yaml()
        return jsonify(
            {
                "success": True,
                "yaml": yaml_content,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    except Exception as e:
        app.logger.error(f"Error generating preview: {str(e)}")
        app.logger.error(traceback.format_exc())
        return (
            jsonify(
                {"error": "Failed to generate preview. Check server logs for details.", "success": False}
            ),
            500,
        )


@app.route("/api/generate/download", methods=["POST"])
def generate_download():
    """Generate and return downloadable YAML file"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Create generator instance
        generator = ImageSetGenerator()

        # Add OCP versions
        if (
            data.get("ocp_versions")
            or data.get("ocp_min_version")
            or data.get("ocp_max_version")
        ):
            channel = data.get("ocp_channel", "stable-4.14")
            min_version = data.get("ocp_min_version")
            max_version = data.get("ocp_max_version")
            graph = data.get("graph", True)

            legacy_versions = None
            if data.get("ocp_versions"):
                legacy_versions = [v.strip() for v in data["ocp_versions"] if v.strip()]

            generator.add_ocp_versions(
                versions=legacy_versions,
                channel=channel,
                min_version=min_version,
                max_version=max_version,
                graph=graph,
            )

        # Add operators using shared helpers
        if data.get("operators"):
            catalog_to_operators = {}
            channels = {}

            for op in data["operators"]:
                op_data = process_operator_data(op)
                if not op_data:
                    continue

                op_entry = prepare_operator_entry(op_data)
                if not op_entry:
                    continue

                if op_data["channel"]:
                    channels[op_data["name"]] = op_data["channel"]

                catalog = (
                    op_data["catalog"]
                    or "registry.redhat.io/redhat/redhat-operator-index"
                )
                catalog_to_operators.setdefault(catalog, []).append(op_entry)

            ocp_version = (
                data.get("ocp_versions", [None])[0]
                or data.get("ocp_min_version")
                or data.get("ocp_max_version")
            )
            for catalog, ops in catalog_to_operators.items():
                try:
                    validate_catalog_url(catalog)
                except ValidationError:
                    return jsonify({"error": f"Invalid catalog URL: {catalog}"}), 400
                generator.add_operators(ops, catalog, channels, ocp_version=ocp_version)

        # Add additional images
        if data.get("additional_images"):
            images = []
            for img in data["additional_images"]:
                if isinstance(img, str):
                    img_val = img.strip()
                elif isinstance(img, dict):
                    img_val = (
                        img.get("name", "").strip()
                        if "name" in img and isinstance(img["name"], str)
                        else ""
                    )
                else:
                    img_val = ""
                if img_val:
                    images.append(img_val)
            generator.add_additional_images(images)

        # Add helm charts
        if data.get("helm_charts"):
            generator.add_helm_charts(data["helm_charts"])

        # Set KubeVirt container mirroring
        if data.get("kubevirt_container", False):
            generator.set_kubevirt_container(True)

        # Set archive size if provided
        if data.get("archive_size"):
            try:
                generator.set_archive_size(int(data["archive_size"]))
            except Exception:
                pass

        yaml_content = generator.generate_yaml()
        return app.response_class(
            yaml_content,
            mimetype="application/x-yaml",
            headers={
                "Content-Disposition": "attachment; filename=imageset-config.yaml"
            },
        )

    except Exception as e:
        app.logger.error(f"Error generating download: {str(e)}")
        app.logger.error(traceback.format_exc())
        return (
            jsonify(
                {"error": "Failed to generate download. Check server logs for details.", "success": False}
            ),
            500,
        )


@app.route("/api/validate", methods=["POST"])
def validate_config():
    """Validate configuration data"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No data provided"}), 400

        errors = []
        warnings = []

        # Check if at least one configuration is provided
        has_ocp = bool(data.get("ocp_versions"))
        has_operators = bool(data.get("operators"))
        has_images = bool(data.get("additional_images"))
        has_helm = bool(data.get("helm_charts"))

        if not (has_ocp or has_operators or has_images or has_helm):
            errors.append(
                "At least one configuration section must be specified"
                " (OCP versions, operators, additional images, or Helm charts)"
            )

        # Validate OCP versions format
        if has_ocp:
            for version in data.get("ocp_versions", []):
                if not version.strip():
                    continue
                version_parts = version.strip().split(".")
                if len(version_parts) < 3 or not all(
                    part.isdigit() for part in version_parts[:3]
                ):
                    warnings.append(
                        f'OCP version "{version}" may not be in the expected format (e.g., 4.14.1)'
                    )

        # Validate operator catalog URL
        if data.get("operator_catalog"):
            catalog = data.get("operator_catalog")
            if not catalog.startswith(("http://", "https://", "registry.")):
                warnings.append("Operator catalog should be a valid registry URL")

        # Validate additional images
        if has_images:
            for image in data.get("additional_images", []):
                if not image.strip():
                    continue
                if ":" not in image:
                    warnings.append(
                        f'Image "{image}" may be missing a tag (e.g., :latest)'
                    )

        # Validate Helm charts
        if has_helm:
            for chart in data.get("helm_charts", []):
                if not chart.get("name"):
                    errors.append("Helm chart name is required")
                if not chart.get("repository"):
                    errors.append("Helm chart repository is required")

        return jsonify(
            {
                "success": True,
                "valid": len(errors) == 0,
                "errors": errors,
                "warnings": warnings,
            }
        )

    except Exception as e:
        app.logger.error(f"Error validating config: {str(e)}")
        return (
            jsonify(
                {
                    "error": "Failed to validate configuration. Check server logs for details.",
                    "success": False,
                }
            ),
            500,
        )


@app.route("/api/refresh/all", methods=["GET"])
def refresh_all_static_data():
    """
    Refresh all static data files:
    - OCP releases
    - Operator catalogs for all known OCP versions
    """

    try:
        # Only call functions that work without per-resource parameters.
        # refresh_ocp_releases() requires version+channel and
        # refresh_ocp_operators() requires catalog, so they must be
        # called individually via their own endpoints.
        refresh_versions()
        refresh_ocp_channels()
    except Exception as e:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Error refreshing static data. Check server logs for details.",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ),
            500,
        )

    return jsonify(
        {
            "status": "success",
            "message": "All static data refreshed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors by serving React app"""
    if request.path.startswith("/api/") or request.path.startswith("/static/"):
        return _not_found_response()

    if _frontend_build_exists():
        return send_from_directory(app.static_folder, "index.html")

    return _not_found_response()


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({"error": "Internal server error", "success": False}), 500


@app.route("/api/ocp-versions", methods=["GET"])
def get_ocp_versions_static():
    """Get OCP versions from static file"""
    try:
        arch = request.args.get("arch", "amd64")
        static_file_path = _data_read_file(
            _arch_scoped_filename("ocp-versions.json", arch)
        )
        if static_file_path.exists():
            with open(static_file_path, "r") as f:
                data = json.load(f)
                return jsonify(
                    {
                        "status": "success",
                        "message": "OCP versions from static file",
                        "releases": data.get("releases", []),
                        "available_versions": data.get("releases", []),
                        "count": data.get("count", 0),
                        "source": data.get("source", "static_file"),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
        else:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Static OCP versions file not found",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                ),
                404,
            )
    except Exception as e:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Error reading OCP versions. Check server logs for details.",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ),
            500,
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="OpenShift ImageSetConfiguration Generator Web API"
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=5000, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    args = parser.parse_args()

    print("Starting OpenShift ImageSetConfiguration Generator Web API...")
    print(f"Access the application at: http://{args.host}:{args.port}")

    app.run(host=args.host, port=args.port, debug=args.debug)
