#!/usr/bin/env python3
import base64
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROADMAP = Path("ROADMAP.md")

REPLACEMENTS = [
    (
        """- **Status:** Partially implemented — scripted scenarios, the browser Sentry gate, and the first four
  local browser procedures (refused segment, non-fatal stall, unbuffered seek, and bandwidth collapse) exist; the remaining browser scenario does not""",
        """- **Status:** Implemented, validation incomplete — scripted scenarios, the browser Sentry gate, and all five
  local browser procedures (refused segment, non-fatal stall, unbuffered seek, bandwidth collapse, and teardown) exist; real-backend browser validation remains open""",
    ),
    (
        """> What remains open is the teardown-path browser case below.
> The previous plan to use that browser harness to prove **A2** Sentry delivery is no longer valid:""",
        """> **The fifth browser procedure now exists, also without runtime evidence.**
> `docs/browser-scenarios/teardown.js` keeps matching media-fragment requests pending behind the same
> explicit CDN-host and mandatory non-secret fragment-path discriminator until the existing terminal
> failure notice appears. It then sends one Escape/Back through the application's normal key path and
> accepts success only when the route leaves the player and the `<video>` element is unmounted. The
> companion Markdown procedure records setup, cleanup, privacy, and the browser-vs-TV evidence
> boundary. This GitHub-only agent environment has not executed it against the real backend/CDN, so
> reproducibility remains unestablished.
>
> All planned browser procedures now exist; what remains open is executing them reproducibly against
> the real backend/CDN. The previous plan to use that browser harness to prove **A2** Sentry delivery is no longer valid:""",
    ),
    (
        """  `docs/browser-scenarios/nonfatal-stall.js` plus its companion Markdown file define the second local
  procedure, `docs/browser-scenarios/unbuffered-seek.js` plus its companion Markdown file define the
  third, and `docs/browser-scenarios/bandwidth-collapse.js` plus its companion Markdown file define
  the fourth. The request-targeting procedures preserve the mandatory fail-closed fragment
  discriminator and all four preserve the privacy boundary; none of the real-backend/CDN runs has
  yet been executed.""",
        """  `docs/browser-scenarios/nonfatal-stall.js` plus its companion Markdown file define the second local
  procedure, `docs/browser-scenarios/unbuffered-seek.js` plus its companion Markdown file define the
  third, `docs/browser-scenarios/bandwidth-collapse.js` plus its companion Markdown file define the
  fourth, and `docs/browser-scenarios/teardown.js` plus its companion Markdown file define the fifth.
  The request-targeting procedures preserve the mandatory fail-closed fragment discriminator and all
  five preserve the privacy boundary; none of the real-backend/CDN runs has yet been executed.""",
    ),
    (
        """  - a stall followed by leaving the player, to exercise the application-side teardown path; actual
    Sentry delivery remains under **A2** because browser Sentry is deliberately disabled.""",
        """  - a stall followed by leaving the player — the documented procedure now exists; once executed
    reproducibly it should exercise the application-side teardown path through normal Back handling,
    route change, and video unmount. Actual Sentry delivery remains under **A2** because browser
    Sentry is deliberately disabled.""",
    ),
    (
        """  for a reason and this must not quietly restore it. The browser Sentry gate and the first four
  procedures are now in place. Execute those procedures before claiming they are reproducible; then
  add one small Playwright script for the remaining teardown scenario. Keep the scripts beside `docs/` as documented procedures, not as CI jobs —""",
        """  for a reason and this must not quietly restore it. The browser Sentry gate and all five planned
  procedures are now in place. Execute those procedures before claiming they are reproducible. Keep
  the scripts beside `docs/` as documented procedures, not as CI jobs —""",
    ),
    (
        """- **Confidence:** code — high for the browser classification, Sentry wiring, and all four procedures'
  evidence/privacy rules; runtime — focused tests cover HTTP/HTTPS versus packaged-file
  classification. None of the real-network browser procedures has been run, so their runtime
  reproducibility is unknown; all LG-device behaviour remains device evidence only.""",
        """- **Confidence:** code — high for the browser classification, Sentry wiring, and all five procedures'
  evidence/privacy rules; runtime — focused tests cover HTTP/HTTPS versus packaged-file
  classification. None of the real-network browser procedures has been run, so their runtime
  reproducibility is unknown; all LG-device behaviour remains device evidence only.""",
    ),
    (
        """  lower `currentLevel` followed by observable playback progression after that downshift. The shaped
  throughput is an input to the experiment, not a measured threshold. A scenario that only works
  sometimes is not finished.""",
        """  lower `currentLevel` followed by observable playback progression after that downshift. The shaped
  throughput is an input to the experiment, not a measured threshold. For teardown, at least one
  matching media-fragment request must be held until the terminal failure notice appears; success
  then requires normal Back handling to leave the player route and unmount the `<video>` element.
  Actual Sentry delivery remains device evidence under **A2**. A scenario that only works sometimes
  is not finished.""",
    ),
    (
        """- **Estimated scope:** Medium. Small for the remaining teardown scenario now that the Sentry gate and
  first four procedures exist.""",
        """- **Estimated scope:** Medium. Procedure implementation is complete; real-backend browser validation remains.""",
    ),
]


