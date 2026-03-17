# OpenShift ImageSetConfiguration Generator

[![Python Tests](https://github.com/tomazb/imageset-generator/actions/workflows/test.yml/badge.svg)](https://github.com/tomazb/imageset-generator/actions/workflows/test.yml)
[![Security Scan](https://github.com/tomazb/imageset-generator/actions/workflows/security.yml/badge.svg)](https://github.com/tomazb/imageset-generator/actions/workflows/security.yml)
[![Container Build](https://github.com/tomazb/imageset-generator/actions/workflows/container.yml/badge.svg)](https://github.com/tomazb/imageset-generator/actions/workflows/container.yml)
[![Code Quality](https://github.com/tomazb/imageset-generator/actions/workflows/quality.yml/badge.svg)](https://github.com/tomazb/imageset-generator/actions/workflows/quality.yml)

An installable Python package for generating [oc-mirror](https://docs.openshift.com/container-platform/latest/installing/disconnected_install/installing-mirroring-disconnected.html) `ImageSetConfiguration` YAML files for OpenShift disconnected installations. It discovers available OCP versions and operators from live APIs, lets you select what to mirror, and produces a ready-to-use YAML configuration for air-gapped environments.

Three interfaces are provided: a **web UI** (React + Flask), a **CLI**, and a **Tkinter GUI** — all from a single `pip install`.

## Features

- **Multiple Interfaces** — Web UI (React/PatternFly + Flask API), command-line, and Tkinter desktop GUI. A smart launcher auto-detects the available display environment.
- **Live Version & Channel Discovery** — A Cincinnati API client (`discovery.py`) dynamically discovers OCP minor versions, channels (stable, fast, eus, candidate), and individual releases. Bundled seed data allows fully offline operation; live refresh endpoints keep the cache current.
- **Multi-Architecture** — Discovery and generation across amd64, arm64, ppc64le, and s390x.
- **Multi-Version** — Supports OCP versions from 4.12 onward (range is discovered dynamically, not hard-coded).
- **Multi-Catalog** — Red Hat Operators, Certified Operators, Community Operators, and Red Hat Marketplace catalogs.
- **Operator Search** — Filter operators by name or keyword. 18 built-in aliases map common names to package names (e.g. `logging` → `cluster-logging`, `istio` → `servicemeshoperator`).
- **Automation** — Scheduled Kubernetes Job execution, cron-based triggers, and multi-channel notifications (Email, Slack, Webhooks). See [automation/README.md](automation/README.md) for details.
- **Security** — Allowlist-based input validation, path traversal prevention, configurable TLS verification (secure by default).
- **Code Quality** — 14-type custom exception hierarchy, centralized constants, 105 tests across 15 test files.

## Quick Start

### 1. Run the container

```bash
./scripts/start-podman.sh
```

The script outputs the web address:

![Command Output](./docs/images/cmd-output.png)

### 2. Walk through the web UI

Select the OCP version, channel, and version range:

![Versions](./docs/images/ocp-version.png)

Choose which operator catalogs to search:

![Catalogs](./docs/images/ocp-catalogs.png)

Search for operators by name or keyword:

![Operator Search](./docs/images/operator-search.png)

Configure storage and advanced options:

![Storage Configuration](./docs/images/storage-config.png)

Generate a preview and copy the YAML to your clipboard:

![Output](./docs/images/preview-gen1.png)
![Output (continued)](./docs/images/preview-gen2.png)

## Installation

### Container (recommended)

```bash
# Podman Compose
podman-compose up imageset-generator

# Or use the helper script
./scripts/start-podman.sh
```

### Python package

Requires Python ≥ 3.10.

```bash
# Install from the repository root
pip install .

# Run the CLI (auto-detects GUI availability)
imageset-generator

# Force a specific interface
imageset-generator --cli
imageset-generator --gui
```

### Development

```bash
pip install -e .
./scripts/start-dev.sh       # Flask dev server + React hot-reload
```

## Architecture

The project is packaged as `imageset-generator` via `pyproject.toml` (setuptools). Everything lives under `src/imageset_generator/`.

### Package modules

| Module | Purpose |
|--------|---------|
| `app.py` | Flask REST API — serves the React frontend and all `/api/*` endpoints |
| `generator.py` | Core YAML generation logic for ImageSetConfiguration files |
| `discovery.py` | Cincinnati API client — discovers OCP versions, channels, and releases with a 1-hour TTL cache |
| `validation.py` | Input validation — allowlist patterns for URLs, versions, channels, and file paths |
| `constants.py` | Centralized configuration — timeouts, paths, patterns, catalogs, operator aliases |
| `exceptions.py` | 14-type custom exception hierarchy with structured `details` dicts |
| `cli/launcher.py` | Unified entry point — auto-detects Tkinter availability, falls back to CLI |
| `cli/gui.py` | Tkinter desktop GUI |
| `automation/` | Kubernetes job scheduling, cron engine, email/Slack/webhook notifications |
| `frontend/build/` | Compiled React UI (PatternFly) |
| `data/*.json` | Bundled seed data (33 JSON files) for offline operation |

### Data path resolution

The application uses a two-tier data strategy:

| Tier | Path | Purpose |
|------|------|---------|
| **Packaged (read-only)** | `src/imageset_generator/data/` | Seed data shipped with the package — always available |
| **Runtime (writable)** | `./data/` | Cache refreshed from live APIs via `/api/*/refresh` endpoints (gitignored, empty on checkout) |

When reading, the runtime cache is preferred; if absent the packaged seed data is used as a fallback. Helper functions `get_data_read_path()` and `get_data_write_path()` in `constants.py` handle the resolution.

To clear the writable cache: `rm -rf ./data/*`

### Frontend components

| Component | Role |
|-----------|------|
| `BasicConfig.js` | OCP version, channel, and version range selection |
| `AdvancedConfig.js` | Storage backend, graph, and additional images |
| `OperatorSearch.js` | Operator search / filter with keyword matching |
| `PreviewGenerate.js` | YAML preview, clipboard copy, and download |
| `LoadSaveConfig.js` | Save / load configuration presets |
| `StatusBar.js` | Connection and refresh status indicators |
| `LoadingSpinner.js` | Loading indicator during API calls |

## REST API

Key endpoints exposed by `app.py`:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check (status, timestamp, version) |
| GET | `/api/versions/` | Available OCP minor versions |
| GET | `/api/channels/<version>` | Available channels for a version |
| GET | `/api/releases/<version>/<channel>` | Releases within a channel |
| GET | `/api/operators/catalogs/<version>` | Operator catalog data for a version |
| GET | `/api/operators/list` | Operators from cached catalog data |
| GET | `/api/operators/<name>/channels` | Channels for a specific operator |
| GET | `/api/operators/mappings` | Operator alias mappings |
| POST | `/api/generate/preview` | Generate YAML preview |
| POST | `/api/generate/download` | Generate and download YAML file |
| POST | `/api/validate` | Validate a configuration |
| POST | `/api/versions/refresh` | Refresh versions from Cincinnati API |
| POST | `/api/channels/refresh` | Refresh channels from Cincinnati API |
| POST | `/api/releases/refresh` | Refresh releases from Cincinnati API |
| POST | `/api/operators/refresh` | Refresh operators from a catalog |
| POST | `/api/operators/catalogs/<version>/refresh` | Refresh catalog data for a version |
| GET | `/api/operators/catalogs` | List available operator catalogs |
| GET | `/api/operators/catalogs/<version>/list` | List operators from a catalog version |
| GET | `/api/ocp-versions` | OCP version list (alternative endpoint) |
| GET | `/api/refresh/all` | Refresh all cached data |

## Security

### Input Validation (`validation.py`)

All user inputs are validated using allowlist patterns:

```python
from imageset_generator.validation import (
    validate_catalog_url,   # Allows registry.redhat.io/* only
    validate_version,       # Enforces X.Y format
    validate_channel,       # Enforces <name>-X.Y pattern
    safe_path_component,    # Blocks traversal (../ , absolute paths)
    ValidationError,
)
```

### TLS Configuration

TLS verification is enabled by default (`TLS_VERIFY = True` in `constants.py`). All outbound calls to registries and APIs respect this setting. To override:

```python
from imageset_generator.constants import TLS_VERIFY
from imageset_generator.app import build_opm_command

cmd = build_opm_command(catalog_url)               # TLS verified
cmd = build_opm_command(catalog_url, skip_tls=True) # Override (not recommended)
```

### Path Traversal Prevention

`safe_path_component()` sanitizes all dynamic file path segments — blocking `../`, absolute paths, and null bytes.

## Configuration

### `constants.py`

| Category | Key constants |
|----------|--------------|
| **Timeouts** | `TIMEOUT_OC_MIRROR_SHORT` (30 s), `TIMEOUT_OPM_RENDER` (180 s), `TIMEOUT_CINCINNATI` (15 s), `TIMEOUT_CATALOG_DISCOVERY` (300 s), `TIMEOUT_SKOPEO` (30 s) |
| **Cincinnati API** | `CINCINNATI_API_URL`, `OCP_MINOR_PROBE_RANGE` (4.12–4.30), `CINCINNATI_CHANNEL_PREFIXES` |
| **Security** | `TLS_VERIFY = True`, `VERSION_PATTERN`, `CHANNEL_PATTERN` |
| **Catalogs** | `BASE_CATALOGS` — Red Hat, Certified, Community, Marketplace |
| **Operator aliases** | `OPERATOR_MAPPINGS` — 18 entries (e.g. `logging` → `cluster-logging`, `tekton` → `openshift-pipelines-operator-rh`) |
| **Paths** | `PROJECT_ROOT`, `RUNTIME_ROOT`, `PACKAGED_DATA_DIR`, `FRONTEND_BUILD_DIR` |

## Error Handling

### Custom Exceptions (`exceptions.py`)

Every exception carries a `details` dict and optional `original_error` for chaining:

```python
from imageset_generator.exceptions import CatalogRenderError

try:
    render_catalog(catalog_url)
except CatalogRenderError as e:
    print(e)                  # Human-readable message
    print(e.details)          # {"catalog": "...", "version": "..."}
    print(e.original_error)   # Original exception, if any
```

| Category | Exceptions |
|----------|-----------|
| Base | `ImageSetGeneratorError` |
| Catalog | `CatalogError`, `CatalogRenderError`, `CatalogParseError` |
| Operator | `OperatorError`, `OperatorNotFoundError`, `InvalidChannelError` |
| Version | `VersionError`, `InvalidVersionError`, `VersionComparisonError` |
| System | `ConfigurationError`, `FileOperationError`, `NetworkError`, `GenerationError` |

## Testing

```bash
# Run all 105 tests
PYTHONPATH=src pytest tests -q

# Run a specific module
PYTHONPATH=src pytest tests/unit/test_validation_simple.py -q

# With coverage
PYTHONPATH=src pytest tests --cov=src/imageset_generator
```

Tests are organized across 15 files in `tests/unit/` and `tests/smoke/`, covering:

- Input validation and sanitization
- Custom exception behavior
- TLS configuration propagation
- Cincinnati API discovery logic
- Flask API endpoints
- CLI launcher and packaging
- YAML generation and refactoring

## Development

### Code quality standards

- **Single Responsibility** — each function does one thing
- **Allowlist Validation** — all user inputs validated via `validation.py`
- **Structured Errors** — domain-specific exceptions with diagnostic context
- **Centralized Config** — no magic numbers; everything in `constants.py`
- **Secure by Default** — TLS on, validation required, paths sanitized

### Dependency management

Dependencies are declared in `pyproject.toml`:

```
PyYAML ≥6.0, Flask ≥2.3, Flask-CORS ≥4.0, packaging ≥25.0,
requests ≥2.32.5, apscheduler ≥3.10, kubernetes ≥28.1
```

Python ≥ 3.10 is required. The package builds with setuptools ≥ 68.

See [CHANGELOG.md](CHANGELOG.md) for detailed version history.

## Contributing

1. All new code must include tests
2. Validate user inputs with functions from `validation.py`
3. Use constants from `constants.py` — no magic numbers
4. Use custom exceptions from `exceptions.py` with context
5. Follow Single Responsibility Principle
6. Update CHANGELOG.md

## License

See LICENSE file for details.

## CI/CD Pipeline

Automated via GitHub Actions (`.github/workflows/`):

| Workflow | What it does |
|----------|-------------|
| `test.yml` | Runs 105 tests across Python 3.10–3.13 |
| `security.yml` | Bandit, Safety, CodeQL, Trivy (weekly + on PR) |
| `container.yml` | Docker/Podman builds with vulnerability scanning |
| `quality.yml` | Linting, complexity checks, type checking |
| `dependencies.yml` | Automated Dependabot updates |

Container images published to: `ghcr.io/tomazb/imageset-generator`

## Additional Documentation

- [CHANGELOG.md](CHANGELOG.md) — Version history
- [automation/README.md](automation/README.md) — Automation module guide
- [automation/QUICKSTART.md](automation/QUICKSTART.md) — Automation quick-start
- [AGENTS.md](AGENTS.md) — AI agent guidelines for this codebase
- [docs/guides/CI_DOCUMENTATION.md](docs/guides/CI_DOCUMENTATION.md) — CI/CD pipeline documentation
- [docs/guides/WEB_INTERFACE.md](docs/guides/WEB_INTERFACE.md) — Web interface guide
- [docs/guides/PODMAN_GUIDE.md](docs/guides/PODMAN_GUIDE.md) — Container deployment guide
