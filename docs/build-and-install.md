# Build and install from source

This document describes the repeatable build and installation loop for this fork. It uses the versions and scripts tracked in the repository and does not require a package or a build instruction from the original repository.

## Prerequisites

Install the following on the computer used for development:

- Git;
- Node.js 14 (required). The repository pins the Node.js line in `.nvmrc` (`lts/fermium`). The build uses `react-scripts` 4 and webpack 4, which are not compatible with Node.js 17 and newer: those versions use OpenSSL 3 and can fail with `ERR_OSSL_EVP_UNSUPPORTED`. If `nvm` is not installed on macOS with zsh, install the pinned, signed [`v0.40.6` release](https://github.com/nvm-sh/nvm/releases/tag/v0.40.6) using Git. The commit check prevents a moved tag from being accepted:

  ```sh
  NVM_VERSION=v0.40.6
  NVM_COMMIT=b6cf55f6adf3b953d0e5e00a4049444e300e3af8
  git clone --depth 1 --branch "$NVM_VERSION" https://github.com/nvm-sh/nvm.git "$HOME/.nvm"
  test "$(git -C "$HOME/.nvm" rev-parse HEAD)" = "$NVM_COMMIT" || {
    echo "Unexpected nvm commit; remove $HOME/.nvm and stop"
    exit 1
  }
  touch "$HOME/.zshrc"
  printf '%s\n' \
    'export NVM_DIR="$HOME/.nvm"' \
    '[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"' >> "$HOME/.zshrc"
  source ~/.zshrc
  command -v nvm
  ```

  Then use the repository's Node.js version:

  ```sh
  nvm install "$(cat .nvmrc)"
  nvm use "$(cat .nvmrc)"
  node --version
  ```

  Confirm that the output starts with `v14.` before installing dependencies or running the build. A newer Node.js version may be installed on the computer, but it must not be used for this repository's build and packaging loop.

- Yarn Classic 1.x. The lockfile is Yarn v1; use a fixed Yarn version for a reproducible dependency install:

  ```sh
  npm install --global yarn@1.22.22
  yarn --version
  ```

The commands below are intended to be run from the repository root. `yarn install` installs the project-local webOS `ares-*` commands as well as the application dependencies, so a global webOS CLI is not required for this loop.

## Install dependencies

```sh
yarn install --frozen-lockfile
```

`--frozen-lockfile` makes Yarn use the committed `yarn.lock` without changing it. If the dependency tree needs to change, update it deliberately in a separate change and review the resulting lockfile diff.

## Build and package the IPK

For a clean local package, remove only the generated directories and then run the tracked build scripts:

```sh
rm -rf build out
yarn lint
yarn build
yarn package
```

The commands produce the web application in `build/` and the IPK package in `out/`. The package for this application is:

```text
out/kinopub.webos_v<version>.ipk
```

For the current `package.json`, for example, the file is `out/kinopub.webos_v1.3.0.ipk`. `yarn package` packages only this canonical application id.

The same build and package commands are used by the repository's GitHub Actions workflows. For code changes, `yarn lint` is a useful local check before building; the build and package steps are the checks that produce the TV artifact.

### Troubleshoot a failed build on a newer Node.js version

If `yarn build` fails with `error:0308010C:digital envelope routines::unsupported` or `ERR_OSSL_EVP_UNSUPPORTED`, check the active runtime:

```sh
node --version
nvm use "$(cat .nvmrc)"
node --version
yarn build
```

## Prepare the LG TV and Developer Mode session

Complete this once per TV, following LG's [Developer Mode app guide](https://webostv.developer.lge.com/develop/getting-started/developer-mode-app):

1. Install **Developer Mode** from LG Apps and sign in with an LG Developer account.
2. Open the Developer Mode app and turn on **Dev Mode Status**. The TV reboots.
3. Keep the TV and the computer on the same network.
4. Add the TV to the local webOS CLI device list:

   ```sh
   yarn ares-setup-device
   ```

   Add a device with the TV's IP address, port `9922`, user `prisoner`, and a name such as `lg-g5`. Check the result with:

   ```sh
   yarn ares-setup-device --list
   ```

5. In the Developer Mode app, turn on **Key Server**. Retrieve and register the TV key:

   ```sh
   yarn ares-novacom --device lg-g5 --getkey
   ```

   When prompted, enter the case-sensitive passphrase shown in the Developer Mode app.

6. Verify the connection:

   ```sh
   yarn ares-device --system-info --device lg-g5
   ```

Replace `lg-g5` with the device name chosen in `ares-setup-device`.

### Renew the Developer Mode session

Developer Mode is time-limited. Open the Developer Mode app while the TV is connected to the network and check **Remain Session**. Before it expires, click **EXTEND**. LG notes that an expired session cannot be extended; after that, enable Developer Mode again and repeat the key/connection steps if necessary. Keep the Developer Mode app available when working on the TV so the remaining session time is visible.

## Install and launch the package

After `yarn package`, install the application package on the TV:

```sh
APP_VERSION="$(node -p "require('./package.json').version")"
yarn ares-install \
  --device lg-g5 \
  "out/kinopub.webos_v${APP_VERSION}.ipk"
```

For the current `package.json`, `APP_VERSION` is `1.3.0`, so the command installs `out/kinopub.webos_v1.3.0.ipk`. The equivalent command with the webOS CLI installed globally is:

```sh
ares-install --device lg-g5 "out/kinopub.webos_v${APP_VERSION}.ipk"
```

Launch the installed app explicitly when needed:

```sh
yarn ares-launch --device lg-g5 kinopub.webos
```

The IPK can also be launched from the TV's app launcher after installation.

## Short smoke test after installation

Before treating the build as usable on the TV, check the following:

1. The app installs without an error and launches from the TV launcher.
2. The existing session or pairing flow completes, or the app shows the expected login/pairing screen on a clean install.
3. A movie or episode opens and starts playback.
4. Pause/resume, seeking, audio selection, and subtitle selection work.
5. Exit to the app UI and reopen the same title from the relevant list.
6. If a playback change is being tested, enable the playback diagnostics overlay in the app settings and record the first visible failure or stall before trying a workaround.

For playback-specific investigations, use the more detailed [playback diagnostics manual test](./playback-diagnostics-manual-test.md).
