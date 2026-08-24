#!/usr/bin/env python3
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

SOURCE = Path("src/components/media/media.new.tsx")
TEMP_WORKFLOW = ".github/workflows/a16-retry-timers-temp.yml"
TEMP_SCRIPT = "scripts/a16-retry-timers-temp.py"

REPLACEMENTS = [
    (
        "    let recoveryTimeoutId: NodeJS.Timeout | undefined;\n",
        "    const recoveryTimeoutIds = new Set<NodeJS.Timeout>();\n",
    ),
    (
        """            recoveryTimeoutId = setTimeout(() => {\n              fatalRetryPendingRef.current = false;\n              if (hlsRef.current === hls) {\n                hls.startLoad();\n              }\n            }, delay);\n""",
        """            const recoveryTimeoutId = setTimeout(() => {\n              recoveryTimeoutIds.delete(recoveryTimeoutId);\n              fatalRetryPendingRef.current = false;\n              if (hlsRef.current === hls) {\n                hls.startLoad();\n              }\n            }, delay);\n            recoveryTimeoutIds.add(recoveryTimeoutId);\n""",
    ),
    (
        """      // Cleared before destroy() so a pending retry can never call startLoad()\n      // on a torn-down instance.\n      if (recoveryTimeoutId) {\n        clearTimeout(recoveryTimeoutId);\n      }\n""",
        """      // Cleared before destroy() so pending retries can never call startLoad()\n      // on a torn-down instance.\n      recoveryTimeoutIds.forEach((timeoutId) => clearTimeout(timeoutId));\n      recoveryTimeoutIds.clear();\n""",
    ),
]


def prepare():
    text = SOURCE.read_text(encoding="utf-8")
    for old, new in REPLACEMENTS:
        count = text.count(old)
        if count != 1:
            raise SystemExit(f"expected exactly one replacement target, found {count}: {old[:80]!r}")
        text = text.replace(old, new, 1)
    SOURCE.write_text(text, encoding="utf-8")


def api(method, path, payload=None):
    token = os.environ["GH_TOKEN"]
    repo = os.environ["GITHUB_REPOSITORY"]
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
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
        with urllib.request.urlopen(request) as response:
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
        raise SystemExit("branch head changed before A16 retry-timer publication")

    text = SOURCE.read_text(encoding="utf-8")
    if text.count("const recoveryTimeoutIds = new Set<NodeJS.Timeout>();") != 1:
        raise SystemExit("prepared retry-timeout set is missing")
    if text.count("recoveryTimeoutIds.add(recoveryTimeoutId);") != 1:
        raise SystemExit("prepared retry-timeout tracking is missing")
    if text.count("recoveryTimeoutIds.forEach((timeoutId) => clearTimeout(timeoutId));") != 1:
        raise SystemExit("prepared retry-timeout cleanup is missing")
    if "let recoveryTimeoutId: NodeJS.Timeout | undefined;" in text:
        raise SystemExit("old single retry-timeout slot is still present")

    content = SOURCE.read_bytes()
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
                {"path": str(SOURCE), "mode": "100644", "type": "blob", "sha": blob},
                {"path": TEMP_WORKFLOW, "mode": "100644", "type": "blob", "sha": None},
                {"path": TEMP_SCRIPT, "mode": "100644", "type": "blob", "sha": None},
            ],
        },
    )["sha"]
    new_commit = api(
        "POST",
        "git/commits",
        {"message": "refactor: track fatal retry timers for cleanup", "tree": tree, "parents": [expected]},
    )["sha"]
    if ref_sha(branch) != expected:
        raise SystemExit("branch head changed before A16 retry-timer ref update")
    api("PATCH", f"git/refs/heads/{branch}", {"sha": new_commit, "force": False})
    print(f"published {new_commit} with media blob {blob}")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"prepare", "publish"}:
        raise SystemExit("usage: a16-retry-timers-temp.py prepare|publish")
    if sys.argv[1] == "prepare":
        prepare()
    else:
        publish()
