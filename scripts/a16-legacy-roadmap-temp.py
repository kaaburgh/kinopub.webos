#!/usr/bin/env python3
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROADMAP = Path("ROADMAP.md")
START = "### A16 — Retire dead code and small inherited defects"
END = "### A17 — Find out whether upstream has moved, and whether older webOS still works"
TEMP_WORKFLOW = ".github/workflows/a16-legacy-roadmap-temp.yml"
TEMP_SCRIPT = "scripts/a16-legacy-roadmap-temp.py"

REPLACEMENTS = [
    (
        """  - `src/components/media/media.tsx` (218 lines, the legacy Enact class implementation) is reachable\n    from nothing — `index.ts` re-exports `media.new` only — except `views/video/video.tsx:6`, which\n    imports the type `SourceTrack` from it. That type differs from the live one (no `number`, no\n    `default`, no `type`) and types `onSourceChange` three lines above a `// @ts-expect-error`\n    (`video.tsx:221`), so `tsc` sees neither half of the mismatch.\n""",
        """  - **Completed substep:** `src/views/video/video.tsx` now imports `SourceTrack` through the live\n    `components/media` barrel, and the dead legacy `src/components/media/media.tsx` implementation\n    has been removed. The nearby `onAudioChange` `@ts-expect-error` was left untouched because this\n    bounded cleanup produced no evidence that it belongs to the legacy type source.\n""",
    ),
    (
        """- **Implemented progress / remaining direction:** The `MediaEvents` type-coverage substep is\n  complete. Point `video.tsx` at `components/media` and delete `media.tsx`; then find out what the\n  `@ts-expect-error` on `:221` was hiding, since it may stop being needed or may reveal a genuine\n  mismatch. Track and clear the retry timers as a set. Remove the style element on unmount. Decide\n  about the extra app ids deliberately.\n""",
        """- **Implemented progress / remaining direction:** Two bounded type-source substeps are complete:\n  `MediaEvents` now covers the live event-name values, and `video.tsx` now takes `SourceTrack` from\n  the live `components/media` barrel with the dead legacy `media.tsx` removed. The nearby\n  `onAudioChange` `@ts-expect-error` remains intentionally untouched pending separate evidence. Track\n  and clear the retry timers as a set. Remove the style element on unmount. Decide about the extra\n  app ids deliberately.\n""",
    ),
    (
        """- **Validation and acceptance criteria:** The completed `MediaEvents` substep has green typecheck,\n  lint, test and build CI. Remaining A16 cleanup must preserve those checks; playback and quality\n  switching unchanged on the TV remains device acceptance where a remaining cleanup can affect\n  playback behaviour.\n""",
        """- **Validation and acceptance criteria:** The completed `MediaEvents` and legacy-media type-source\n  substeps have green typecheck, lint, test and build CI. Remaining A16 cleanup must preserve those\n  checks; playback and quality switching unchanged on the TV remains device acceptance where a\n  remaining cleanup can affect playback behaviour.\n""",
    ),
]


def prepare():
    text = ROADMAP.read_text(encoding="utf-8")
    if text.count(START) != 1 or text.count(END) != 1:
        raise SystemExit("A16/A17 roadmap boundaries are not unique")
    before, rest = text.split(START, 1)
    block, after = rest.split(END, 1)
    block = START + block
    for old, new in REPLACEMENTS:
        count = block.count(old)
        if count != 1:
            raise SystemExit(f"expected exactly one A16 replacement target, found {count}: {old[:80]!r}")
        block = block.replace(old, new, 1)
    ROADMAP.write_text(before + block + END + after, encoding="utf-8")


def api(method, path, payload=None):
    token = os.environ["GH_TOKEN"]
    repo = os.environ["GITHUB_REPOSITORY"]
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        sys.stderr.write(exc.read().decode("utf-8", errors="replace"))
        raise


def ref_sha(branch):
    return api("GET", f"git/ref/heads/{branch}")["object"]["sha"]


def publish():
    expected = os.environ["EXPECTED_HEAD"]
    branch = os.environ["HEAD_BRANCH"]
    if ref_sha(branch) != expected:
        raise SystemExit("branch head changed before A16 roadmap publication")

    content = ROADMAP.read_bytes()
    blob = api(
        "POST",
        "git/blobs",
        {"content": base64.b64encode(content).decode("ascii"), "encoding": "base64"},
    )["sha"]
    commit = api("GET", f"git/commits/{expected}")
    tree = api(
        "POST",
        "git/trees",
        {
            "base_tree": commit["tree"]["sha"],
            "tree": [
                {"path": "ROADMAP.md", "mode": "100644", "type": "blob", "sha": blob},
                {"path": TEMP_WORKFLOW, "mode": "100644", "type": "blob", "sha": None},
                {"path": TEMP_SCRIPT, "mode": "100644", "type": "blob", "sha": None},
            ],
        },
    )["sha"]
    new_commit = api(
        "POST",
        "git/commits",
        {"message": "docs: reconcile A16 legacy media cleanup", "tree": tree, "parents": [expected]},
    )["sha"]
    if ref_sha(branch) != expected:
        raise SystemExit("branch head changed before A16 roadmap ref update")
    api("PATCH", f"git/refs/heads/{branch}", {"sha": new_commit, "force": False})
    print(f"published {new_commit} with ROADMAP blob {blob}")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"prepare", "publish"}:
        raise SystemExit("usage: a16-legacy-roadmap-temp.py prepare|publish")
    if sys.argv[1] == "prepare":
        prepare()
    else:
        publish()
