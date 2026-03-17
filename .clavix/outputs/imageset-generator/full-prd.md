# Product Requirements Document: OpenShift ImageSet Generator

## Problem & Goal

Platform engineers managing disconnected (air-gapped) OpenShift clusters face two compounding problems:

1. **Configuration complexity**: Writing ImageSetConfiguration YAML files for `oc-mirror` is error-prone, tedious, and requires deep knowledge of catalog structures, operator channels, and version compatibility across 4 Red Hat catalogs.

2. **Ongoing maintenance burden**: Once initial mirroring is done, keeping operators, Helm charts, and OCP releases up-to-date across multiple disconnected registries requires repetitive manual work that is easy to forget or get wrong.

**Goal**: Provide a single tool that lets platform engineers generate correct ImageSetConfiguration files through an intuitive UI or CLI, manage the lifecycle of already-mirrored artifacts, and automate recurring mirror operations across multiple clusters/registries - reducing a multi-hour manual process to a codified, hands-off workflow that can be set up in under 30 minutes.

---

## Users & Personas

### Primary: Platform Engineer
- Manages 1+ disconnected OpenShift clusters
- Responsible for keeping cluster operators and platform images current
- Comfortable with CLI tools, Kubernetes, and YAML but wants to avoid unnecessary toil
- Needs auditability and predictability in what gets mirrored

### Secondary: Cluster Administrator
- Consumes the mirrored content but may not configure the mirroring
- Needs visibility into what's available in the disconnected registry
- Wants confidence that security patches and updates are flowing

---

## Product Versioning & Roadmap

### v1.0 - Core Generator (Current State - Implemented)
The foundation: generate correct ImageSetConfiguration YAML files.

### v1.x - Lifecycle Management & Automation MVP
Add artifact tracking, automated version discovery, and single-cluster automation.

### v2.0 - Multi-Cluster & Autonomous Operations
Full multi-registry support, policy-driven mirroring, and autonomous release tracking.

---

## Requirements

### v1.0 - Core Generator (Implemented)

#### 1.1 ImageSetConfiguration YAML Generation
- **Status**: Implemented
- Generate valid `ImageSetConfiguration` YAML for `oc-mirror` v2 (`mirror.openshift.io/v2alpha1`)
- `oc-mirror --v2` is used exclusively for mirroring execution; version/channel discovery uses the Cincinnati API
- Support OCP versions 4.16 and beyond (new versions discovered dynamically via Cincinnati API; seed data currently covers 4.16-4.21)
- Support all 4 Red Hat operator catalogs: Red Hat, Community, Certified, Marketplace
- Include metadata comments in generated YAML for traceability
- Support additional container images beyond operators
- Support Helm chart mirroring
- Support KubeVirt container disk mirroring
- Optional archive size specification for split mirrors

#### 1.2 Operator Discovery & Search
- **Status**: Implemented
- Search and filter operators across all 4 catalogs
- Smart operator name mapping (18+ aliases, e.g., "logging" -> "cluster-logging")
- Version-specific operator listings with channel information
- Cached catalog data with manual refresh capability (via `opm render`); catalog discovery also uses `opm render` (replacing `oc-mirror list operators`)

#### 1.3 Web User Interface
- **Status**: Implemented
- React + PatternFly UI (consistent with OpenShift console look & feel)
- Tabbed interface: Basic Config, Advanced Config, Preview & Generate, Load/Save
- Real-time YAML preview with syntax highlighting as user configures
- Operator search with multi-select
- Copy-to-clipboard and file download for generated YAML
- Load/save configuration files (drag-and-drop upload)
- Toast notifications and loading states for async operations

#### 1.4 CLI Interface
- **Status**: Implemented
- Full CLI mode for scripting and automation
- Arguments: `--ocp-versions`, `--ocp-channel`, `--operators`, `--operator-catalog`, `--additional-images`, `--output`
- Unified launcher with auto-detection of GUI/CLI/web mode
- Tkinter GUI fallback when web UI is unavailable

