#!/usr/bin/env python3
import base64
import json
import os
import pathlib
import sys
import urllib.request

VIDEO = pathlib.Path('src/views/video/video.tsx')
LEGACY = pathlib.Path('src/components/media/media.tsx')
WORKFLOW_PATH = '.github/workflows/a16-retire-legacy-media-temp.yml'
SCRIPT_PATH = 'scripts/a16-retire-legacy-media-temp.py'
OLD_IMPORT = "import { AudioTrack, SubtitleTrack } from 'components/media';\nimport { SourceTrack } from 'components/media/media';"
NEW_IMPORT = "import { AudioTrack, SourceTrack, SubtitleTrack } from 'components/media';"


def prepare():
    text = VIDEO.read_text()
    count = text.count(OLD_IMPORT)
    if count != 1:
        raise SystemExit(f'expected exactly one legacy SourceTrack import, found {count}')
    VIDEO.write_text(text.replace(OLD_IMPORT, NEW_IMPORT))
    if not LEGACY.exists():
        raise SystemExit('legacy media.tsx was already absent')
    LEGACY.unlink()


def api(path, method='GET', body=None):
    repo = os.environ['GITHUB_REPOSITORY']
    token = os.environ['GH_TOKEN']
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        f'https://api.github.com/repos/{repo}{path}',
        data=data,
        method=method,
        headers={
            'Accept': 'application/vnd.github+json',
            'Authorization': f'Bearer {token}',
            'X-GitHub-Api-Version': '2022-11-28',
            'Content-Type': 'application/json',
        },
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def ref_sha(branch):
    return api(f'/git/ref/heads/{branch}')['object']['sha']


def create_blob(path):
    content = base64.b64encode(path.read_bytes()).decode()
    return api('/git/blobs', 'POST', {'content': content, 'encoding': 'base64'})['sha']


def publish():
    expected = os.environ['EXPECTED_HEAD']
    branch = os.environ['HEAD_BRANCH']
    text = VIDEO.read_text()
    if OLD_IMPORT in text or text.count(NEW_IMPORT) != 1:
        raise SystemExit('live SourceTrack import guard failed')
    if LEGACY.exists():
        raise SystemExit('legacy media.tsx still exists')
    if ref_sha(branch) != expected:
        raise SystemExit('branch head changed before publish')

    commit = api(f'/git/commits/{expected}')
    video_blob = create_blob(VIDEO)
    tree = api('/git/trees', 'POST', {
        'base_tree': commit['tree']['sha'],
        'tree': [
            {'path': str(VIDEO), 'mode': '100644', 'type': 'blob', 'sha': video_blob},
            {'path': str(LEGACY), 'mode': '100644', 'type': 'blob', 'sha': None},
            {'path': WORKFLOW_PATH, 'mode': '100644', 'type': 'blob', 'sha': None},
            {'path': SCRIPT_PATH, 'mode': '100644', 'type': 'blob', 'sha': None},
        ],
    })
    new_commit = api('/git/commits', 'POST', {
        'message': 'refactor: retire legacy media type source',
        'tree': tree['sha'],
        'parents': [expected],
    })
    if ref_sha(branch) != expected:
        raise SystemExit('branch head changed before ref update')
    api(f'/git/refs/heads/{branch}', 'PATCH', {'sha': new_commit['sha'], 'force': False})
    print(f"published {new_commit['sha']}")


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in {'prepare', 'publish'}:
        raise SystemExit('usage: a16-retire-legacy-media-temp.py prepare|publish')
    globals()[sys.argv[1]]()
