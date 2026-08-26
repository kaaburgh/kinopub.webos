#!/usr/bin/env python3
import json
import os
import pathlib
import urllib.error
import urllib.request

ROADMAP = pathlib.Path('ROADMAP.md')
START = '### A19 — Move the Sentry DSN out of the source and rotate it\n'
END = '### A12 — Reproduce and isolate subtitle brightness, including whether HDR is involved\n'

NEW_SECTION = '''### A19 — Move the Sentry DSN out of the source and rotate it

- **Status:** Partially implemented — source/config relocation shipped; external DSN rotation remains
- **Depends on:** None
- **Priority:** Low
- **Category:** Configuration / privacy
- **Origin:** **A4**, deferred deliberately by the repository owner
- **Problem or opportunity:** The Sentry DSN was a literal in tracked source, in a public repository,
  and was additionally served in a public bundle for as long as the GitHub Pages deployment was live.
  A DSN is an ingest endpoint, not a credential — the practical exposure is unwanted event ingestion
  and quota consumption — so this remains Low priority. The repository-side inheritance problem is now
  fixed; the already-exposed DSN still needs to be rotated in Sentry.
- **Concrete evidence:** `src/utils/logging.ts` now reads `process.env.REACT_APP_SENTRY_DSN` instead of
  embedding the DSN literal. `src/utils/enviroment.ts` exposes a tested `shouldInitSentry` gate: browser
  runtimes remain silent, and packaged runtimes without a configured DSN deliberately skip
  `Sentry.init`. Focused unit coverage checks configured packaged runtime, browser runtime, missing DSN,
  and an empty DSN. The current DSN value is retained in tracked `.env` for this bounded relocation,
  so repository behaviour does not silently change before the external rotation step.
- **Motivation and expected benefit:** Build-time configuration prevents future forks or builds from
  inheriting a source literal and makes silent no-DSN builds intentional. Rotating the existing Sentry
  DSN separately invalidates the already-public ingest endpoint without conflating repository code with
  an external project-configuration change.
- **Implemented direction:** Use `REACT_APP_SENTRY_DSN` at build time and initialise Sentry only when a
  packaged runtime has a non-empty configured value. Preserve the existing A18 browser-runtime gate.
  Keep the current value in tracked `.env` until the external rotation is performed, then update that
  configured value as a separate evidence-bearing step.
- **Dependencies and sequencing:** None. The repository-side change is complete. External Sentry DSN
  rotation is the remaining step and cannot be performed or inferred from a GitHub code change.
- **Compatibility risks:** Low. `react-scripts` injects the value at build time; missing configuration
  now intentionally produces a silent packaged runtime rather than a broken build. Browser sessions
  remain silent regardless of configuration.
- **Confidence:** code/runtime — high for the build-time gate and focused unit coverage; external Sentry
  rotation — not performed.
- **Validation and acceptance criteria:** Exact-head CI on implementation head
  `0706c638a047e7e1fb7c47609db30e4a7c54b3f4` passed `CI`, `Agentic repository contract`, and
  `Release drafter`; focused tests cover the Sentry-initialisation gate. Repository acceptance is met
  for source/config relocation. A19 remains incomplete until the old DSN is rotated in Sentry and the
  configured value is updated; no repository evidence may claim that external rotation has happened.
- **Estimated scope:** Repository work complete; one small external configuration step remains.

'''

def prepare():
    text = ROADMAP.read_text()
    if text.count(START) != 1 or text.count(END) != 1:
        raise SystemExit('expected exactly one A19 section boundary')
    start = text.index(START)
    end = text.index(END, start)
    old = text[start:end]
    required = [
        '- **Status:** Open',
        '`src/utils/logging.ts:16` holds the value inline',
        'Read it from `process.env.REACT_APP_SENTRY_DSN`',
        'Then rotate the key in Sentry and update the',
    ]
    for needle in required:
        if needle not in old:
            raise SystemExit(f'A19 guard missing: {needle}')
    ROADMAP.write_text(text[:start] + NEW_SECTION + text[end:])


def request(method, path, payload=None):
    repo = os.environ['GITHUB_REPOSITORY']
    token = os.environ['GH_TOKEN']
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        f'https://api.github.com/repos/{repo}{path}', data=data, method=method,
        headers={
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'Content-Type': 'application/json',
        })
    with urllib.request.urlopen(req) as response:
        return json.load(response)


def ref_sha(branch):
    return request('GET', f'/git/ref/heads/{branch}')['object']['sha']


def publish():
    expected = os.environ['EXPECTED_HEAD']
    branch = os.environ['HEAD_BRANCH']
    if ref_sha(branch) != expected:
        raise SystemExit('branch moved before A19 reconciliation publish')

    roadmap_bytes = ROADMAP.read_bytes()
    import base64
    roadmap_blob = request('POST', '/git/blobs', {
        'content': base64.b64encode(roadmap_bytes).decode(), 'encoding': 'base64'
    })['sha']

    commit = request('GET', f'/git/commits/{expected}')
    base_tree = commit['tree']['sha']
    tree = request('POST', '/git/trees', {
        'base_tree': base_tree,
        'tree': [
            {'path': 'ROADMAP.md', 'mode': '100644', 'type': 'blob', 'sha': roadmap_blob},
            {'path': '.github/workflows/a19-roadmap-temp.yml', 'mode': '100644', 'type': 'blob', 'sha': None},
            {'path': 'scripts/a19-roadmap-temp.py', 'mode': '100644', 'type': 'blob', 'sha': None},
        ],
    })['sha']
    new_commit = request('POST', '/git/commits', {
        'message': 'docs: reconcile A19 Sentry configuration progress',
        'tree': tree,
        'parents': [expected],
    })['sha']

    if ref_sha(branch) != expected:
        raise SystemExit('branch moved before A19 reconciliation ref update')
    request('PATCH', f'/git/refs/heads/{branch}', {'sha': new_commit, 'force': False})
    print(f'published={new_commit}')
    print(f'roadmap_blob={roadmap_blob}')


if __name__ == '__main__':
    import sys
    if sys.argv[1:] == ['prepare']:
        prepare()
    elif sys.argv[1:] == ['publish']:
        publish()
    else:
        raise SystemExit('usage: script prepare|publish')
