#!/usr/bin/env python3
import json
import os
import sys
import urllib.parse
import urllib.request

MEDIA = "src/components/media/media.new.tsx"
LEVELS = "src/utils/hlsLevels.ts"
TEST = "src/utils/hlsLevels.test.ts"
WORKFLOW = ".github/workflows/a13-hls-level-choices-temp.yml"
SCRIPT = "scripts/a13-hls-level-choices-temp.py"


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def prepare():
    with open(MEDIA, encoding="utf-8") as f:
        media = f.read()
    with open(LEVELS, encoding="utf-8") as f:
        levels = f.read()

    media = replace_once(
        media,
        "import { findLevelIndexForQuality } from 'utils/hlsLevels';",
        "import { findHlsFixedLevelIndex, findLevelIndexForQuality, getHlsFixedLevelChoices } from 'utils/hlsLevels';",
        "hlsLevels import",
    )

    media = replace_once(
        media,
        "  const [qualityMode, setQualityMode] = useState<'auto' | 'fixed'>('fixed');\n  // Mirrors qualityMode synchronously so a pending Auto request survives a\n  // replacement manifest that is still loading (see setSourceTrack below).\n  const qualityModeRef = useRef(qualityMode);",
        "  const [qualityMode, setQualityMode] = useState<'auto' | 'fixed'>('fixed');\n  // Exact manifest-level choices are separate from API source tracks: choosing one pins an HLS\n  // level in place without replacing the source URL. Keep the name in a ref too so a recovery\n  // rebuild can re-apply the same exact level after the replacement manifest arrives.\n  const [fixedHlsLevelName, setFixedHlsLevelName] = useState<string | null>(null);\n  const fixedHlsLevelNameRef = useRef<string | null>(null);\n  // Mirrors qualityMode synchronously so a pending Auto request survives a\n  // replacement manifest that is still loading (see setSourceTrack below).\n  const qualityModeRef = useRef(qualityMode);",
        "fixed HLS level state",
    )

    media = replace_once(
        media,
        "    // Only a genuine master playlist with multiple HLS levels gets an\n    // explicit Auto option, delegating level selection to HLS.js.\n    return [{ ...currentSourceTrack, name: AUTO_SOURCE_NAME, default: false }, ...sourceTracks];\n  }, [sourceTracks, isAdaptiveLevel, currentSourceTrack]);\n  const getSourceTrack = useCallback(\n    () => (qualityMode === 'auto' && isAdaptiveLevel ? AUTO_SOURCE_NAME : currentSourceTrack?.name),\n    [qualityMode, isAdaptiveLevel, currentSourceTrack],\n  );",
        "    // Only a genuine master playlist with multiple HLS levels gets Auto and exact manifest\n    // choices. The synthetic tracks intentionally reuse the current source URL: selecting one must\n    // pin hls.js in place, not route through the API source-change path.\n    const hlsLevelTracks = getHlsFixedLevelChoices(hlsRef.current?.levels).map(({ name }) => ({\n      ...currentSourceTrack,\n      name,\n      default: false,\n    }));\n\n    return [{ ...currentSourceTrack, name: AUTO_SOURCE_NAME, default: false }, ...sourceTracks, ...hlsLevelTracks];\n  }, [sourceTracks, isAdaptiveLevel, currentSourceTrack]);\n  const getSourceTrack = useCallback(\n    () => (qualityMode === 'auto' && isAdaptiveLevel ? AUTO_SOURCE_NAME : fixedHlsLevelName || currentSourceTrack?.name),\n    [qualityMode, isAdaptiveLevel, fixedHlsLevelName, currentSourceTrack],\n  );",
        "source track choices",
    )

    media = replace_once(
        media,
        "      if (sourceTrackName === AUTO_SOURCE_NAME) {\n        qualityModeRef.current = 'auto';\n        setQualityMode('auto');",
        "      if (sourceTrackName === AUTO_SOURCE_NAME) {\n        fixedHlsLevelNameRef.current = null;\n        setFixedHlsLevelName(null);\n        qualityModeRef.current = 'auto';\n        setQualityMode('auto');",
        "auto clears fixed HLS level",
    )

    media = replace_once(
        media,
        "      const sourceTrackIndex = sourceTracks?.findIndex((sourceTrack) => sourceTrack.name === sourceTrackName) ?? -1;\n      if (sourceTrackIndex !== -1) {",
        "      const fixedHlsLevelIndex = findHlsFixedLevelIndex(hlsRef.current?.levels, sourceTrackName);\n      if (fixedHlsLevelIndex !== -1 && hlsRef.current && hlsRef.current.levels.length > 1) {\n        fixedHlsLevelNameRef.current = sourceTrackName;\n        setFixedHlsLevelName(sourceTrackName);\n        qualityModeRef.current = 'fixed';\n        setQualityMode('fixed');\n        hlsRef.current.nextLevel = fixedHlsLevelIndex;\n        return;\n      }\n\n      const sourceTrackIndex = sourceTracks?.findIndex((sourceTrack) => sourceTrack.name === sourceTrackName) ?? -1;\n      if (sourceTrackIndex !== -1) {",
        "exact HLS level selection",
    )

    media = replace_once(
        media,
        "        const sourceTrack = sourceTracks![sourceTrackIndex];\n        qualityModeRef.current = 'fixed';",
        "        const sourceTrack = sourceTracks![sourceTrackIndex];\n        fixedHlsLevelNameRef.current = null;\n        setFixedHlsLevelName(null);\n        qualityModeRef.current = 'fixed';",
        "API source clears exact HLS selection",
    )

    media = replace_once(
        media,
        "          if (isAdaptive) {\n            const levelIndex = findLevelIndexForQuality(hls.levels, currentSourceTrackRef.current?.name || '');\n            if (levelIndex !== -1) {\n              hls.currentLevel = levelIndex;\n            }\n          }",
        "          if (isAdaptive && fixedHlsLevelNameRef.current) {\n            const fixedLevelIndex = findHlsFixedLevelIndex(hls.levels, fixedHlsLevelNameRef.current);\n            if (fixedLevelIndex !== -1) {\n              hls.currentLevel = fixedLevelIndex;\n              return;\n            }\n\n            fixedHlsLevelNameRef.current = null;\n            setFixedHlsLevelName(null);\n          }\n\n          if (isAdaptive) {\n            const levelIndex = findLevelIndexForQuality(hls.levels, currentSourceTrackRef.current?.name || '');\n            if (levelIndex !== -1) {\n              hls.currentLevel = levelIndex;\n            }\n          }",
        "manifest restores exact HLS level",
    )

    levels = replace_once(
        levels,
        "type LevelLike = {\n  width?: number;\n  height?: number;\n};",
        "type LevelLike = {\n  width?: number;\n  height?: number;\n};\n\nexport type HlsFixedLevelChoice = {\n  index: number;\n  name: string;\n};",
        "HLS fixed choice type",
    )

    levels += """

/**
 * Stable, human-readable name for an exact level from a master playlist.
 *
 * The level index is part of the name deliberately: manifests can contain two renditions with the
 * same resolution but different bitrates/codecs, and A13 requires every manifest level to remain
 * independently selectable rather than collapsing them by nominal quality.
 */
export function getHlsFixedLevelSourceName(level: LevelLike, index: number) {
  const qualityHeight = getLevelQualityHeight(level);
  const width = getPositiveNumber(level?.width);
  const height = getPositiveNumber(level?.height);
  const quality = qualityHeight ? `${qualityHeight}p` : 'качество неизвестно';
  const resolution = width && height ? ` (${width}x${height})` : '';

  return `HLS ${index + 1}: ${quality}${resolution}`;
}

export function getHlsFixedLevelChoices(levels: readonly LevelLike[] | undefined): HlsFixedLevelChoice[] {
  return (levels || []).map((level, index) => ({ index, name: getHlsFixedLevelSourceName(level, index) }));
}

export function findHlsFixedLevelIndex(levels: readonly LevelLike[] | undefined, sourceName: string) {
  return getHlsFixedLevelChoices(levels).find((choice) => choice.name === sourceName)?.index ?? -1;
}
"""

    test = """import { findHlsFixedLevelIndex, getHlsFixedLevelChoices, getHlsFixedLevelSourceName } from './hlsLevels';

describe('exact HLS level choices', () => {
  const levels = [
    { width: 1920, height: 804 },
    { width: 1920, height: 804 },
    { width: 1280, height: 536 },
  ];

  test('keeps every manifest level selectable even when resolutions repeat', () => {
    expect(getHlsFixedLevelChoices(levels)).toEqual([
      { index: 0, name: 'HLS 1: 1080p (1920x804)' },
      { index: 1, name: 'HLS 2: 1080p (1920x804)' },
      { index: 2, name: 'HLS 3: 720p (1280x536)' },
    ]);
  });

  test('resolves only names generated for the current manifest', () => {
    const second = getHlsFixedLevelSourceName(levels[1], 1);

    expect(findHlsFixedLevelIndex(levels, second)).toBe(1);
    expect(findHlsFixedLevelIndex(levels, 'HLS 4: 2160p (3840x1606)')).toBe(-1);
  });

  test('falls back to a deterministic level label when dimensions are unavailable', () => {
    expect(getHlsFixedLevelSourceName({}, 0)).toBe('HLS 1: качество неизвестно');
  });
});
"""

    with open(MEDIA, "w", encoding="utf-8") as f:
        f.write(media)
    with open(LEVELS, "w", encoding="utf-8") as f:
        f.write(levels)
    with open(TEST, "w", encoding="utf-8") as f:
        f.write(test)