#### 1.5 REST API
- **Status**: Implemented
- Version management: list versions, refresh cache
- Release management: get releases per version/channel
- Operator management: refresh catalogs, list operators
- Channel management: list and refresh channels
- Config generation: preview and download endpoints
- Health check endpoint

#### 1.6 Input Validation & Security
- **Status**: Implemented
- Catalog URL allowlist (registry.redhat.io only)
- Version format validation (X.Y semantic versioning)
- Channel name format validation
- Path traversal prevention
- TLS verification enabled by default (configurable)
- Custom exception hierarchy with context preservation (11 exception classes)

#### 1.7 Data Management
- **Status**: Implemented
- Bundled seed data (50+ JSON files covering OCP 4.16-4.21) for offline-first operation
- Runtime cache in `./data/` directory supports any OCP version, with fallback to bundled seed data
- Manual cache refresh via API endpoints
- Dynamic data sources: Cincinnati API for OCP version/channel/release discovery, `opm render` for operator catalog data

#### 1.8 Deployment
- **Status**: Implemented
- Python package installable via pip (`imageset-generator`)
- Containerfile for Podman/Docker builds
- podman-compose for local development
- Published to ghcr.io/tomazb/imageset-generator
- Startup scripts: `start-podman.sh`, `start-dev.sh`, `start-web.sh`

#### 1.9 Quality & CI/CD
- **Status**: Implemented
- 83 passing tests (unit + smoke)
- CI workflows: tests (Python 3.10-3.13), security scanning (Bandit, Safety, CodeQL, Trivy), container builds, quality checks (linting, complexity, types), dependency updates

---

### v1.x - Lifecycle Management & Automation MVP (Backlog)

#### 2.1 Artifact Inventory & Tracking
- **Status**: Not started
- Track what has been mirrored: operators, versions, Helm charts, additional images
- Record mirror history: when each artifact was last mirrored, from which catalog version
- Detect drift: what's in the ImageSetConfiguration vs what's actually in the registry
- Show "what's new since last mirror" diff for operators and OCP releases
- Persistent storage for inventory (database or structured files)

#### 2.2 Operator Lifecycle Management
- **Status**: Not started
- Detect available operator updates across subscribed channels
- Show upgrade paths: current mirrored version vs latest available
- Generate incremental ImageSetConfigurations (only what changed)
- Alert when operators are deprecated or removed from catalogs
- Track operator dependencies and related images

#### 2.3 Helm Chart Lifecycle Management
- **Status**: Not started
- Track mirrored Helm charts and their versions
- Detect new chart versions available upstream
- Support chart dependency resolution
- Generate update configurations for changed charts only

#### 2.4 Smart Version Discovery
- **Status**: Scaffolding exists in automation/engine.py
- Automatic discovery of new OCP patch releases via Cincinnati API
- Selection strategies: latest, latest-patch, latest-stable (with age threshold)
- "Download the highest patch version of channel stable at the end of the month" - fully codified
- Version pinning and exclusion rules (skip known-bad releases)
- Channel-aware discovery (stable, fast, candidate, eus)

#### 2.5 Automated Mirror Execution
- **Status**: Scaffolding exists in automation/ module
- Scheduled execution: monthly windows (configurable day ranges)
- Kubernetes Job creation for `oc-mirror --v2` execution
  - Resource limits/requests
  - PVC mounting for mirror storage
  - Registry credential injection
  - Job monitoring and log collection
  - Automatic cleanup of completed jobs
- Dry-run mode for safe testing
- Concurrent job prevention (safety lock)
- State persistence across restarts

#### 2.6 Notifications
- **Status**: Scaffolding exists in automation/notifier.py
- Email (SMTP) notifications on mirror completion/failure
- Slack webhook notifications
- Generic webhook support for custom integrations
- Configurable notification triggers: success, failure, new versions detected, drift detected

