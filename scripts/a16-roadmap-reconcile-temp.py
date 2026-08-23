#!/usr/bin/env python3
import base64
import json
import os
import sys
import urllib.request
from pathlib import Path

ROADMAP = Path('ROADMAP.md')
WORKFLOW_PATH = '.github/workflows/a16-roadmap-reconcile-temp.yml'
SCRIPT_PATH = 'scripts/a16-roadmap-reconcile-temp.py'


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected exactly one match, found {count}')
    return text.replace(old, new, 1)


def a16_block(text):
    start_marker = '### A16 — Retire dead code and small inherited defects\n'
    end_marker = '\n### A17 — Find out whether upstream has moved, and whether older webOS still works\n'
    start = text.find(start_marker)
    end = text.find(end_marker, start)
    if start < 0 or end < 0:
        raise SystemExit('could not isolate A16 roadmap block')
    return start, end, text[start:end]


def prepare():
    text = ROADMAP.read_text()
    start, end, block = a16_block(text)

    block = replace_once(
        block,
        '- **Status:** Open',
        '- **Status:** Partially implemented',
        'A16 status',
    )
    block = replace_once(
        block,
        "  - `type MediaEvents = keyof typeof MEDIA_EVENTS` (`media.new.tsx:1075`) resolves to array members,\n    not event names; `typeof MEDIA_EVENTS[number]` was intended, so the `Partial<Record<…>>` below\n    checks nothing. Inherited; no runtime effect.",
        "  - **Completed substep:** `MediaEvents` now derives from `typeof MEDIA_EVENTS[number]`, and the\n    generated wrapper map uses `React.ReactEventHandler<HTMLVideoElement>` instead of generic\n    `Function`; the local `@ts-expect-error` is gone. This restores type coverage for the live event\n    props without intending a runtime behaviour change.",
        'MediaEvents evidence',
    )
    block = replace_once(
        block,
        "- **Proposed direction:** Point `video.tsx` at `components/media` and delete `media.tsx`; then find\n  out what the `@ts-expect-error` on `:221` was hiding, since it may stop being needed or may reveal a\n  genuine mismatch. Track and clear the retry timers as a set. Remove the style element on unmount.\n  Fix `MediaEvents`. Decide about the extra app ids deliberately.",
        "- **Implemented progress / remaining direction:** The `MediaEvents` type-coverage substep is\n  complete. Point `video.tsx` at `components/media` and delete `media.tsx`; then find out what the\n  `@ts-expect-error` on `:221` was hiding, since it may stop being needed or may reveal a genuine\n  mismatch. Track and clear the retry timers as a set. Remove the style element on unmount. Decide\n  about the extra app ids deliberately.",
        'A16 direction',
    )
    block = replace_once(
        block,
        "- **Validation and acceptance criteria:** `yarn typecheck`, `yarn lint`, `yarn test` and `yarn build`\n  all pass; playback and quality switching unchanged on the TV.",
        "- **Validation and acceptance criteria:** The completed `MediaEvents` substep has green typecheck,\n  lint, test and build CI. Remaining A16 cleanup must preserve those checks; playback and quality\n  switching unchanged on the TV remains device acceptance where a remaining cleanup can affect\n  playback behaviour.",
        'A16 validation',
    )

    ROADMAP.write_text(text[:start] + block + text[end:])


def api(method, path, payload=None):
    repo = os.environ['GITHUB_REPOSITORY']
    token = os.environ['GH_TOKEN']
    url = f'https://api.github.com/repos/{repo}{path}'
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Authorization', f'Bearer {token}')
    req.add_header('Accept', 'application/vnd.github+json')
    req.add_header('X-GitHub-Api-Version', '2022-11-28')
    if data is not None:
        req.add_header('Content-Type', 'application/json')
    with urllib.request.urlopen(req) as response:
        return json.load(response)


def ref_sha():
    branch = os.environ['HEAD_BRANCH']
    return api('GET', f'/git/ref/heads/{branch}')['object']['sha']


def publish():
    expected_head = os.environ['EXPECTED_HEAD']
    branch = os.environ['HEAD_BRANCH']
    text = ROADMAP.read_text()
    _, _, block = a16_block(text)
    required = [
        '- **Status:** Partially implemented',
        '**Completed substep:** `MediaEvents` now derives from `typeof MEDIA_EVENTS[number]`',
        '- **Implemented progress / remaining direction:** The `MediaEvents` type-coverage substep is',
        'The completed `MediaEvents` substep has green typecheck',
    ]
    for needle in required:
        if block.count(needle) != 1:
            raise SystemExit(f'publish guard failed for {needle!r}')
    if '`type MediaEvents = keyof typeof MEDIA_EVENTS`' in block:
        raise SystemExit('stale MediaEvents roadmap evidence remains')

    if ref_sha() != expected_head:
        raise SystemExit('branch head changed before publication')

    roadmap_bytes = ROADMAP.read_bytes()
    blob = api('POST', '/git/blobs', {
        'content': base64.b64encode(roadmap_bytes).decode(),
        'encoding': 'base64',
    })['sha']
    head_commit = api('GET', f'/git/commits/{expected_head}')
    tree = api('POST', '/git/trees', {
        'base_tree': head_commit['tree']['sha'],
        'tree': [
            {'path': 'ROADMAP.md', 'mode': '100644', 'type': 'blob', 'sha': blob},
            {'path': WORKFLOW_PATH, 'mode': '100644', 'type': 'blob', 'sha': None},
            {'path': SCRIPT_PATH, 'mode': '100644', 'type': 'blob', 'sha': None},
        ],
    })['sha']
    commit = api('POST', '/git/commits', {
        'message': 'docs: reconcile A16 media event type progress',
        'tree': tree,
        'parents': [expected_head],
    })['sha']

    if ref_sha() != expected_head:
        raise SystemExit('branch head changed immediately before ref update')
    api('PATCH', f'/git/refs/heads/{branch}', {'sha': commit, 'force': False})
    print(f'published cleanup commit {commit}')
    print(f'roadmap blob {blob}')


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in {'prepare', 'publish'}:
        raise SystemExit('usage: a16-roadmap-reconcile-temp.py prepare|publish')
    if sys.argv[1] == 'prepare':
        prepare()
    else:
        publish()
