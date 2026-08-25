from pathlib import Path
import base64
import json
import os
import urllib.request

ROADMAP = Path('ROADMAP.md')
README = Path('README.md')
WORKFLOW = '.github/workflows/a17-upstream-compat-temp.yml'
SCRIPT = 'scripts/a17-upstream-compat-temp.py'

OLD_REQUIREMENT = '- an LG Smart TV with webOS v3+ and the [Developer Mode app](https://webostv.developer.lge.com/develop/getting-started/developer-mode-app) for installing a development build;'
NEW_REQUIREMENT = '- an LG Smart TV with the [Developer Mode app](https://webostv.developer.lge.com/develop/getting-started/developer-mode-app) for installing a development build; this fork has been exercised on an LG G5, while older webOS generations remain unverified;'

NEW_A17 = '''### A17 — Find out whether upstream has moved, and whether older webOS still works

- **Status:** Investigation first — upstream checked; older-webOS device validation remains open
- **Depends on:** None
- **Priority:** Low
- **Category:** Compatibility
- **Origin:** Review §3, §7.5, §7.6
- **Problem or opportunity:** The two unknowns have now been separated. Upstream movement can be
  answered from repository history; older-webOS compatibility still needs target-device evidence.
- **Concrete evidence:** GitHub fork metadata identifies `alexeyeryshev/kinopub.webos` as this fork's
  direct parent and `ValeraGin/kinopub.webos` as the source repository. The direct parent's `master`
  advanced from inherited commit `58bd3ea0327c53247317de1f7f81795ca1ae21e6` to
  `e887c9966227a490e038a6a1efd56a559ffb3d32` with two commits: `6c632f9` adds default device settings
  plus substantial streaming/audio-selection changes, and `e887c99` bumps the version to 1.4.0.
  The source repository remains at `1d18773dcb18da59b7e32a700cc1f7de539669dd` from 2021, and
  `adascal/kinopub.webos` currently resolves 404 on GitHub. The parent's behavioral change includes
  disabling hls.js by default for its 4K/native-player path and changing audio-selection/device-setting
  behavior, so it conflicts with assumptions this fork has since made explicit and tested around HLS
  diagnostics, quality selection, and recovery; it is not a safe wholesale cherry-pick. Independently,
  `README.md` used to claim `webOS v3+`, while this fork's collected device evidence is from the LG G5.
  Older generations have not been verified. ES built-ins are covered by `core-js` and added DOM APIs
  are guarded, but flex `gap` in diagnostics remains a known presentation degradation on older engines.
- **Motivation and expected benefit:** The upstream half is no longer an unknown, and the public support
  claim now distinguishes tested reality from inherited compatibility assumptions.
- **Implemented direction:** Do not import the parent's August 2026 playback/default-settings commit
  wholesale. Treat any individual idea from it as a separate change requiring reconciliation with the
  fork's current playback architecture and evidence. README now states the tested LG G5 baseline and
  leaves older webOS generations explicitly unverified instead of claiming `webOS v3+`.
- **Dependencies and sequencing:** Upstream investigation is complete. Older-webOS compatibility is
  device-only and can be tested independently when suitable hardware is available.
- **Compatibility risks:** None from this documentation/investigation step. Narrowing the claim avoids
  promising support that has not been exercised.
- **Confidence:** code/repository history — high for upstream state and CSS analysis; device — LG G5
  only, with older webOS generations still unverified.
- **Validation and acceptance criteria:** Upstream movement and the adoption decision are recorded.
  The README claim matches verified device evidence. To finish the remaining compatibility question,
  install and exercise the current build on an older webOS panel and record the result; until then no
  older-generation support claim should be restored.
- **Estimated scope:** Upstream investigation complete; one older-panel viewing/install session remains.
'''


def prepare():
    readme = README.read_text()
    if readme.count(OLD_REQUIREMENT) != 1:
        raise SystemExit(f'expected exactly one old README requirement, found {readme.count(OLD_REQUIREMENT)}')
    README.write_text(readme.replace(OLD_REQUIREMENT, NEW_REQUIREMENT, 1))

    roadmap = ROADMAP.read_text()
    start_marker = '### A17 — Find out whether upstream has moved, and whether older webOS still works\n'
    start = roadmap.find(start_marker)
    if start < 0 or roadmap.find(start_marker, start + 1) >= 0:
        raise SystemExit('expected exactly one A17 heading')
    end = roadmap.find('\n---\n', start)
    if end < 0:
        raise SystemExit('could not find A17 section terminator')
    old_section = roadmap[start:end]
    if '- **Status:** Investigation first' not in old_section:
        raise SystemExit('A17 status no longer matches expected investigation state')
    ROADMAP.write_text(roadmap[:start] + NEW_A17.rstrip() + roadmap[end:])


def request(method, path, payload=None):
    repo = os.environ['GITHUB_REPOSITORY']
    token = os.environ['GH_TOKEN']
    url = f'https://api.github.com/repos/{repo}{path}'
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Accept', 'application/vnd.github+json')
    req.add_header('Authorization', f'Bearer {token}')
    req.add_header('X-GitHub-Api-Version', '2022-11-28')
    with urllib.request.urlopen(req) as response:
        return json.load(response)


def blob(path):
    content = base64.b64encode(Path(path).read_bytes()).decode()
    return request('POST', '/git/blobs', {'content': content, 'encoding': 'base64'})['sha']


def current_ref(branch):
    return request('GET', f'/git/ref/heads/{branch}')['object']['sha']


def publish():
    expected = os.environ['EXPECTED_HEAD']
    branch = os.environ['HEAD_BRANCH']
    if current_ref(branch) != expected:
        raise SystemExit('branch moved before publication')

    commit = request('GET', f'/git/commits/{expected}')
    tree = request('POST', '/git/trees', {
        'base_tree': commit['tree']['sha'],
        'tree': [
            {'path': 'ROADMAP.md', 'mode': '100644', 'type': 'blob', 'sha': blob('ROADMAP.md')},
            {'path': 'README.md', 'mode': '100644', 'type': 'blob', 'sha': blob('README.md')},
            {'path': WORKFLOW, 'mode': '100644', 'type': 'blob', 'sha': None},
            {'path': SCRIPT, 'mode': '100644', 'type': 'blob', 'sha': None},
        ],
    })['sha']
    new_commit = request('POST', '/git/commits', {
        'message': 'docs: record A17 upstream investigation',
        'tree': tree,
        'parents': [expected],
    })['sha']
    if current_ref(branch) != expected:
        raise SystemExit('branch moved before ref update')
    request('PATCH', f'/git/refs/heads/{branch}', {'sha': new_commit, 'force': False})
    print(f'published {new_commit}')


if __name__ == '__main__':
    mode = os.environ.get('MODE', 'prepare')
    if mode == 'prepare':
        prepare()
    elif mode == 'publish':
        publish()
    else:
        raise SystemExit(f'unknown MODE: {mode}')
