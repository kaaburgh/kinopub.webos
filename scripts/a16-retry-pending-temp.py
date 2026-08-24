#!/usr/bin/env python3
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

SOURCE = Path("src/components/media/media.new.tsx")
TEMP_WORKFLOW = ".github/workflows/a16-retry-pending-temp.yml"
TEMP_SCRIPT = "scripts/a16-retry-pending-temp.py"
OLD = """              recoveryTimeoutIds.delete(recoveryTimeoutId);\n              fatalRetryPendingRef.current = false;\n"""
NEW = """              recoveryTimeoutIds.delete(recoveryTimeoutId);\n              fatalRetryPendingRef.current = recoveryTimeoutIds.size > 0;\n"""


def prepare():
    text = SOURCE.read_text(encoding="utf-8")
    count = text.count(OLD)
    if count != 1:
        raise SystemExit(f"expected exactly one retry pending-state target, found {count}")
    SOURCE.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")


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
        raise SystemExit("branch head changed before A16 retry pending-state publication")

    text = SOURCE.read_text(encoding="utf-8")
    if text.count(NEW) != 1:
        raise SystemExit("prepared retry pending-state invariant is missing")
    if OLD in text:
        raise SystemExit("old retry pending-state reset is still present")

    blob = api(
        "POST",
        "git/blobs",
        {"content": base64.b64encode(SOURCE.read_bytes()).decode("ascii"), "encoding": "base64"},
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
        {"message": "fix: keep fatal retry pending state until timers drain", "tree": tree, "parents": [expected]},
    )["sha"]
    if ref_sha(branch) != expected:
        raise SystemExit("branch head changed before A16 retry pending-state ref update")
    api("PATCH", f"git/refs/heads/{branch}", {"sha": new_commit, "force": False})
    print(f"published {new_commit} with media blob {blob}")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"prepare", "publish"}:
        raise SystemExit("usage: a16-retry-pending-temp.py prepare|publish")
    if sys.argv[1] == "prepare":
        prepare()
    else:
        publish()
