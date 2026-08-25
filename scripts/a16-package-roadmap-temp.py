import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = os.environ.get('GITHUB_REPOSITORY', '')
API_ROOT = 'https://api.github.com'
DOC_PATH = Path('docs/build-and-install.md')
ROADMAP_PATH = Path('ROADMAP.md')
WORKFLOW_PATH = '.github/workflows/a16-package-roadmap-temp.yml'
SCRIPT_PATH = 'scripts/a16-package-roadmap-temp.py'


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected exactly one match, found {count}')
    return text.replace(old, new, 1)


def prepare() -> None:
    doc = DOC_PATH.read_text(encoding='utf-8')
    doc = replace_once(
        doc,
        'The commands produce the web application in `build/` and IPK packages in `out/`.',
        'The commands produce the web application in `build/` and the IPK package in `out/`.',
        'build/install package-count wording',
    )
    doc = replace_once(
        doc,
        'For the current `package.json`, for example, the file is `out/kinopub.webos_v1.3.0.ipk`. `yarn package` also creates packages with the test IDs used by the existing project tooling; install the package whose name starts with `kinopub.webos_v` and has no additional suffix.',
        'For the current `package.json`, for example, the file is `out/kinopub.webos_v1.3.0.ipk`. `yarn package` packages only this canonical application id.',
        'build/install inherited-id wording',
    )
    DOC_PATH.write_text(doc, encoding='utf-8')

    roadmap = ROADMAP_PATH.read_text(encoding='utf-8')
    start = roadmap.index('### A16 — Retire dead code and small inherited defects')
    end = roadmap.index('\n### A17 —', start)
    block = roadmap[start:end]

    block = replace_once(
        block,
        '- **Status:** Partially implemented',
        '- **Status:** Completed, validation incomplete',
        'A16 status',
    )
    block = replace_once(
        block,
        '  - `scripts/package.js:12` builds IPKs under `netflix`, `amazon`, `ivi`, `youtube`, `ui30` as well as\n    the real id. Inherited, documented around rather than decided on.',
        '  - **Completed substep:** packaging now uses only the canonical `package.json` application id. The\n    inherited `netflix`, `amazon`, `ivi`, `youtube`, and `ui30` package aliases were removed; the\n    normal `out/kinopub.webos_v<version>.ipk` artifact and packaging flow are otherwise unchanged.',
        'A16 package evidence',
    )
    old_progress = (
        '- **Implemented progress / remaining direction:** Four bounded maintenance substeps are complete:\n'
        '  `MediaEvents` now covers the live event-name values; `video.tsx` now takes `SourceTrack` from the\n'
        '  live `components/media` barrel with the dead legacy `media.tsx` removed; fatal-network retry timers\n'
        '  are tracked and cleaned up as a set without changing retry policy; and the subtitle-opacity style\n'
        '  now has symmetric effect cleanup without changing opacity semantics. The nearby `onAudioChange`\n'
        '  `@ts-expect-error` remains intentionally untouched pending separate evidence. Decide about the extra\n'
        '  app ids deliberately.'
    )
    new_progress = (
        '- **Implemented progress / remaining direction:** All five bounded maintenance decisions in this item\n'
        '  are complete: `MediaEvents` covers the live event-name values; `video.tsx` takes `SourceTrack` from\n'
        '  the live `components/media` barrel with the dead legacy `media.tsx` removed; fatal-network retry\n'
        '  timers are tracked and cleaned up as a set without changing retry policy; the subtitle-opacity style\n'
        '  has symmetric effect cleanup without changing opacity semantics; and packaging now uses only the\n'
        '  canonical application id. The nearby `onAudioChange` `@ts-expect-error` remains intentionally\n'
        '  untouched because none of these bounded cleanups produced evidence that it is part of A16.'
    )
    block = replace_once(block, old_progress, new_progress, 'A16 progress')
    old_validation = (
        '- **Validation and acceptance criteria:** The completed `MediaEvents`, legacy-media type-source,\n'
        '  retry-timer, and subtitle-style lifecycle substeps have green typecheck, lint, test and build CI;\n'
        '  the retry-timer and subtitle-style changes also passed ES5 validation. Remaining A16 cleanup must\n'
        '  preserve those checks; playback and quality switching unchanged on the TV remains device acceptance\n'
        '  where a remaining cleanup can affect playback behaviour.'
    )
    new_validation = (
        '- **Validation and acceptance criteria:** The completed `MediaEvents`, legacy-media type-source,\n'
        '  retry-timer, and subtitle-style lifecycle substeps have green typecheck, lint, test and build CI;\n'
        '  the retry-timer and subtitle-style changes also passed ES5 validation. The canonical-package-id\n'
        '  substep has green CI packaging evidence that the normal `out/kinopub.webos_v<version>.ipk` is still\n'
        '  produced. Installing and launching that package on a television remains **A14** device evidence, not\n'
        '  something this maintenance item can verify in CI.'
    )
    block = replace_once(block, old_validation, new_validation, 'A16 validation')

    ROADMAP_PATH.write_text(roadmap[:start] + block + roadmap[end:], encoding='utf-8')


