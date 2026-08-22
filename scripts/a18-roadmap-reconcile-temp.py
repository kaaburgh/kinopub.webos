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
        """- **Status:** Partially implemented — scripted scenarios, the browser Sentry gate, and the first three
  local browser procedures (refused segment, non-fatal stall, and unbuffered seek) exist; the remaining browser scenarios do not""",
        """- **Status:** Partially implemented — scripted scenarios, the browser Sentry gate, and the first four
  local browser procedures (refused segment, non-fatal stall, unbuffered seek, and bandwidth collapse) exist; the remaining browser scenario does not""",
    ),
    (
        """> What remains open is the rest of the browser harness: bandwidth collapse driving real ABR and the
> teardown-path case below.""",
        """> **The fourth browser procedure now exists, also without runtime evidence.**
> `docs/browser-scenarios/bandwidth-collapse.js` keeps a genuine multi-level HLS stream in Auto mode
> and uses Chromium DevTools Protocol network emulation to shape the browser network path without
> manufacturing hls.js events, level state, or responses. A run is accepted only when diagnostics
> show a lower `currentLevel` and the video then advances by at least the configured progress window
> after that first observed downshift. The configured throughput is synthetic and is not a measured
> connection threshold. The companion Markdown procedure records setup, cleanup, privacy, and the
> browser-vs-TV evidence boundary. This GitHub-only agent environment has not executed it against the
> real backend/CDN, so reproducibility remains unestablished.
>
> What remains open is the teardown-path browser case below.""",
    ),
    (
        """  `docs/browser-scenarios/nonfatal-stall.js` plus its companion Markdown file define the second local
  procedure, and `docs/browser-scenarios/unbuffered-seek.js` plus its companion Markdown file define
  the third. All three require the mandatory fail-closed fragment discriminator and preserve the
  privacy boundary; none of the real-backend/CDN runs has yet been executed.""",
        """  `docs/browser-scenarios/nonfatal-stall.js` plus its companion Markdown file define the second local
  procedure, `docs/browser-scenarios/unbuffered-seek.js` plus its companion Markdown file define the
  third, and `docs/browser-scenarios/bandwidth-collapse.js` plus its companion Markdown file define
  the fourth. The request-targeting procedures preserve the mandatory fail-closed fragment
  discriminator and all four preserve the privacy boundary; none of the real-backend/CDN runs has
  yet been executed.""",
    ),
    (
        """  - bandwidth collapse, to watch ABR move quality on its own;""",
        """  - bandwidth collapse — the documented procedure now exists; once executed reproducibly it should
    show a lower HLS level followed by continued playback progress under a synthetically shaped
    Chromium network path;""",
    ),
    (
        """  for a reason and this must not quietly restore it. The browser Sentry gate and the first three
  procedures are now in place. Execute those procedures before claiming they are reproducible; then
  add one small Playwright script per remaining scenario, driving the app with request interception.""",
        """  for a reason and this must not quietly restore it. The browser Sentry gate and the first four
  procedures are now in place. Execute those procedures before claiming they are reproducible; then
  add one small Playwright script for the remaining teardown scenario.""",
    ),
    (
        """- **Confidence:** code — high for the browser classification, Sentry wiring, and all three procedures'
  fail-closed request selection/privacy rules; runtime — focused tests cover HTTP/HTTPS versus
  packaged-file classification. None of the real-network browser procedures has been run, so their
  runtime reproducibility is unknown; all LG-device behaviour remains device evidence only.""",
        """- **Confidence:** code — high for the browser classification, Sentry wiring, and all four procedures'
  evidence/privacy rules; runtime — focused tests cover HTTP/HTTPS versus packaged-file
  classification. None of the real-network browser procedures has been run, so their runtime
  reproducibility is unknown; all LG-device behaviour remains device evidence only.""",
    ),
    (
        """  ranges, a matching media-fragment request must be observed after the seek, and `resumed` is valid
  only after observable playback progression beyond the reached seek target. A scenario that only
  works sometimes is not finished.""",
        """  ranges, a matching media-fragment request must be observed after the seek, and `resumed` is valid
  only after observable playback progression beyond the reached seek target. For bandwidth collapse,
  diagnostics must start in Auto mode with multiple levels and a level above zero; success requires a
  lower `currentLevel` followed by observable playback progression after that downshift. The shaped
  throughput is an input to the experiment, not a measured threshold. A scenario that only works
  sometimes is not finished.""",
    ),
    (
        """- **Estimated scope:** Medium. Small per remaining scenario now that the Sentry gate and first three
  procedures exist.""",
        """- **Estimated scope:** Medium. Small for the remaining teardown scenario now that the Sentry gate and
  first four procedures exist.""",
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
    commit = api("POST", "/git/commits", {"message": "docs: reconcile A18 bandwidth-collapse progress", "tree": tree, "parents": [expected]})["sha"]
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
