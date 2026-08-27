#!/usr/bin/env python3
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROADMAP = Path("ROADMAP.md")
WORKFLOW_PATH = ".github/workflows/a13-roadmap-temp.yml"
SCRIPT_PATH = "scripts/a13-roadmap-temp.py"
HEADING = "### A13 — Quality-selection follow-ups: decode-driven reduction, and ABR levels as fixed choices"
NEXT_HEADING = "### A14 — Walk the build-and-install document end to end on a TV"

NEW_BLOCK = r'''### A13 — Quality-selection follow-ups: decode-driven reduction, and ABR levels as fixed choices

- **Status:** Partially implemented — manifest HLS levels are available as fixed choices; decode-driven reduction remains blocked on **A5**
- **Depends on:** A5
- **Priority:** Low
- **Category:** Playback quality
- **Origin:** The live remainders of items 3 and 4, consolidated
- **Problem or opportunity:** Two related open ends were tracked here. (a) Automatic quality reduction when the _decoder_ struggles remains deliberately unbuilt because it would act on an unvalidated signal. (b) The independent fixed-choice gap is now implemented: a genuine multi-level master playlist exposes every manifest rendition as a deterministic fixed quality choice in addition to Auto and the API-derived choices.
- **Concrete evidence:** Item 4's narrowing paragraph still defines the evidence gate for (a). For (b), PR #84 adds pure HLS-level choice helpers and integrates them into `media.new.tsx`: every manifest level gets a deterministic UI choice, selecting one pins `hls.nextLevel` without replacing the source URL, and recovery restores the chosen rendition by metadata rather than by its previous manifest index. Duplicate metadata fingerprints fail closed rather than silently choosing a colliding rendition. Regression coverage includes equal-resolution levels, manifest reorder, and duplicate-fingerprint ambiguity. Exact-head CI on implementation head `db8da61042eb313761c477cf48cffac916cdb4e5` passed `CI`, `Agentic repository contract`, and `Release drafter`; owner review on that same head found no new blockers. No LG-device behaviour is inferred from that cloud/runtime evidence.
- **Motivation and expected benefit:** (a) would let the app respond to a decoder problem instead of only reporting it. (b) closes the quality-selection completeness gap and gives diagnostics/testing a direct way to pin a rendition that exists only inside the master manifest.
- **Proposed direction:** Keep (b) as implemented and do not broaden it into decode policy. Do not start (a) until **A5** says what a real decode problem looks like on this panel. When it does: reduce one level at a time via `nextLevel` (never `currentLevel` — see **A7**), with hysteresis and a cooldown, never silently overriding a deliberate manual choice, and showing the reason in diagnostics. Item 4's original bullet list still describes the shape wanted.
- **Dependencies and sequencing:** (a) remains strictly after **A5** and benefits from **A7** landing first. The implemented fixed-choice substep (b) is independent of A5 and should not be treated as evidence that decode-driven fallback is ready.
- **Compatibility risks:** High for (a) relative to its value — this is the one item that changes what the player does to a stream that is currently playing. For implemented (b), fixed choices preserve the established `nextLevel` semantics; rebuild recovery uses a rendition fingerprint only when it uniquely identifies one level and otherwise fails closed, avoiding a silent switch to a different colliding rendition.
- **Confidence:** code/runtime — high for implemented (b), with focused regression coverage and green repository CI; device — not established for the new fixed choices. The premise of (a) remains assumed and is precisely what **A5** exists to test.
- **Validation and acceptance criteria:** For implemented (b), repository acceptance is met when every manifest level is represented by a separately selectable fixed choice, selection is reflected through the fixed HLS path, reorder recovery preserves a uniquely identifiable rendition, duplicate fingerprints fail closed, and the quality-selection tests plus repository CI stay green; PR #84 provides that cloud/runtime evidence. LG-device validation remains unclaimed. For (a): a decode problem reproduced on the TV, a single reduction observed, no oscillation over 10 minutes, and the reason visible in diagnostics.
- **Estimated scope:** Small fixed-choice substep implemented; medium decode-driven substep remains blocked on device evidence.
'''


def prepare():
    text = ROADMAP.read_text()
    start = text.find(HEADING)
    if start < 0:
        raise SystemExit("A13 heading not found")
    end = text.find(NEXT_HEADING, start)
    if end < 0:
        raise SystemExit("A14 heading after A13 not found")
    block = text[start:end].rstrip() + "\n"
    required = [
        "- **Status:** Open — blocked on **A5**",
        "  (b) A master playlist's internal ABR levels are not offered as separate fixed choices",
        "  (b) is independent and small.",
        "  each manifest level selectable and reflected in `currentLevel`.",
    ]
    for marker in required:
        if marker not in block:
            raise SystemExit(f"expected A13 marker not found: {marker}")
    updated = text[:start] + NEW_BLOCK + "\n" + text[end:]
    if updated == text:
        raise SystemExit("A13 reconciliation produced no change")
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
        raise SystemExit("branch head changed before A13 roadmap publication")

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
        {"message": "docs: reconcile A13 fixed-level progress", "tree": tree, "parents": [expected]},
    )["sha"]

    if ref_sha(branch) != expected:
        raise SystemExit("branch head changed before A13 roadmap ref update")
    encoded = urllib.parse.quote(branch, safe="")
    api("PATCH", f"/git/refs/heads/{encoded}", {"sha": new_commit, "force": False})
    print(new_commit)


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"prepare", "publish"}:
        raise SystemExit("usage: a13-roadmap-temp.py prepare|publish")
    {"prepare": prepare, "publish": publish}[sys.argv[1]]()