def api(method, path, payload=None):
    token = os.environ["GH_TOKEN"]
    repo = os.environ["GITHUB_REPOSITORY"]
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}{path}",
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as response:
        return json.load(response)


def publish():
    expected = os.environ["EXPECTED_HEAD"]
    branch = os.environ["HEAD_BRANCH"]
    quoted = urllib.parse.quote(branch, safe="")
    current = api("GET", f"/git/ref/heads/{quoted}")["object"]["sha"]
    if current != expected:
        raise SystemExit(f"head moved before publish: expected {expected}, got {current}")

    commit = api("GET", f"/git/commits/{expected}")
    entries = []
    for path in (MEDIA, LEVELS, TEST):
        with open(path, encoding="utf-8") as f:
            blob = api("POST", "/git/blobs", {"content": f.read(), "encoding": "utf-8"})["sha"]
        entries.append({"path": path, "mode": "100644", "type": "blob", "sha": blob})
    entries.extend([
        {"path": WORKFLOW, "mode": "100644", "type": "blob", "sha": None},
        {"path": SCRIPT, "mode": "100644", "type": "blob", "sha": None},
    ])
    tree = api("POST", "/git/trees", {"base_tree": commit["tree"]["sha"], "tree": entries})["sha"]
    durable = api("POST", "/git/commits", {"message": "feat: expose exact HLS levels as fixed choices", "tree": tree, "parents": [expected]})["sha"]

    current = api("GET", f"/git/ref/heads/{quoted}")["object"]["sha"]
    if current != expected:
        raise SystemExit(f"head moved during publish: expected {expected}, got {current}")
    api("PATCH", f"/git/refs/heads/{quoted}", {"sha": durable, "force": False})
    print(durable)


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"prepare", "publish"}:
        raise SystemExit("usage: a13-hls-level-choices-temp.py prepare|publish")
    prepare() if sys.argv[1] == "prepare" else publish()
