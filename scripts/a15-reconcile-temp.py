#!/usr/bin/env python3
import base64
import json
import os
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

REPO = os.environ['GITHUB_REPOSITORY']
TOKEN = os.environ['GITHUB_TOKEN']
BRANCH = os.environ['GITHUB_HEAD_REF']
EVENT = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
EXPECTED_HEAD = EVENT['pull_request']['head']['sha']
API = f"https://api.github.com/repos/{REPO}"


def request(method, path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={
            'Authorization': f'Bearer {TOKEN}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'kinopub-a15-reconcile',
            'Content-Type': 'application/json',
        },
    )
    with urllib.request.urlopen(req) as response:
        return json.load(response)


def replace_exact(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected exactly one match, found {count}')
    return text.replace(old, new, 1)


ref_path = '/git/ref/heads/' + urllib.parse.quote(BRANCH, safe='')
current = request('GET', ref_path)['object']['sha']
if current != EXPECTED_HEAD:
    raise RuntimeError(f'head moved before reconciliation: expected {EXPECTED_HEAD}, got {current}')

spec_path = Path('docs/playback-diagnostics-spec.md')
spec = spec_path.read_text()

spec = replace_exact(
    spec,
    """The overlay can serialize its current state into a QR code so a report can leave the TV without a\nnetwork round trip. That constraint drives the whole\ndesign: the failure under investigation is a network stall, so any transport that uploads from the\napp is unavailable exactly when the capture matters. Scanning with a phone works regardless.\n\nSending to the Sentry DSN already present in `src/utils/logging.ts` is not an option either — it\nbelongs to the upstream project, so the data would go to a third party and stay invisible to whoever\nis debugging this fork.\n""",
    """The overlay can serialize its current state into a QR code so a report can leave the TV without a\nnetwork round trip. The failure under investigation is a network stall, so any transport that uploads\nfrom the app can be unavailable exactly when the capture matters. Scanning with a phone works\nregardless.\n\nSentry complements rather than replaces this path: it can report while connectivity still works,\nbut the QR export remains locally retrievable when the failing condition is the network itself.\n""",
    'capture-export rationale',
)

spec = replace_exact(
    spec,
    """Reported conditions, all of them states the player could not resolve on its own:\n\n- `fatal-network-recovery-exhausted`\n- `fatal-media-recovery-exhausted`\n- `fatal-unrecoverable`\n- `stall-watchdog-exhausted`\n- persistent non-fatal playback wedge (episode trigger `persistent-wedge`)\n- `decode-health-severe`\n""",
    """Failures the player tries to recover from are reported as recovery episodes rather than as\nstandalone playback issues. Episode triggers cover fatal recovery, watchdog recovery, and persistent\nnon-fatal wedges; one event is emitted when the episode concludes as recovered or abandoned. The\nonly standalone playback issue is `decode-health-severe`, which is deliberately not an episode.\n""",
    'error-reporting model',
)

spec = replace_exact(
    spec,
    """Two rules keep this useful:\n\n- **One report per issue per playback session.** The failure this project has been chasing produces\n  a few hundred errors a minute; reporting each would bury the signal and burn the quota in one\n  evening. The interesting fact is that a session hit a wall, not how many times it bounced off it.\n  The guard resets when a new source loads.\n- **Hostnames only.** Stream URLs carry access tokens and appear in messages, breadcrumbs and\n""",
    """Two rules keep this useful:\n\n- **Bound repeated reports at the right scope.** Standalone playback issues are reported once per\n  playback session, API failures once per endpoint/kind/session, and recoverable playback failures\n  once per recovery episode. The failure this project has been chasing can produce a few hundred\n  errors a minute; reporting each would bury the signal and burn the quota in one evening.\n- **Hostnames only.** Stream URLs carry access tokens and appear in messages, breadcrumbs and\n""",
    'report-volume rule',
)

spec_path.write_text(spec)

roadmap_path = Path('ROADMAP.md')
roadmap = roadmap_path.read_text()
roadmap = replace_exact(
    roadmap,
    """### A15 — Truth up the specification documents\n\n- **Status:** Open\n""",
    """### A15 — Truth up the specification documents\n\n- **Status:** Completed, validation incomplete\n""",
    'A15 status',
)
roadmap = replace_exact(
    roadmap,
    """- **Proposed direction:** Replace the five-item list with the episode model plus the one standalone\n  issue; rewrite the QR rationale to say the export exists because the _network_ is what fails during\n  a stall — which is still true and is the stronger argument — rather than because the DSN belongs to\n  someone else. Sweep for other statements the recent commits invalidated while there.\n- **Dependencies and sequencing:** None. Should follow **A4**, whose decisions the spec should record.\n""",
    """- **Implemented direction:** Replaced the stale standalone-condition list with the recovery-episode\n  model plus `decode-health-severe`, rewrote the QR rationale around network independence rather than\n  the obsolete upstream-DSN premise, and corrected the adjacent report-volume rule so it distinguishes\n  session-scoped standalone issues, endpoint-scoped API failures, and recovery episodes.\n- **Dependencies and sequencing:** None. Followed **A4**, whose telemetry decisions the spec now records.\n""",
    'A15 direction',
)
roadmap_path.write_text(roadmap)

subprocess.run(['yarn', 'prettier', 'docs/playback-diagnostics-spec.md', 'ROADMAP.md', '--write'], check=True)
subprocess.run(['yarn', 'format:check'], check=True)
subprocess.run(['yarn', 'check:docs'], check=True)
subprocess.run(['git', 'diff', '--check'], check=True)


def create_blob(path):
    content = base64.b64encode(Path(path).read_bytes()).decode()
    return request('POST', '/git/blobs', {'content': content, 'encoding': 'base64'})['sha']

spec_blob = create_blob('docs/playback-diagnostics-spec.md')
roadmap_blob = create_blob('ROADMAP.md')
base_tree = request('GET', f'/git/commits/{EXPECTED_HEAD}')['tree']['sha']

tree = request('POST', '/git/trees', {
    'base_tree': base_tree,
    'tree': [
        {'path': 'docs/playback-diagnostics-spec.md', 'mode': '100644', 'type': 'blob', 'sha': spec_blob},
        {'path': 'ROADMAP.md', 'mode': '100644', 'type': 'blob', 'sha': roadmap_blob},
        {'path': '.github/workflows/a15-reconcile-temp.yml', 'mode': '100644', 'type': 'blob', 'sha': None},
        {'path': 'scripts/a15-reconcile-temp.py', 'mode': '100755', 'type': 'blob', 'sha': None},
    ],
})['sha']

commit = request('POST', '/git/commits', {
    'message': 'docs: truth up playback diagnostics specification',
    'tree': tree,
    'parents': [EXPECTED_HEAD],
})['sha']

current = request('GET', ref_path)['object']['sha']
if current != EXPECTED_HEAD:
    raise RuntimeError(f'head moved before publish: expected {EXPECTED_HEAD}, got {current}')

request('PATCH', ref_path, {'sha': commit, 'force': False})
print(f'published reconciliation commit {commit}')
print(f'ROADMAP blob {roadmap_blob}')
print(f'spec blob {spec_blob}')
