#!/usr/bin/env python3
import json
import os
import urllib.parse
import urllib.request

MEDIA = "src/components/media/media.new.tsx"
LEVELS = "src/utils/hlsLevels.ts"
TEST = "src/utils/hlsLevels.test.ts"
WORKFLOW = ".github/workflows/a13-hls-level-identity-temp.yml"
SCRIPT = "scripts/a13-hls-level-identity-temp.py"


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
    with open(TEST, encoding="utf-8") as f:
        test = f.read()

    media = replace_once(
        media,
        "import { findHlsFixedLevelIndex, findLevelIndexForQuality, getHlsFixedLevelChoices } from 'utils/hlsLevels';",
        "import { findHlsFixedLevelChoiceByFingerprint, findHlsFixedLevelIndex, findLevelIndexForQuality, getHlsFixedLevelChoices, getHlsFixedLevelFingerprint } from 'utils/hlsLevels';",
        "hlsLevels import",
    )

    media = replace_once(
        media,
        "  // Exact manifest-level choices are separate from API source tracks: choosing one pins an HLS\n  // level in place without replacing the source URL. Keep the name in a ref too so a recovery\n  // rebuild can re-apply the same exact level after the replacement manifest arrives.\n  const [fixedHlsLevelName, setFixedHlsLevelName] = useState<string | null>(null);\n  const fixedHlsLevelNameRef = useRef<string | null>(null);",
        "  // Exact manifest-level choices are separate from API source tracks: choosing one pins an HLS\n  // level in place without replacing the source URL. Keep a rendition fingerprint in a ref so a\n  // recovery rebuild can find the same rendition even when the replacement manifest reorders it.\n  const [fixedHlsLevelName, setFixedHlsLevelName] = useState<string | null>(null);\n  const fixedHlsLevelFingerprintRef = useRef<string | null>(null);",
        "fixed HLS identity state",
    )

    media = media.replace("fixedHlsLevelNameRef.current = null;", "fixedHlsLevelFingerprintRef.current = null;")
    if media.count("fixedHlsLevelNameRef.current") != 2:
        raise SystemExit(f"fixed HLS name ref: expected two remaining selection/recovery references, found {media.count('fixedHlsLevelNameRef.current')}")

    media = replace_once(
        media,
        "      const fixedHlsLevelIndex = findHlsFixedLevelIndex(hlsRef.current?.levels, sourceTrackName);\n      if (fixedHlsLevelIndex !== -1 && hlsRef.current && hlsRef.current.levels.length > 1) {\n        fixedHlsLevelNameRef.current = sourceTrackName;\n        setFixedHlsLevelName(sourceTrackName);\n        qualityModeRef.current = 'fixed';\n        setQualityMode('fixed');\n        hlsRef.current.nextLevel = fixedHlsLevelIndex;\n        return;\n      }",
        "      const hls = hlsRef.current;\n      const fixedHlsLevelIndex = findHlsFixedLevelIndex(hls?.levels, sourceTrackName);\n      if (fixedHlsLevelIndex !== -1 && hls && hls.levels.length > 1) {\n        fixedHlsLevelFingerprintRef.current = getHlsFixedLevelFingerprint(hls.levels[fixedHlsLevelIndex]);\n        setFixedHlsLevelName(sourceTrackName);\n        qualityModeRef.current = 'fixed';\n        setQualityMode('fixed');\n        hls.nextLevel = fixedHlsLevelIndex;\n        return;\n      }",
        "exact HLS selection stores rendition fingerprint",
    )

    media = replace_once(
        media,
        "          if (isAdaptive && fixedHlsLevelNameRef.current) {\n            const fixedLevelIndex = findHlsFixedLevelIndex(hls.levels, fixedHlsLevelNameRef.current);\n            if (fixedLevelIndex !== -1) {\n              hls.currentLevel = fixedLevelIndex;\n              return;\n            }\n\n            fixedHlsLevelNameRef.current = null;\n            setFixedHlsLevelName(null);\n          }",
        "          if (isAdaptive && fixedHlsLevelFingerprintRef.current) {\n            const fixedLevelChoice = findHlsFixedLevelChoiceByFingerprint(hls.levels, fixedHlsLevelFingerprintRef.current);\n            if (fixedLevelChoice) {\n              setFixedHlsLevelName(fixedLevelChoice.name);\n              hls.currentLevel = fixedLevelChoice.index;\n              return;\n            }\n\n            fixedHlsLevelFingerprintRef.current = null;\n            setFixedHlsLevelName(null);\n          }",
        "manifest restores rendition by fingerprint",
    )

    if "fixedHlsLevelNameRef" in media:
        raise SystemExit("stale fixedHlsLevelNameRef remains")

    levels = replace_once(
        levels,
        "type LevelLike = {\n  width?: number;\n  height?: number;\n};",
        "type LevelLike = {\n  width?: number;\n  height?: number;\n  bitrate?: number;\n  videoCodec?: string;\n  audioCodec?: string;\n  name?: string;\n};",
        "level identity fields",
    )

    levels = replace_once(
        levels,
        "function getPositiveNumber(value: unknown) {\n  return typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : 0;\n}",
        "function getPositiveNumber(value: unknown) {\n  return typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : 0;\n}\n\nfunction getStableString(value: unknown) {\n  return typeof value === 'string' ? value : '';\n}",
        "stable string helper",
    )

    levels = replace_once(
        levels,
        "export function getHlsFixedLevelChoices(levels: readonly LevelLike[] | undefined): HlsFixedLevelChoice[] {\n  return (levels || []).map((level, index) => ({ index, name: getHlsFixedLevelSourceName(level, index) }));\n}\n\nexport function findHlsFixedLevelIndex(levels: readonly LevelLike[] | undefined, sourceName: string) {\n  return getHlsFixedLevelChoices(levels).find((choice) => choice.name === sourceName)?.index ?? -1;\n}",
        "export function getHlsFixedLevelChoices(levels: readonly LevelLike[] | undefined): HlsFixedLevelChoice[] {\n  return (levels || []).map((level, index) => ({ index, name: getHlsFixedLevelSourceName(level, index) }));\n}\n\nexport function findHlsFixedLevelIndex(levels: readonly LevelLike[] | undefined, sourceName: string) {\n  return getHlsFixedLevelChoices(levels).find((choice) => choice.name === sourceName)?.index ?? -1;\n}\n\n/**\n * Stable identity for restoring a user-selected rendition after an HLS rebuild. The UI label keeps\n * the current manifest index for disambiguation, while recovery keys on rendition metadata that is\n * expected to survive manifest reordering.\n */\nexport function getHlsFixedLevelFingerprint(level: LevelLike) {\n  return [\n    getPositiveNumber(level?.width),\n    getPositiveNumber(level?.height),\n    getPositiveNumber(level?.bitrate),\n    getStableString(level?.videoCodec),\n    getStableString(level?.audioCodec),\n    getStableString(level?.name),\n  ].join('|');\n}\n\nexport function findHlsFixedLevelChoiceByFingerprint(levels: readonly LevelLike[] | undefined, fingerprint: string) {\n  const index = (levels || []).findIndex((level) => getHlsFixedLevelFingerprint(level) === fingerprint);\n  return index === -1 ? undefined : { index, name: getHlsFixedLevelSourceName(levels![index], index) };\n}",
        "stable rendition lookup",
    )

    test = replace_once(
        test,
        "import { findHlsFixedLevelIndex, getHlsFixedLevelChoices, getHlsFixedLevelSourceName } from './hlsLevels';",
        "import { findHlsFixedLevelChoiceByFingerprint, findHlsFixedLevelIndex, getHlsFixedLevelChoices, getHlsFixedLevelFingerprint, getHlsFixedLevelSourceName } from './hlsLevels';",
        "test imports",
    )

    test = replace_once(
        test,
        "  const levels = [\n    { width: 1920, height: 804 },\n    { width: 1920, height: 804 },\n    { width: 1280, height: 536 },\n  ];",
        "  const levels = [\n    { width: 1920, height: 804, bitrate: 4000000, videoCodec: 'avc1.640028' },\n    { width: 1920, height: 804, bitrate: 8000000, videoCodec: 'avc1.640032' },\n    { width: 1280, height: 536, bitrate: 2500000, videoCodec: 'avc1.64001f' },\n  ];",
        "test rendition metadata",
    )

    test = replace_once(
        test,
        "  test('falls back to a deterministic level label when dimensions are unavailable', () => {\n    expect(getHlsFixedLevelSourceName({}, 0)).toBe('HLS 1: качество неизвестно');\n  });",
        "  test('restores the same rendition when a replacement manifest reorders equal-resolution levels', () => {\n    const fingerprint = getHlsFixedLevelFingerprint(levels[0]);\n    const reordered = [levels[1], levels[0], levels[2]];\n\n    expect(findHlsFixedLevelChoiceByFingerprint(reordered, fingerprint)).toEqual({\n      index: 1,\n      name: 'HLS 2: 1080p (1920x804)',\n    });\n  });\n\n  test('falls back to a deterministic level label when dimensions are unavailable', () => {\n    expect(getHlsFixedLevelSourceName({}, 0)).toBe('HLS 1: качество неизвестно');\n  });",
        "reorder recovery test",
    )

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

    with open(LEVELS, encoding="utf-8") as f:
        levels_text = f.read()
    with open(MEDIA, encoding="utf-8") as f:
        media_text = f.read()
    with open(TEST, encoding="utf-8") as f:
        test_text = f.read()

    required = [
        "getHlsFixedLevelFingerprint",
        "findHlsFixedLevelChoiceByFingerprint",
        "fixedHlsLevelFingerprintRef",
        "reorders equal-resolution levels",
    ]
    combined = levels_text + media_text + test_text
    for marker in required:
        if marker not in combined:
            raise SystemExit(f"missing durable identity marker: {marker}")
    if "fixedHlsLevelNameRef" in media_text:
        raise SystemExit("stale name-based recovery ref remains")

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
    durable = api("POST", "/git/commits", {"message": "fix: restore exact HLS rendition identity", "tree": tree, "parents": [expected]})["sha"]

    current = api("GET", f"/git/ref/heads/{quoted}")["object"]["sha"]
    if current != expected:
        raise SystemExit(f"head moved before ref update: expected {expected}, got {current}")
    api("PATCH", f"/git/refs/heads/{quoted}", {"sha": durable, "force": False})
    print(durable)


if __name__ == "__main__":
    if len(os.sys.argv) != 2 or os.sys.argv[1] not in {"prepare", "publish"}:
        raise SystemExit("usage: a13-hls-level-identity-temp.py prepare|publish")
    globals()[os.sys.argv[1]]()
