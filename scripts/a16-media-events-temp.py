#!/usr/bin/env python3
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

REPO = os.environ['GITHUB_REPOSITORY']
BRANCH = os.environ['HEAD_BRANCH']
EXPECTED = os.environ['EXPECTED_HEAD_SHA']
TOKEN = os.environ['GITHUB_TOKEN']
API = 'https://api.github.com'
SOURCE = Path('src/components/media/media.new.tsx')
WORKFLOW_PATH = '.github/workflows/a16-media-events-temp.yml'
SCRIPT_PATH = 'scripts/a16-media-events-temp.py'
OLD = 'type MediaEvents = keyof typeof MEDIA_EVENTS;'
NEW = 'type MediaEvents = (typeof MEDIA_EVENTS)[number];'


def request(method, path, payload=None):
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={
            'Authorization': 'Bearer ' + TOKEN,
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'Content-Type': 'application/json',
        },
    )
    try:
        with urllib.request.urlopen(req) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        body = error.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'{method} {path} failed: HTTP {error.code}: {body}') from error


def ref_sha():
    return request('GET', f'/repos/{REPO}/git/ref/heads/{BRANCH}')['object']['sha']


text = SOURCE.read_text(encoding='utf-8')
if text.count(OLD) != 1:
    raise SystemExit(f'expected exactly one old MediaEvents declaration, found {text.count(OLD)}')
if NEW in text:
    raise SystemExit('new MediaEvents declaration already present unexpectedly')
SOURCE.write_text(text.replace(OLD, NEW), encoding='utf-8')

if ref_sha() != EXPECTED:
    raise SystemExit('branch head changed before publication')

source_blob = request('POST', f'/repos/{REPO}/git/blobs', {'content': SOURCE.read_text(encoding='utf-8'), 'encoding': 'utf-8'})['sha']
base_commit = request('GET', f'/repos/{REPO}/git/commits/{EXPECTED}')
base_tree = base_commit['tree']['sha']
new_tree = request(
    'POST',
    f'/repos/{REPO}/git/trees',
    {
        'base_tree': base_tree,
        'tree': [
            {'path': str(SOURCE), 'mode': '100644', 'type': 'blob', 'sha': source_blob},
            {'path': WORKFLOW_PATH, 'mode': '100644', 'type': 'blob', 'sha': None},
            {'path': SCRIPT_PATH, 'mode': '100644', 'type': 'blob', 'sha': None},
        ],
    },
)['sha']
new_commit = request(
    'POST',
    f'/repos/{REPO}/git/commits',
    {'message': 'fix: type generated media event handlers by event name', 'tree': new_tree, 'parents': [EXPECTED]},
)['sha']

if ref_sha() != EXPECTED:
    raise SystemExit('branch head changed before ref update')

request('PATCH', f'/repos/{REPO}/git/refs/heads/{BRANCH}', {'sha': new_commit, 'force': False})
print('published', new_commit)