#### 2.7 Automation API
- **Status**: Scaffolding exists in automation/api.py
- Manual trigger endpoint (run mirror now)
- Status monitoring (current job state, last run, next scheduled)
- Job management (cancel, retry, view logs)
- Configuration management (update schedules, version strategies)

#### 2.8 Automation Configuration
- **Status**: Config template exists in automation/config.yaml
- YAML-based configuration for all automation settings
- Safety defaults: disabled by default, opt-in model
- Configurable schedules, version strategies, K8s resources, notification channels
- Environment variable overrides for sensitive values (credentials, tokens)

---

### v2.0 - Multi-Cluster & Autonomous Operations (Future)

#### 3.1 Multi-Registry / Multi-Cluster Support
- **Status**: Not started
- Manage multiple target disconnected registries from one instance
- Per-registry configuration: which operators, versions, and charts to mirror
- Shared operator catalog cache across registries (avoid redundant `opm render` calls)
- Registry health checks and connectivity validation
- Dashboard view: all registries, their sync status, last mirror time

#### 3.2 Policy-Driven Mirroring
- **Status**: Not started
- Define mirroring policies per registry/cluster: "always mirror latest stable", "only mirror EUS releases", "include community operators only for dev clusters"
- Policy inheritance: base policy + per-cluster overrides
- Policy validation: warn when policies conflict or create gaps
- Approval workflows: optionally require human approval before mirroring new major versions

#### 3.3 Autonomous Release Tracking
- **Status**: Not started
- Continuously monitor Red Hat release feeds for new OCP versions
- Automatically generate and execute mirror jobs when new releases match policies
- "Set and forget" mode: codified rules replace manual version selection entirely
- Configurable lag: "mirror stable releases that are at least 7 days old"
- Emergency override: manually trigger immediate mirror for critical security patches

#### 3.4 Audit Trail & Compliance
- **Status**: Not started
- Complete audit log of all mirror operations: who triggered, what was mirrored, when, to which registry
- Compliance reporting: prove what versions are available in each disconnected environment
- Change detection: alert when mirrored content changes unexpectedly
- Export audit data for external compliance tools

#### 3.5 Registry Content Inspection
- **Status**: Not started
- Query what's actually in a disconnected registry (not just what was configured)
- Compare registry contents against ImageSetConfiguration (detect manual changes)
- Storage usage reporting per registry
- Stale artifact identification and cleanup recommendations

#### 3.6 Advanced Scheduling
- **Status**: Not started
- Per-registry schedules (different clusters may have different maintenance windows)
- Dependency-aware scheduling: mirror base images before operators that depend on them
- Bandwidth-aware scheduling: stagger large mirrors to avoid network saturation
- Calendar integration: respect cluster maintenance windows and change freezes

---

## Technical Requirements

### Existing Stack (Preserve)
- **Backend**: Python 3.10+, Flask, PyYAML, requests, packaging, Cincinnati API (`api.openshift.com`)
- **Frontend**: React 18, PatternFly 5, axios, react-syntax-highlighter
- **Automation**: APScheduler, kubernetes client library
- **Package**: pip-installable Python package with bundled frontend build
- **Container**: Podman/Docker via Containerfile

### New Technical Needs (v1.x)
- **Persistent storage**: Database or structured file store for artifact inventory and mirror history
- **Background task management**: Robust job queue for long-running mirror operations
- **Incremental diff engine**: Compare current vs desired state to generate minimal ImageSetConfigurations

### New Technical Needs (v2.0)
- **Multi-tenancy in configuration**: Per-registry/cluster config management
- **Event system**: Pub/sub for release detection, job completion, drift alerts
- **External feed integration**: Red Hat release RSS/API monitoring

### Architecture Constraints
- Must remain deployable as a single container (with optional external database for v1.x+)
- Offline-first: core generation must work without network access (seed data)
- Automation features are always opt-in, disabled by default
- No breaking changes to existing CLI arguments or API endpoints between versions

