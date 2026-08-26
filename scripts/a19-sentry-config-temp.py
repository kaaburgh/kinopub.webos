#!/usr/bin/env python3
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = os.environ.get("GITHUB_REPOSITORY")

DSN = "https://627d68f05165b49ebcb52675dc97e3bc@o4511850860576768.ingest.de.sentry.io/4511850884431952"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def prepare() -> None:
    logging_path = Path("src/utils/logging.ts")
    logging = logging_path.read_text()
    logging = replace_once(
        logging,
        "import { IS_WEB } from 'utils/enviroment';",
        "import { IS_WEB, shouldInitSentry } from 'utils/enviroment';",
        "logging import",
    )
    logging = replace_once(
        logging,
        "if (!IS_WEB) {\n  Sentry.init({\n    release: APP_VERSION,\n    dsn: '" + DSN + "',",
        "const SENTRY_DSN = process.env.REACT_APP_SENTRY_DSN;\n\nif (shouldInitSentry(IS_WEB, SENTRY_DSN)) {\n  Sentry.init({\n    release: APP_VERSION,\n    dsn: SENTRY_DSN,",
        "Sentry initialization",
    )
    logging_path.write_text(logging)

    environment_path = Path("src/utils/enviroment.ts")
    environment = environment_path.read_text()
    environment = replace_once(
        environment,
        "export const IS_WEB = isWebRuntime(window.location.origin);",
        "export function shouldInitSentry(isWeb: boolean, dsn?: string): dsn is string {\n  return !isWeb && Boolean(dsn);\n}\n\nexport const IS_WEB = isWebRuntime(window.location.origin);",
        "Sentry gate helper",
    )
    environment_path.write_text(environment)

    test_path = Path("src/utils/enviroment.test.ts")
    test = test_path.read_text()
    test = replace_once(
        test,
        "import { isWebRuntime } from './enviroment';",
        "import { isWebRuntime, shouldInitSentry } from './enviroment';",
        "environment test import",
    )
    if "describe('shouldInitSentry'" in test:
        raise SystemExit("Sentry gate tests already exist")
    test += "\ndescribe('shouldInitSentry', () => {\n  it('enables configured packaged runtimes', () => {\n    expect(shouldInitSentry(false, 'https://example.invalid/1')).toBe(true);\n  });\n\n  it('keeps browser and unconfigured packaged runtimes silent', () => {\n    expect(shouldInitSentry(true, 'https://example.invalid/1')).toBe(false);\n    expect(shouldInitSentry(false, undefined)).toBe(false);\n    expect(shouldInitSentry(false, '')).toBe(false);\n  });\n});\n"
    test_path.write_text(test)

    env_path = Path(".env")
    env_text = env_path.read_text()
    if "REACT_APP_SENTRY_DSN=" in env_text:
        raise SystemExit("REACT_APP_SENTRY_DSN already exists")
    if not env_text.endswith("\n"):
        env_text += "\n"
    env_text += f"REACT_APP_SENTRY_DSN={DSN}\n"
    env_path.write_text(env_text)


def api(method: str, path: str, payload=None):
    token = os.environ["GH_TOKEN"]
    if not REPO:
        raise SystemExit("GITHUB_REPOSITORY is missing")
    url = f"https://api.github.com/repos/{REPO}{path}"
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request) as response:
            body = response.read()
            return json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise SystemExit(f"GitHub API {method} {path} failed: {exc.code} {body}")


def branch_sha(branch: str) -> str:
    escaped = urllib.parse.quote(f"heads/{branch}", safe="/")
    return api("GET", f"/git/ref/{escaped}")["object"]["sha"]


def create_blob(path: str) -> str:
    content = Path(path).read_bytes()
    return api(
        "POST",
        "/git/blobs",
        {"content": base64.b64encode(content).decode(), "encoding": "base64"},
    )["sha"]


def publish() -> None:
    expected = os.environ["EXPECTED_HEAD"]
    branch = os.environ["HEAD_BRANCH"]

    observed = branch_sha(branch)
    if observed != expected:
        raise SystemExit(f"head moved before publish: expected {expected}, observed {observed}")

    commit = api("GET", f"/git/commits/{expected}")
    base_tree = commit["tree"]["sha"]

    files = [
        ".env",
        "src/utils/logging.ts",
        "src/utils/enviroment.ts",
        "src/utils/enviroment.test.ts",
    ]
    entries = [
        {"path": path, "mode": "100644", "type": "blob", "sha": create_blob(path)}
        for path in files
    ]
    entries.extend(
        [
            {"path": ".github/workflows/a19-sentry-config-temp.yml", "mode": "100644", "type": "blob", "sha": None},
            {"path": "scripts/a19-sentry-config-temp.py", "mode": "100644", "type": "blob", "sha": None},
        ]
    )

    tree = api("POST", "/git/trees", {"base_tree": base_tree, "tree": entries})["sha"]
    new_commit = api(
        "POST",
        "/git/commits",
        {
            "message": "config: read Sentry DSN from build environment",
            "tree": tree,
            "parents": [expected],
        },
    )["sha"]

    observed = branch_sha(branch)
    if observed != expected:
        raise SystemExit(f"head moved before ref update: expected {expected}, observed {observed}")

    escaped = urllib.parse.quote(f"heads/{branch}", safe="/")
    api("PATCH", f"/git/refs/{escaped}", {"sha": new_commit, "force": False})
    print(f"published {new_commit}")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"prepare", "publish"}:
        raise SystemExit("usage: a19-sentry-config-temp.py prepare|publish")
    if sys.argv[1] == "prepare":
        prepare()
    else:
        publish()
