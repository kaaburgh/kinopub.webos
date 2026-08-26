#!/usr/bin/env python3
import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROADMAP = Path("ROADMAP.md")
START = "### A14 — Walk the build-and-install document end to end on a TV"
END = "### A15 — Truth up the specification documents"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def prepare() -> None:
    text = ROADMAP.read_text()
    if text.count(START) != 1 or text.count(END) != 1:
        raise SystemExit("A14/A15 section markers are not unique")
    prefix, rest = text.split(START, 1)
    block, suffix = rest.split(END, 1)

    block = replace_once(
        block,
        "- **Status:** Open — blocked on device evidence",
        "- **Status:** Partially implemented",
        "A14 status",
    )
    block = replace_once(
        block,
        "  Two related staleness bugs: `.github/workflows/ci.yml:41-42` and `docs/ci.md:36-37` both state the\n  project has no test files, when there are 3 suites and 41 tests, and `--passWithNoTests` would now\n  hide a suite that stopped being discovered.",
        "  The CI test-discovery maintenance is now implemented: the normal test step runs without\n  `--passWithNoTests`, and `docs/ci.md` describes the existing unit and playback-scenario suites. PR\n  CI #212 passed with that fail-closed discovery rule. TV install and launch remain unverified.",
        "A14 concrete evidence",
    )
    block = replace_once(
        block,
        "- **Proposed direction:** Follow `docs/build-and-install.md` on a clean machine through\n  `ares-install` and the smoke test, correcting whatever is wrong. Separately, drop\n  `--passWithNoTests` and fix both stale \"no test files\" claims.",
        "- **Proposed direction:** Follow `docs/build-and-install.md` on a clean machine through\n  `ares-install` and the smoke test, correcting whatever is wrong. The CI test-discovery guard and\n  stale CI documentation cleanup are complete; the television walkthrough is the remaining work.",
        "A14 proposed direction",
    )
    block = replace_once(
        block,
        "- **Confidence:** code — high for the stale claims. device — untested for the install loop.",
        "- **Confidence:** code — high for the CI test-discovery guard. device — untested for the\n  install loop.",
        "A14 confidence",
    )

    ROADMAP.write_text(prefix + START + block + END + suffix)


def request(method: str, path: str, payload=None):
    repo = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GH_TOKEN"]
    url = f"https://api.github.com/repos/{repo}{path}"
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise SystemExit(f"GitHub API {method} {path} failed: {exc.code} {body}") from exc


def ref_path(branch: str, plural: bool = False) -> str:
    family = "refs" if plural else "ref"
    return f"/git/{family}/heads/{urllib.parse.quote(branch, safe='/')}"


def publish() -> None:
    expected = os.environ["EXPECTED_HEAD"]
    branch = os.environ["HEAD_BRANCH"]

    current = request("GET", ref_path(branch))["object"]["sha"]
    if current != expected:
        raise SystemExit(f"head moved before publish: expected {expected}, got {current}")

    commit = request("GET", f"/git/commits/{expected}")
    base_tree = commit["tree"]["sha"]
    roadmap_b64 = base64.b64encode(ROADMAP.read_bytes()).decode()
    roadmap_blob = request("POST", "/git/blobs", {"content": roadmap_b64, "encoding": "base64"})["sha"]

    tree = request(
        "POST",
        "/git/trees",
        {
            "base_tree": base_tree,
            "tree": [
                {"path": "ROADMAP.md", "mode": "100644", "type": "blob", "sha": roadmap_blob},
                {"path": ".github/workflows/a14-roadmap-temp.yml", "mode": "100644", "type": "blob", "sha": None},
                {"path": "scripts/a14-roadmap-temp.py", "mode": "100644", "type": "blob", "sha": None},
            ],
        },
    )["sha"]
    new_commit = request(
        "POST",
        "/git/commits",
        {"message": "docs: reconcile A14 CI test discovery progress", "tree": tree, "parents": [expected]},
    )["sha"]

    current = request("GET", ref_path(branch))["object"]["sha"]
    if current != expected:
        raise SystemExit(f"head moved before ref update: expected {expected}, got {current}")

    request("PATCH", ref_path(branch, plural=True), {"sha": new_commit, "force": False})
    print(f"published cleanup commit {new_commit}")
    print(f"ROADMAP blob {roadmap_blob}")


if __name__ == "__main__":
    mode = os.environ.get("MODE", "prepare")
    if mode == "prepare":
        prepare()
    elif mode == "publish":
        publish()
    else:
        raise SystemExit(f"unknown MODE: {mode}")
