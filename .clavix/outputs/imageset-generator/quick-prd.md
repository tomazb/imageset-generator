# OpenShift ImageSet Generator - Quick PRD

OpenShift ImageSet Generator is a full-stack tool (Python/Flask + React/PatternFly) that helps platform engineers managing disconnected OpenShift clusters generate correct ImageSetConfiguration YAML files for `oc-mirror --v2` (`mirror.openshift.io/v2alpha1`). The core generator (v1.0) is implemented: web UI with operator search across 4 Red Hat catalogs, real-time YAML preview, CLI mode for scripting, REST API, input validation, bundled seed data for offline use, and containerized deployment. It supports OCP 4.16+ (seed data covers 4.16-4.21, new versions discovered dynamically via Cincinnati API) with smart operator name mapping, Helm charts, additional images, and KubeVirt container disks. Version/channel discovery uses the Cincinnati API (`api.openshift.com`); operator catalog discovery uses `opm render`; `oc-mirror --v2` is used only for actual mirroring execution.

The next milestone (v1.x) adds lifecycle management and automation: tracking what's been mirrored (operators, charts, images), detecting available updates, generating incremental configurations, and automating recurring mirror operations via Kubernetes Jobs with scheduling, version discovery strategies ("mirror highest stable patch monthly"), and multi-channel notifications (Email, Slack, webhooks). Scaffolding for automation exists in the codebase (engine, scheduler, K8s manager, notifier, API blueprint) but is disabled by default and needs significant hardening, testing, and production readiness work.

The long-term vision (v2.0) extends to multi-registry/multi-cluster management from a single instance, policy-driven mirroring rules ("only EUS for production, latest stable for dev"), autonomous release tracking that eliminates manual version selection entirely, audit trails for compliance, and registry content inspection. Architecture must remain single-container deployable, offline-first for core generation, and fully opt-in for automation features. Success: a platform engineer sets up automated monthly mirroring with notifications in under 30 minutes, with zero manual intervention for routine operations once configured.

---

*Generated with Clavix Planning Mode*
*Generated: 2026-03-16T00:00:00Z*
