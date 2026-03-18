import { filterReleasesByMinorVersion, compareVersions } from './versionUtils';

describe('filterReleasesByMinorVersion', () => {
  it('filters releases to match the selected minor version', () => {
    const releases = ['4.18.0', '4.18.1', '4.19.0', '4.19.5', '4.20.0', '4.20.15'];
    expect(filterReleasesByMinorVersion(releases, '4.20')).toEqual(['4.20.0', '4.20.15']);
  });

  it('returns empty array when no releases match', () => {
    const releases = ['4.18.0', '4.19.0'];
    expect(filterReleasesByMinorVersion(releases, '4.20')).toEqual([]);
  });

  it('returns empty array for empty input', () => {
    expect(filterReleasesByMinorVersion([], '4.20')).toEqual([]);
  });

  it('returns all releases when minorVersion is empty', () => {
    const releases = ['4.18.0', '4.20.0'];
    expect(filterReleasesByMinorVersion(releases, '')).toEqual(['4.18.0', '4.20.0']);
  });

  it('does not match partial prefixes (4.2 should not match 4.20.x)', () => {
    const releases = ['4.2.0', '4.20.0', '4.20.1'];
    expect(filterReleasesByMinorVersion(releases, '4.2')).toEqual(['4.2.0']);
  });

  it('preserves sort order from input', () => {
    const releases = ['4.20.0', '4.20.1', '4.20.10', '4.20.2'];
    expect(filterReleasesByMinorVersion(releases, '4.20')).toEqual(['4.20.0', '4.20.1', '4.20.10', '4.20.2']);
  });
});

describe('compareVersions', () => {
  it('returns -1 when a < b (different patch)', () => {
    expect(compareVersions('4.20.9', '4.20.15')).toBe(-1);
  });

  it('returns 0 when versions are equal', () => {
    expect(compareVersions('4.20.15', '4.20.15')).toBe(0);
  });

  it('returns 1 when a > b (different patch)', () => {
    expect(compareVersions('4.20.15', '4.20.9')).toBe(1);
  });

  it('handles different minor versions', () => {
    expect(compareVersions('4.19.99', '4.20.0')).toBe(-1);
    expect(compareVersions('4.21.0', '4.20.99')).toBe(1);
  });

  it('handles different major versions', () => {
    expect(compareVersions('3.20.0', '4.20.0')).toBe(-1);
  });

  it('handles versions with different segment counts', () => {
    expect(compareVersions('4.20', '4.20.0')).toBe(0);
    expect(compareVersions('4.20', '4.20.1')).toBe(-1);
  });
});

describe('max version filtering (integration logic)', () => {
  it('filters releases to only include versions >= min', () => {
    const releases = ['4.20.0', '4.20.5', '4.20.10', '4.20.15'];
    const minVersion = '4.20.10';
    const filtered = releases.filter(v => compareVersions(v, minVersion) >= 0);
    expect(filtered).toEqual(['4.20.10', '4.20.15']);
  });

  it('shows all releases when no min is selected', () => {
    const releases = ['4.20.0', '4.20.5', '4.20.10'];
    const minVersion = '';
    const filtered = releases.filter(v => !minVersion || compareVersions(v, minVersion) >= 0);
    expect(filtered).toEqual(['4.20.0', '4.20.5', '4.20.10']);
  });

  it('includes the min version itself in the filtered list', () => {
    const releases = ['4.20.0', '4.20.5', '4.20.10'];
    const minVersion = '4.20.5';
    const filtered = releases.filter(v => compareVersions(v, minVersion) >= 0);
    expect(filtered).toEqual(['4.20.5', '4.20.10']);
  });
});
