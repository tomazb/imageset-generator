// Pure utility functions for OCP version filtering and comparison.
// Kept in a separate module so they can be tested without pulling in
// React, axios, or PatternFly dependencies.

// Filter releases to only include those matching the selected minor version.
// Cincinnati channels (e.g., stable-4.20) contain releases from multiple minor
// versions (upgrade sources), but users expect to see only the selected minor.
export function filterReleasesByMinorVersion(releases, minorVersion) {
  if (!minorVersion || !Array.isArray(releases)) return releases || [];
  const prefix = minorVersion + '.';
  return releases.filter(r => r.startsWith(prefix));
}

// Compare two version strings numerically (e.g., "4.20.9" vs "4.20.15").
// Returns -1 if a < b, 0 if equal, 1 if a > b.
export function compareVersions(a, b) {
  const pa = a.split('.').map(Number);
  const pb = b.split('.').map(Number);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const na = pa[i] || 0;
    const nb = pb[i] || 0;
    if (na < nb) return -1;
    if (na > nb) return 1;
  }
  return 0;
}
