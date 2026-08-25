import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PLAYER_PATH = Path('src/components/player/player.tsx')
WORKFLOW_PATH = '.github/workflows/a16-subtitle-style-temp.yml'
SCRIPT_PATH = 'scripts/a16-subtitle-style-temp.py'

OLD = """  useEffect(() => {\n    const styleId = 'subtitle-opacity-style';\n    let styleEl = document.getElementById(styleId) as HTMLStyleElement | null;\n    if (!styleEl) {\n      styleEl = document.createElement('style');\n      styleEl.id = styleId;\n      document.head.appendChild(styleEl);\n    }\n    styleEl.textContent = `video::cue { opacity: ${subtitleOpacity ?? 1}; }`;\n  }, [subtitleOpacity]);\n"""

NEW = """  useEffect(() => {\n    const styleId = 'subtitle-opacity-style';\n    let styleEl = document.getElementById(styleId) as HTMLStyleElement | null;\n    if (!styleEl) {\n      styleEl = document.createElement('style');\n      styleEl.id = styleId;\n      document.head.appendChild(styleEl);\n    }\n    styleEl.textContent = `video::cue { opacity: ${subtitleOpacity ?? 1}; }`;\n\n    return () => {\n      if (styleEl?.parentNode) {\n        styleEl.parentNode.removeChild(styleEl);\n      }\n    };\n  }, [subtitleOpacity]);\n"""


def prepare() -> None:
    text = PLAYER_PATH.read_text()
    count = text.count(OLD)
    if count != 1:
        raise SystemExit(f'expected exactly one subtitle opacity effect, found {count}')
    if NEW in text:
        raise SystemExit('corrected subtitle opacity effect already present')
    PLAYER_PATH.write_text(text.replace(OLD, NEW))


def api(method: str, path: str, payload=None):
    repo = os.environ['GITHUB_REPOSITORY']
    token = os.environ['GH_TOKEN']
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
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
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        body = error.read().decode(errors='replace')
        raise SystemExit(f'GitHub API {method} {path} failed: {error.code} {body}')


def ref_sha(branch: str) -> str:
    encoded = urllib.parse.quote(branch, safe='')
    return api('GET', f'/git/ref/heads/{encoded}')['object']['sha']


def publish() -> None:
    expected_head = os.environ['EXPECTED_HEAD']
    branch = os.environ['HEAD_BRANCH']
    if ref_sha(branch) != expected_head:
        raise SystemExit('branch head changed before publication')

    text = PLAYER_PATH.read_text()
    if text.count(NEW) != 1 or OLD in text:
        raise SystemExit('prepared player source does not contain the expected lifecycle fix')

    source_blob = api(
        'POST',
        '/git/blobs',
        {'content': base64.b64encode(PLAYER_PATH.read_bytes()).decode(), 'encoding': 'base64'},
    )['sha']
    base_commit = api('GET', f'/git/commits/{expected_head}')
    tree = api(
        'POST',
        '/git/trees',
        {
            'base_tree': base_commit['tree']['sha'],
            'tree': [
                {'path': str(PLAYER_PATH), 'mode': '100644', 'type': 'blob', 'sha': source_blob},
                {'path': WORKFLOW_PATH, 'mode': '100644', 'type': 'blob', 'sha': None},
                {'path': SCRIPT_PATH, 'mode': '100644', 'type': 'blob', 'sha': None},
            ],
        },
    )['sha']
    commit = api(
        'POST',
        '/git/commits',
        {
            'message': 'fix: clean up subtitle opacity style',
            'tree': tree,
            'parents': [expected_head],
        },
    )['sha']

    if ref_sha(branch) != expected_head:
        raise SystemExit('branch head changed before ref update')
    encoded = urllib.parse.quote(branch, safe='')
    api('PATCH', f'/git/refs/heads/{encoded}', {'sha': commit, 'force': False})
    print(commit)


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in {'prepare', 'publish'}:
        raise SystemExit('usage: a16-subtitle-style-temp.py prepare|publish')
    if sys.argv[1] == 'prepare':
        prepare()
    else:
        publish()
