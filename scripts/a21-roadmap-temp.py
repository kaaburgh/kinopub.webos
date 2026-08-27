#!/usr/bin/env python3
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROADMAP = Path("ROADMAP.md")
WORKFLOW_PATH = ".github/workflows/a21-roadmap-temp.yml"
SCRIPT_PATH = "scripts/a21-roadmap-temp.py"
HEADING = "### A21 — Establish the newest known-good hls.js baseline on the LG G5"
NEXT_HEADING = "### A6 — Answer whether the stall watchdog rescues playback"

NEW_BLOCK = r'''### A21 — Establish the newest known-good hls.js baseline on the LG G5

- **Status:** Partially implemented — the repository baseline is restored to hls.js 1.0.10; fresh LG G5 confirmation and the newest-safe-version search remain open
- **Depends on:** None
- **Priority:** Medium
- **Category:** Playback compatibility
- **Origin:** hls.js upgrade PRs #26–#30 and the LG G5 regression observed after #28
- **Problem or opportunity:** The repository had moved above the last hls.js version with positive target-device evidence, while a real title that plays on the pre-upgrade 1.0.10 build wedges on newer hls.js builds. The operational half is now corrected: PR #82 restores exact `hls.js@1.0.10` without reverting the application fixes, diagnostics, recovery logic, or scenario infrastructure accumulated since the upgrade. This is a development-safety baseline, not fresh proof that the current application tree still works on the television.
- **Concrete evidence:** PR #28 upgraded from 1.0.10 to 1.7.0-rc.2 and ran the scenario suite against both versions successfully. PR #30 then captured the device-only regression: playback stopped at 0.2 s with `readyState=1` and `bufferAppendNoProgress`, while the same title played on the commit immediately before the upgrade. PR #27's 1.5.20 experiment also exposed a separate comparison hazard: newer package entry points can resolve to the ESM build with different transmuxer-worker behaviour, so a version test is only meaningful if the actual browser bundle/runtime path is held constant and recorded. The later repository baseline was 1.6.15; PR #82 now pins exact `hls.js@1.0.10` and regenerates the lockfile. Its migration also removes scenario assertions that encoded 1.6-era HLS error/fatality accounting while preserving strict player-level recovery outcomes. Exact-head PR CI #230 on `cad4328045317df00747cf850f9652f0e0eaa461` passed `CI`, `Agentic repository contract`, and `Release drafter`. No fresh LG G5 run has been performed on the restored current tree.
- **Motivation and expected benefit:** Day-to-day development is again based on the last hls.js version with positive historical target-device evidence, while the investigation can continue toward the newest safe release instead of freezing the dependency forever. This keeps future playback changes from being evaluated on top of a library version already implicated in a device regression.
- **Proposed direction:** The operational rollback is implemented. Next, confirm the restored 1.0.10 current tree on the LG G5, then test the newest stable hls.js candidate available at investigation time and sample older stable checkpoints as needed to understand compatibility. Treat every candidate as an independent device result: a bad midpoint does not rule out a later release that may have fixed the regression, so continue testing later releases instead of narrowing a single monotonic first-bad/newest-good boundary. For each candidate, verify the actual bundled hls.js entry point and worker behaviour before comparing results. Use the same LG G5 matrix every time: the known-regressing title from cold start; a normal HLS title; seek into an unbuffered region; Auto and fixed-quality switching; alternate audio selection; and an HDR title. Do not promote a candidate from browser/scenario evidence alone.
- **Dependencies and sequencing:** The repository rollback is complete and should precede unrelated playback-behaviour changes so those changes are evaluated against the historical known-good library baseline. Fresh device confirmation should happen before calling the restored current tree verified. The version search can then run independently, but conclusions in **A6** and **A20** must record which hls.js baseline produced the evidence. **A18** remains useful as a fast pre-device filter, not as the acceptance gate.
- **Compatibility risks:** High if future version work is treated as a mechanical dependency bump. hls.js changed loader deadlines, retry ownership, package entry points and worker behaviour across the range already tested. A candidate can pass every repository test and still fail on webOS MSE/decoder behaviour; conversely, a scenario difference may be an intentional upstream policy change rather than a regression. Keep version-only changes isolated from player-policy changes.
- **Confidence:** runtime/code — high that the 1.0.10 rollback is internally consistent and passes the repository suite/build/ES5 checks; device — high that newer hls.js introduced the previously observed regression, but the restored current 1.0.10 tree has not yet been re-confirmed on the LG G5; unknown which releases above 1.0.10 are safe on the target device.
- **Validation and acceptance criteria:** Repository-side rollback acceptance is met when exact 1.0.10 remains pinned, the complete repository test/scenario suite stays green, and build plus ES5 validation pass; PR #82 provides that cloud/runtime evidence. Device acceptance remains open: restore the known-regressing title on the LG G5 using the current 1.0.10 tree. The investigation ends with a recorded newest-known-good hls.js version that passes the same repository suite plus the complete device matrix above, with the bundled entry point/worker mode recorded. A failed candidate does not terminate testing of later releases. If no tested candidate above 1.0.10 passes, keep 1.0.10 pinned and record the tested candidates and their results rather than weakening the device gate.
- **Estimated scope:** Repository rollback implemented; medium remaining for fresh baseline confirmation and the version search because device passes, not code volume, are the limiting factor.
'''