---

## Out of Scope

### Permanently Out of Scope
- **oc-mirror binary management**: This tool generates configurations, it does not ship or manage the `oc-mirror` binary itself
- **Registry operation**: Not a registry (that's Quay, Harbor, etc.) - this tool configures what goes INTO a registry
- **Cluster management**: Not an OpenShift management tool - focused solely on image mirroring configuration
- **Non-Red Hat ecosystems**: Designed for OpenShift/OKD only, not generic container mirroring

### Out of Scope for v1.x (Consider for v2.0+)
- Multi-registry management (single target registry in v1.x)
- Policy engine and approval workflows
- Autonomous release tracking (manual trigger + scheduled in v1.x)
- Audit trail and compliance reporting
- Registry content inspection

---

## Success Criteria

### v1.0 (Current - Validate)
- Platform engineer can generate a correct ImageSetConfiguration in under 5 minutes via web UI
- CLI mode supports full scriptability for CI/CD pipelines
- Generated YAML passes `oc-mirror` validation without errors
- Works offline with bundled seed data

### v1.x (Target)
- Platform engineer can set up automated monthly mirroring with notifications in under 30 minutes
- Artifact inventory accurately reflects what has been mirrored
- Smart version discovery correctly identifies new patch releases
- Incremental configurations reduce mirror time by 50%+ vs full re-mirror
- Zero manual intervention required for routine monthly mirrors once configured

### v2.0 (Target)
- Single instance manages mirrors for 5+ disconnected registries
- Policy-driven mirroring eliminates per-mirror version selection
- Audit trail satisfies compliance requirements for regulated environments
- New OCP releases are automatically mirrored within configured policy parameters

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Cincinnati API availability or format changes | Version/channel discovery fails | Graceful fallback to cached seed data, configurable timeout, offline-first design |
| `oc-mirror` v2 config format changes | Generated YAML becomes invalid | Version-aware generation (`v2alpha1`), CI tests against oc-mirror v2 |
| Red Hat catalog structure changes | Operator discovery breaks | Graceful fallback to cached data, monitoring for catalog schema changes |
| Automation runs unattended with wrong config | Mirrors wrong content to production registry | Dry-run mode default, concurrent job prevention, version change detection, notifications |
| Large mirrors overwhelm storage/network | Failed jobs, partial mirrors | Archive size limits, bandwidth-aware scheduling (v2.0), progress monitoring |
| Multi-registry complexity | Configuration errors across environments | Policy validation, per-registry health checks, audit trail |

---

## Appendix: Current Implementation Inventory

### Source Structure
```
src/imageset_generator/
  app.py              # Flask REST API (~1,900 LOC)
  generator.py        # YAML generation core (~370 LOC)
  constants.py        # Centralized config (~180 LOC)
  validation.py       # Input validation (~170 LOC)
  exceptions.py       # Custom exceptions (~220 LOC)
  cli/                # CLI launcher + tkinter GUI
  automation/         # Scheduler, K8s manager, notifier, API blueprint
  data/               # 50+ JSON seed files (seed data covers OCP 4.16-4.21; runtime supports any version)
frontend/src/         # React application (8 components)
tests/                # 46 tests (unit + smoke)
```

### Automation Module Status
The `automation/` module contains scaffolding for the full automation pipeline but is **disabled by default** and needs significant hardening:
- `engine.py` - Orchestration logic (exists, needs testing and hardening)
- `scheduler.py` - APScheduler integration (exists, needs production hardening)
- `k8s_manager.py` - K8s Job management (exists, needs real-cluster testing)
- `notifier.py` - Email/Slack/webhook (exists, needs integration testing)
- `api.py` - REST endpoints for automation (exists, needs auth and validation)
- `config.yaml` - Configuration template (exists, comprehensive)

---

*Generated with Clavix Planning Mode*
*Generated: 2026-03-16T00:00:00Z*
