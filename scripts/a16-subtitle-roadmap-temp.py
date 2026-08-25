#!/usr/bin/env python3
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROADMAP = Path("ROADMAP.md")
WORKFLOW_PATH = ".github/workflows/a16-subtitle-roadmap-temp.yml"
SCRIPT_PATH = "scripts/a16-subtitle-roadmap-temp.py"

REPLACEMENTS = [
    (
        "  - `player.tsx:194-203` appends `#subtitle-opacity-style` to `document.head` and never removes it —\n    the one lifecycle asymmetry in otherwise careful cleanup code.\n",
        "  - **Completed substep:** the subtitle-opacity effect still owns the same global\n    `#subtitle-opacity-style` element and `video::cue` opacity rule, but now removes that style during\n    effect cleanup so repeated player mounts do not leave global style state behind. Opacity values and\n    storage behaviour are unchanged.\n",
    ),
    (
        "- **Implemented progress / remaining direction:** Three bounded maintenance substeps are complete:\n  `MediaEvents` now covers the live event-name values; `video.tsx` now takes `SourceTrack` from the\n  live `components/media` barrel with the dead legacy `media.tsx` removed; and fatal-network retry\n  timers are tracked and cleaned up as a set without changing retry policy. The nearby\n  `onAudioChange` `@ts-expect-error` remains intentionally untouched pending separate evidence. Remove\n  the style element on unmount. Decide about the extra app ids deliberately.\n",
        "- **Implemented progress / remaining direction:** Four bounded maintenance substeps are complete:\n  `MediaEvents` now covers the live event-name values; `video.tsx` now takes `SourceTrack` from the\n  live `components/media` barrel with the dead legacy `media.tsx` removed; fatal-network retry timers\n  are tracked and cleaned up as a set without changing retry policy; and the subtitle-opacity style\n  now has symmetric effect cleanup without changing opacity semantics. The nearby `onAudioChange`\n  `@ts-expect-error` remains intentionally untouched pending separate evidence. Decide about the extra\n  app ids deliberately.\n",
    ),
    (
        "- **Validation and acceptance criteria:** The completed `MediaEvents`, legacy-media type-source, and\n  retry-timer substeps have green typecheck, lint, test and build CI; the retry-timer change also\n  passed ES5 validation. Remaining A16 cleanup must preserve those checks; playback and quality\n  switching unchanged on the TV remains device acceptance where a remaining cleanup can affect\n  playback behaviour.\n",
        "- **Validation and acceptance criteria:** The completed `MediaEvents`, legacy-media type-source,\n  retry-timer, and subtitle-style lifecycle substeps have green typecheck, lint, test and build CI;\n  the retry-timer and subtitle-style changes also passed ES5 validation. Remaining A16 cleanup must\n  preserve those checks; playback and quality switching unchanged on the TV remains device acceptance\n  where a remaining cleanup can affect playback behaviour.\n",
    ),
]


def prepare() -> None:
    text = ROADMAP.read_text(encoding="utf-8")
    start = text.index("### A16 — Retire dead code and small inherited defects")
    end = text.index("\n### A17 —", start)
    block = text[start:end]
    for old, new in REPLACEMENTS:
        count = block.count(old)
        if count != 1:
            raise SystemExit(f"expected exactly one A16 replacement target, found {count}: {old[:80]!r}")
        block = block.replace(old, new, 1)
    text = text[:start] + block + text[end:]
    ROADMAP.write_text(text, encoding="utf-8")


def request(method: str, path: str, token: str, body=None):
    url = f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}{path}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise SystemExit(f"GitHub API {method} {path} failed: HTTP {exc.code}: {detail}")
    return json.loads(payload.decode("utf-8")) if payload else None


def ref_sha(branch: str, token: str) -> str:
    quoted = urllib.parse.quote(branch, safe="/")
    return request("GET", f"/git/ref/heads/{quoted}", token)["object"]["sha"]


def publish() -> None:
    token = os.environ["GH_TOKEN"]
    expected = os.environ["EXPECTED_HEAD"]
    branch = os.environ["HEAD_BRANCH"]
    if ref_sha(branch, token) != expected:
        raise SystemExit("branch head moved before roadmap publication")

    commit = request("GET", f"/git/commits/{expected}", token)
    roadmap_blob = request(
        "POST",
        "/git/blobs",
        token,
        {"content": ROADMAP.read_text(encoding="utf-8"), "encoding": "utf-8"},
    )["sha"]
    tree = request(
        "POST",
        "/git/trees",
        token,
        {
            "base_tree": commit["tree"]["sha"],
            "tree": [
                {"path": "ROADMAP.md", "mode": "100644", "type": "blob", "sha": roadmap_blob},
                {"path": WORKFLOW_PATH, "mode": "100644", "type": "blob", "sha": None},
                {"path": SCRIPT_PATH, "mode": "100644", "type": "blob", "sha": None},
            ],
        },
    )["sha"]
    new_commit = request(
        "POST",
        "/git/commits",
        token,
        {"message": "docs: reconcile A16 subtitle style cleanup", "tree": tree, "parents": [expected]},
    )["sha"]

    if ref_sha(branch, token) != expected:
        raise SystemExit("branch head moved before final roadmap ref update")
    quoted = urllib.parse.quote(branch, safe="/")
    request("PATCH", f"/git/refs/heads/{quoted}", token, {"sha": new_commit, "force": False})
    print(new_commit)


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"prepare", "publish"}:
        raise SystemExit("usage: a16-subtitle-roadmap-temp.py prepare|publish")
    if sys.argv[1] == "prepare":
        prepare()
    else:
        publish()
