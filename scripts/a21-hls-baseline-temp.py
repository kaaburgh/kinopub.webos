import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

REPO = os.environ['GITHUB_REPOSITORY']
TOKEN = os.environ['GH_TOKEN']
EXPECTED_HEAD = os.environ['EXPECTED_HEAD']
HEAD_BRANCH = os.environ['HEAD_BRANCH']
API = f'https://api.github.com/repos/{REPO}'
TEMP_PATHS = [
    '.github/workflows/a21-hls-baseline-temp.yml',
    'scripts/a21-hls-baseline-temp.py',
]


def api(method, path, payload=None):
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={
            'Authorization': f'Bearer {TOKEN}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'Content-Type': 'application/json',
        },
    )
    try:
        with urllib.request.urlopen(req) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode('utf-8', 'replace')
        raise RuntimeError(f'{method} {path} failed: HTTP {exc.code}: {body}') from exc


def ref_sha():
    branch = urllib.parse.quote(HEAD_BRANCH, safe='/')
    return api('GET', f'/git/ref/heads/{branch}')['object']['sha']


def create_file_blob(path):
    with open(path, 'rb') as handle:
        encoded = base64.b64encode(handle.read()).decode('ascii')
    return api('POST', '/git/blobs', {'content': encoded, 'encoding': 'base64'})['sha']


def main():
    package = json.load(open('package.json', encoding='utf-8'))
    actual = package.get('dependencies', {}).get('hls.js')
    if actual != '1.0.10':
        raise RuntimeError(f'expected package.json hls.js=1.0.10 after preparation, found {actual!r}')

    lock_text = open('yarn.lock', encoding='utf-8').read()
    if 'hls.js@1.0.10:' not in lock_text and 'hls.js@"1.0.10":' not in lock_text:
        raise RuntimeError('yarn.lock does not contain an hls.js 1.0.10 entry')
    if 'hls.js@1.6.15:' in lock_text or 'hls.js@"1.6.15":' in lock_text:
        raise RuntimeError('yarn.lock still contains the direct hls.js 1.6.15 entry')

    current = ref_sha()
    if current != EXPECTED_HEAD:
        raise RuntimeError(f'branch moved before publication: expected {EXPECTED_HEAD}, found {current}')

    base_commit = api('GET', f'/git/commits/{EXPECTED_HEAD}')
    base_tree = base_commit['tree']['sha']
    package_blob = create_file_blob('package.json')
    lock_blob = create_file_blob('yarn.lock')

    entries = [
        {'path': 'package.json', 'mode': '100644', 'type': 'blob', 'sha': package_blob},
        {'path': 'yarn.lock', 'mode': '100644', 'type': 'blob', 'sha': lock_blob},
    ]
    for path in TEMP_PATHS:
        entries.append({'path': path, 'mode': '100644', 'type': 'blob', 'sha': None})

    tree = api('POST', '/git/trees', {'base_tree': base_tree, 'tree': entries})
    commit = api(
        'POST',
        '/git/commits',
        {
            'message': 'build: restore hls.js 1.0.10 baseline',
            'tree': tree['sha'],
            'parents': [EXPECTED_HEAD],
        },
    )

    current = ref_sha()
    if current != EXPECTED_HEAD:
        raise RuntimeError(f'branch moved before ref update: expected {EXPECTED_HEAD}, found {current}')

    branch = urllib.parse.quote(HEAD_BRANCH, safe='/')
    api('PATCH', f'/git/refs/heads/{branch}', {'sha': commit['sha'], 'force': False})
    print(commit['sha'])


if __name__ == '__main__':
    main()
