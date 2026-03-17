# Original Prompt (Extracted from Conversation)

Create a bash script for refreshing the packaged seed data files used by the imageset-generator application. The script should refresh three Cincinnati-sourced JSON files: ocp-versions.json, ocp-channels.json, and channel-releases.json, which live in src/imageset_generator/data/.

The script should leverage the app's existing refresh API endpoints rather than calling Cincinnati directly. The workflow is: start the Flask app locally, hit the refresh endpoints to populate the runtime cache in data/, then copy those refreshed files over to the packaged seed data directory at src/imageset_generator/data/.

Validation is essential — the script must verify that the refreshed data isn't a regression compared to the current seed data. For example, if the current seed has 23 OCP versions and the refresh only returns 1, the script should reject the update. Only amd64 architecture needs to be supported.

This script is intended as a release management step — maintainers run it before cutting a release to ensure the packaged seed data ships with current version and channel information.

---
*Extracted by Clavix on 2026-03-17. See optimized-prompt.md for enhanced version.*