def api(method: str, path: str, payload=None):
    token = os.environ['GH_TOKEN']
    url = API_ROOT + path
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Authorization', f'Bearer {token}')
    req.add_header('Accept', 'application/vnd.github+json')
    req.add_header('X-GitHub-Api-Version', '2022-11-28')
    if data is not None:
        req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'{method} {path} failed: HTTP {exc.code}: {body}') from exc


def create_blob(path: Path) -> str:
    raw = path.read_bytes()
    result = api(
        'POST',
        f'/repos/{REPO}/git/blobs',
        {'content': base64.b64encode(raw).decode('ascii'), 'encoding': 'base64'},
    )
    return result['sha']


def ref_sha(branch: str) -> str:
    encoded = urllib.parse.quote(f'heads/{branch}', safe='/')
    return api('GET', f'/repos/{REPO}/git/ref/{encoded}')['object']['sha']


def publish() -> None:
    expected_head = os.environ['EXPECTED_HEAD']
    branch = os.environ['HEAD_BRANCH']

    current = ref_sha(branch)
    if current != expected_head:
        raise RuntimeError(f'head changed before publish: expected {expected_head}, found {current}')

    commit = api('GET', f'/repos/{REPO}/git/commits/{expected_head}')
    base_tree = commit['tree']['sha']
    doc_blob = create_blob(DOC_PATH)
    roadmap_blob = create_blob(ROADMAP_PATH)

    tree = api(
        'POST',
        f'/repos/{REPO}/git/trees',
        {
            'base_tree': base_tree,
            'tree': [
                {'path': str(DOC_PATH), 'mode': '100644', 'type': 'blob', 'sha': doc_blob},
                {'path': str(ROADMAP_PATH), 'mode': '100644', 'type': 'blob', 'sha': roadmap_blob},
                {'path': WORKFLOW_PATH, 'mode': '100644', 'type': 'blob', 'sha': None},
                {'path': SCRIPT_PATH, 'mode': '100644', 'type': 'blob', 'sha': None},
            ],
        },
    )
    final_commit = api(
        'POST',
        f'/repos/{REPO}/git/commits',
        {
            'message': 'docs: reconcile canonical package id decision',
            'tree': tree['sha'],
            'parents': [expected_head],
        },
    )

    current = ref_sha(branch)
    if current != expected_head:
        raise RuntimeError(f'head changed before ref update: expected {expected_head}, found {current}')

    encoded = urllib.parse.quote(f'heads/{branch}', safe='/')
    api(
        'PATCH',
        f'/repos/{REPO}/git/refs/{encoded}',
        {'sha': final_commit['sha'], 'force': False},
    )
    print(f"published cleanup commit {final_commit['sha']}")
    print(f"ROADMAP blob {roadmap_blob}")
    print(f"build/install blob {doc_blob}")


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {'prepare', 'publish'}:
        raise SystemExit('usage: a16-package-roadmap-temp.py prepare|publish')
    if sys.argv[1] == 'prepare':
        prepare()
    else:
        publish()


if __name__ == '__main__':
    main()