def prepare():
    text = ROADMAP.read_text()
    start = text.index("### A18 — A web build for reproducing playback problems, with scripted scenarios")
    end = text.index("\n### A20 —", start)
    before, section, after = text[:start], text[start:end], text[end:]
    for old, new in REPLACEMENTS:
        count = section.count(old)
        if count != 1:
            raise SystemExit(f"expected exactly one A18 replacement match, found {count}")
        section = section.replace(old, new, 1)
    ROADMAP.write_text(before + section + after)


def api(method, path, payload=None):
    repo = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GH_TOKEN"]
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}{path}",
        data=data,
        headers={"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}", "X-GitHub-Api-Version": "2022-11-28"},
        method=method,
    )
    with urllib.request.urlopen(req) as response:
        return json.load(response)


def publish():
    expected = os.environ["EXPECTED_HEAD"]
    branch = os.environ["HEAD_REF"]
    original_ci_blob = os.environ["ORIGINAL_CI_BLOB"]
    encoded_branch = urllib.parse.quote(branch, safe="")
    ref_path = f"/git/ref/heads/{encoded_branch}"
    ref = api("GET", ref_path)
    if ref["object"]["sha"] != expected:
        raise SystemExit(f"branch moved before reconciliation: expected {expected}, found {ref['object']['sha']}")
    head_commit = api("GET", f"/git/commits/{expected}")
    base_tree = head_commit["tree"]["sha"]
    roadmap_blob = api("POST", "/git/blobs", {"content": base64.b64encode(ROADMAP.read_bytes()).decode("ascii"), "encoding": "base64"})["sha"]
    tree = api("POST", "/git/trees", {"base_tree": base_tree, "tree": [
        {"path": "ROADMAP.md", "mode": "100644", "type": "blob", "sha": roadmap_blob},
        {"path": ".github/workflows/ci.yml", "mode": "100644", "type": "blob", "sha": original_ci_blob},
        {"path": "scripts/a18-roadmap-reconcile-temp.py", "mode": "100644", "type": "blob", "sha": None},
    ]})["sha"]
    commit = api("POST", "/git/commits", {"message": "docs: reconcile A18 teardown progress", "tree": tree, "parents": [expected]})["sha"]
    ref = api("GET", ref_path)
    if ref["object"]["sha"] != expected:
        raise SystemExit(f"branch moved before ref update: expected {expected}, found {ref['object']['sha']}")
    api("PATCH", f"/git/refs/heads/{encoded_branch}", {"sha": commit, "force": False})
    print(f"A18_RECONCILIATION_HEAD={commit}")
    print(f"A18_ROADMAP_BLOB={roadmap_blob}")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"prepare", "publish"}:
        raise SystemExit("usage: a18-roadmap-reconcile-temp.py prepare|publish")
    prepare() if sys.argv[1] == "prepare" else publish()