def prepare():
    text = ROADMAP.read_text()
    start = text.find(HEADING)
    if start < 0:
        raise SystemExit("A21 heading not found")
    end = text.find(NEXT_HEADING, start)
    if end < 0:
        raise SystemExit("A6 heading after A21 not found")
    block = text[start:end].rstrip() + "\n"
    required = [
        "- **Status:** Investigation first — restore the known-good baseline, then search for the newest safe release",
        "- **Problem or opportunity:** `master` currently pins `hls.js@1.7.0-rc.2`",
        "- **Validation and acceptance criteria:** The operational rollback leaves the complete repository",
    ]
    for marker in required:
        if marker not in block:
            raise SystemExit(f"expected A21 marker not found: {marker}")
    updated = text[:start] + NEW_BLOCK + "\n" + text[end:]
    if updated == text:
        raise SystemExit("A21 reconciliation produced no change")
    ROADMAP.write_text(updated)


def api(method, path, payload=None):
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
        raise SystemExit(f"GitHub API {method} {path} failed: {exc.code} {body}")


def ref_sha(branch):
    encoded = urllib.parse.quote(branch, safe="")
    return api("GET", f"/git/ref/heads/{encoded}")["object"]["sha"]


def publish():
    expected = os.environ["EXPECTED_HEAD"]
    branch = os.environ["HEAD_BRANCH"]
    if ref_sha(branch) != expected:
        raise SystemExit("branch head changed before A21 publication")

    commit = api("GET", f"/git/commits/{expected}")
    base_tree = commit["tree"]["sha"]
    roadmap_blob = api("POST", "/git/blobs", {"content": ROADMAP.read_text(), "encoding": "utf-8"})["sha"]
    tree = api(
        "POST",
        "/git/trees",
        {
            "base_tree": base_tree,
            "tree": [
                {"path": "ROADMAP.md", "mode": "100644", "type": "blob", "sha": roadmap_blob},
                {"path": WORKFLOW_PATH, "mode": "100644", "type": "blob", "sha": None},
                {"path": SCRIPT_PATH, "mode": "100644", "type": "blob", "sha": None},
            ],
        },
    )["sha"]
    new_commit = api(
        "POST",
        "/git/commits",
        {"message": "docs: reconcile A21 rollback progress", "tree": tree, "parents": [expected]},
    )["sha"]

    if ref_sha(branch) != expected:
        raise SystemExit("branch head changed before A21 ref update")
    encoded = urllib.parse.quote(branch, safe="")
    api("PATCH", f"/git/refs/heads/{encoded}", {"sha": new_commit, "force": False})
    print(new_commit)


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"prepare", "publish"}:
        raise SystemExit("usage: a21-roadmap-temp.py prepare|publish")
    {"prepare": prepare, "publish": publish}[sys.argv[1]]()
