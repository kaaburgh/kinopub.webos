#!/usr/bin/env python3
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROADMAP = Path("ROADMAP.md")
WORKFLOW = ".github/workflows/a16-retry-roadmap-temp.yml"
SCRIPT = "scripts/a16-retry-roadmap-temp.py"

OLD_EVIDENCE = """  - `recoveryTimeoutId` is a single slot (`media.new.tsx:330`, `:448`), so a second fatal error inside\n    the backoff window orphans the first timer and the cleanup at `:546-548` clears only the last.\n    The `hlsRef.current === hls` guard at `:450` keeps this benign — the worst case is a duplicated\n    `startLoad()`, which `dist/hls.js:8771-8775` largely absorbs.\n"""
NEW_EVIDENCE = """  - **Completed substep:** fatal-network retry timeouts are tracked in a `Set<NodeJS.Timeout>`; each\n    callback removes its own timer, `fatalRetryPendingRef` stays true while another retry remains\n    pending, and media-effect cleanup clears every remaining retry timeout before HLS destruction.\n    Retry counts, backoff delays, and hls.js recovery policy are unchanged.\n"""

OLD_DIRECTION = """- **Implemented progress / remaining direction:** Two bounded type-source substeps are complete:\n  `MediaEvents` now covers the live event-name values, and `video.tsx` now takes `SourceTrack` from\n  the live `components/media` barrel with the dead legacy `media.tsx` removed. The nearby\n  `onAudioChange` `@ts-expect-error` remains intentionally untouched pending separate evidence. Track\n  and clear the retry timers as a set. Remove the style element on unmount. Decide about the extra\n  app ids deliberately.\n"""
NEW_DIRECTION = """- **Implemented progress / remaining direction:** Three bounded maintenance substeps are complete:\n  `MediaEvents` now covers the live event-name values; `video.tsx` now takes `SourceTrack` from the\n  live `components/media` barrel with the dead legacy `media.tsx` removed; and fatal-network retry\n  timers are tracked and cleaned up as a set without changing retry policy. The nearby\n  `onAudioChange` `@ts-expect-error` remains intentionally untouched pending separate evidence. Remove\n  the style element on unmount. Decide about the extra app ids deliberately.\n"""

OLD_VALIDATION = """- **Validation and acceptance criteria:** The completed `MediaEvents` and legacy-media type-source\n  substeps have green typecheck, lint, test and build CI. Remaining A16 cleanup must preserve those\n  checks; playback and quality switching unchanged on the TV remains device acceptance where a\n  remaining cleanup can affect playback behaviour.\n"""
NEW_VALIDATION = """- **Validation and acceptance criteria:** The completed `MediaEvents`, legacy-media type-source, and\n  retry-timer substeps have green typecheck, lint, test and build CI; the retry-timer change also\n  passed ES5 validation. Remaining A16 cleanup must preserve those checks; playback and quality\n  switching unchanged on the TV remains device acceptance where a remaining cleanup can affect\n  playback behaviour.\n"""


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def prepare():
    text = ROADMAP.read_text(encoding="utf-8")
    marker = "### A16 — Retire dead code and small inherited defects"
    if text.count(marker) != 1:
        raise SystemExit(f"A16 marker: expected exactly one match, found {text.count(marker)}")
    text = replace_once(text, OLD_EVIDENCE, NEW_EVIDENCE, "retry evidence")
    text = replace_once(text, OLD_DIRECTION, NEW_DIRECTION, "A16 direction")
    text = replace_once(text, OLD_VALIDATION, NEW_VALIDATION, "A16 validation")
    ROADMAP.write_text(text, encoding="utf-8")


def api(method, path, payload=None):
    repo = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GH_TOKEN"]
    url = f"https://api.github.com/repos/{repo}{path}"
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", "replace")
        raise SystemExit(f"GitHub API {method} {path} failed: {error.code} {body}")


def ref_sha(branch):
    encoded = urllib.parse.quote(branch, safe="")
    return api("GET", f"/git/ref/heads/{encoded}")["object"]["sha"]


def publish():
    expected = os.environ["EXPECTED_HEAD"]
    branch = os.environ["HEAD_BRANCH"]
    current = ref_sha(branch)
    if current != expected:
        raise SystemExit(f"branch moved before publication: expected {expected}, found {current}")

    commit = api("GET", f"/git/commits/{expected}")
    base_tree = commit["tree"]["sha"]
    roadmap_bytes = ROADMAP.read_bytes()
    blob = api(
        "POST",
        "/git/blobs",
        {"content": base64.b64encode(roadmap_bytes).decode("ascii"), "encoding": "base64"},
    )["sha"]

    tree = api(
        "POST",
        "/git/trees",
        {
            "base_tree": base_tree,
            "tree": [
                {"path": "ROADMAP.md", "mode": "100644", "type": "blob", "sha": blob},
                {"path": WORKFLOW, "mode": "100644", "type": "blob", "sha": None},
                {"path": SCRIPT, "mode": "100644", "type": "blob", "sha": None},
            ],
        },
    )["sha"]

    new_commit = api(
        "POST",
        "/git/commits",
        {"message": "docs: reconcile A16 retry timer cleanup", "tree": tree, "parents": [expected]},
    )["sha"]

    current = ref_sha(branch)
    if current != expected:
        raise SystemExit(f"branch moved before ref update: expected {expected}, found {current}")
    encoded = urllib.parse.quote(branch, safe="")
    api("PATCH", f"/git/refs/heads/{encoded}", {"sha": new_commit, "force": False})
    print(f"published {new_commit} with ROADMAP blob {blob}")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"prepare", "publish"}:
        raise SystemExit("usage: a16-retry-roadmap-temp.py prepare|publish")
    globals()[sys.argv[1]]()
