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
        """- **Status:** Partially implemented — scripted scenarios, the browser Sentry gate, and the first local
  refused-segment browser procedure exist; the remaining browser scenarios do not""",
        """- **Status:** Partially implemented — scripted scenarios, the browser Sentry gate, and the first two
  local browser procedures (refused segment and non-fatal stall) exist; the remaining browser scenarios do not""",
    ),
    (
        """> What remains open is the rest of the browser harness: a non-fatal stall, a seek into an unbuffered
> region against the real CDN, bandwidth collapse driving real ABR, and the teardown-path case below.""",
        """> **The second browser procedure now exists, also without runtime evidence.**
> `docs/browser-scenarios/nonfatal-stall.js` keeps requests pending at Playwright's routing boundary
> only when the same explicit CDN-host and mandatory non-secret media-fragment path discriminator
> match. It opens the existing diagnostics before arming and counts a run as non-fatal-stall evidence
> only when watchdog restart/reload progression is visible and fatal recovery does not become causal
> before the terminal notice. The companion Markdown procedure records setup, cleanup, privacy, and
> the browser-vs-TV evidence boundary. This GitHub-only agent environment has not executed it against
> the real backend/CDN, so reproducibility remains unestablished.
>
> What remains open is the rest of the browser harness: a seek into an unbuffered region against the
> real CDN, bandwidth collapse driving real ABR, and the teardown-path case below.""",
    ),
    (
        """  `docs/browser-scenarios/refused-segment.js` and its README now define the first local browser
  procedure, including the mandatory fail-closed fragment discriminator and the privacy boundary;
  the real-backend/CDN run has not yet been executed.""",
        """  `docs/browser-scenarios/refused-segment.js` plus its README define the refused-segment procedure,
  and `docs/browser-scenarios/nonfatal-stall.js` plus its companion Markdown file define the second
  local procedure. Both require the mandatory fail-closed fragment discriminator and preserve the
  privacy boundary; neither real-backend/CDN run has yet been executed.""",
    ),
    (
        """  - a non-fatal stall — block segments without letting hls.js escalate, and confirm the watchdog's
    restart/reload escalation and then the notice;""",
        """  - a non-fatal stall — the documented procedure now exists; once executed reproducibly it should
    confirm the watchdog's restart/reload escalation and then the notice without fatal recovery
    becoming causal first;""",
    ),
    (
        """  for a reason and this must not quietly restore it. The browser Sentry gate and the first
  refused-segment procedure are now in place. Execute that procedure before claiming it is
  reproducible; then add one small Playwright script per remaining scenario, driving the app with
  request interception.""",
        """  for a reason and this must not quietly restore it. The browser Sentry gate and the first two
  procedures are now in place. Execute those procedures before claiming they are reproducible; then
  add one small Playwright script per remaining scenario, driving the app with request interception.""",
    ),
    (
        """- **Confidence:** code — high for the browser classification, Sentry wiring, and the first procedure's
  fail-closed request selection/privacy rules; runtime — focused tests cover HTTP/HTTPS versus
  packaged-file classification. The refused-segment real-network procedure itself has not been run,
  so its runtime reproducibility is unknown; all LG-device behaviour remains device evidence only.""",
        """- **Confidence:** code — high for the browser classification, Sentry wiring, and both procedures'
  fail-closed request selection/privacy rules; runtime — focused tests cover HTTP/HTTPS versus
  packaged-file classification. Neither real-network browser procedure has been run, so their runtime
  reproducibility is unknown; all LG-device behaviour remains device evidence only.""",
    ),
    (
        """  evidence is valid only when the configured non-secret discriminator uniquely selects media
  fragments rather than keys/subtitles/other CDN requests. A scenario that only works sometimes is
  not finished. The browser gate itself is covered by focused runtime classification tests; actual""",
        """  evidence is valid only when the configured non-secret discriminator uniquely selects media
  fragments rather than keys/subtitles/other CDN requests. For the non-fatal-stall case, diagnostics
  must show watchdog restart/reload progression without fatal recovery becoming causal before the
  terminal notice. A scenario that only works sometimes is not finished. The browser gate itself is
  covered by focused runtime classification tests; actual""",
    ),
    (
        """- **Estimated scope:** Medium. Small per remaining scenario now that the Sentry gate and first
  procedure exist.""",
        """- **Estimated scope:** Medium. Small per remaining scenario now that the Sentry gate and first two
  procedures exist.""",
    ),
]


def prepare():
    text = ROADMAP.read_text()
    for old, new in REPLACEMENTS:
        count = text.count(old)
        if count != 1:
            raise SystemExit(f"expected exactly one A18 replacement match, found {count}")
        text = text.replace(old, new, 1)
    ROADMAP.write_text(text)


def api(method, path, payload=None):
    repo = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GH_TOKEN"]
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}{path}",
        data=data,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
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
        raise SystemExit(
            f"branch moved before reconciliation: expected {expected}, found {ref['object']['sha']}"
        )

    head_commit = api("GET", f"/git/commits/{expected}")
    base_tree = head_commit["tree"]["sha"]

    roadmap_content = base64.b64encode(ROADMAP.read_bytes()).decode("ascii")
    roadmap_blob = api(
        "POST",
        "/git/blobs",
        {"content": roadmap_content, "encoding": "base64"},
    )["sha"]

    tree = api(
        "POST",
        "/git/trees",
        {
            "base_tree": base_tree,
            "tree": [
                {
                    "path": "ROADMAP.md",
                    "mode": "100644",
                    "type": "blob",
                    "sha": roadmap_blob,
                },
                {
                    "path": ".github/workflows/ci.yml",
                    "mode": "100644",
                    "type": "blob",
                    "sha": original_ci_blob,
                },
                {
                    "path": "scripts/a18-roadmap-reconcile-temp.py",
                    "mode": "100644",
                    "type": "blob",
                    "sha": None,
                },
            ],
        },
    )["sha"]

    commit = api(
        "POST",
        "/git/commits",
        {
            "message": "docs: reconcile A18 non-fatal stall progress",
            "tree": tree,
            "parents": [expected],
        },
    )["sha"]

    ref = api("GET", ref_path)
    if ref["object"]["sha"] != expected:
        raise SystemExit(
            f"branch moved before ref update: expected {expected}, found {ref['object']['sha']}"
        )

    api(
        "PATCH",
        f"/git/refs/heads/{encoded_branch}",
        {"sha": commit, "force": False},
    )
    print(f"A18_RECONCILIATION_HEAD={commit}")
    print(f"A18_ROADMAP_BLOB={roadmap_blob}")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"prepare", "publish"}:
        raise SystemExit("usage: a18-roadmap-reconcile-temp.py prepare|publish")
    if sys.argv[1] == "prepare":
        prepare()
    else:
        publish()
