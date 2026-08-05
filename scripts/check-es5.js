#!/usr/bin/env node
/**
 * Fails if anything in the production bundle is not ES5.
 *
 * The television this app is built for runs a browser from around 2016, which `.browserslistrc`
 * pins as `chrome 35`. A single arrow function or `const` reaching it is not a degraded experience:
 * the script fails to parse, nothing runs, and the screen stays black with no error anyone can see.
 * That makes it the worst class of regression this project can ship and the cheapest to check.
 *
 * The check exists because the guarantee is indirect and easy to lose. Create React App transpiles
 * dependencies as well as application code -- it applies `babel-preset-react-app/dependencies` to
 * every `.js` and `.mjs` under `node_modules`, targeting the same browserslist -- so a modern
 * dependency is normally downlevelled without anyone thinking about it. Nothing announces it when
 * that stops being true: a package that ships syntax Babel's target does not cover, a build tool
 * change, or a bundler that stops running the rule would all pass every other check in CI.
 *
 * Reading the output is not a substitute for parsing it. `class`, backticks and `?.` all appear in
 * string literals inside a minified bundle, so grep says the file is modern when it is not.
 */
const fs = require('fs');
const path = require('path');

const acorn = require('acorn');

const BUNDLE_DIR = path.join(__dirname, '..', 'build', 'static', 'js');

function main() {
  if (!fs.existsSync(BUNDLE_DIR)) {
    console.error(`No bundle found at ${path.relative(process.cwd(), BUNDLE_DIR)}. Run \`yarn build\` first.`);
    process.exit(1);
  }

  const bundles = fs.readdirSync(BUNDLE_DIR).filter((name) => name.endsWith('.js'));

  if (bundles.length === 0) {
    console.error(`No JavaScript bundles in ${path.relative(process.cwd(), BUNDLE_DIR)}; the build produced nothing to check.`);
    process.exit(1);
  }

  const failures = [];

  bundles.forEach((name) => {
    const source = fs.readFileSync(path.join(BUNDLE_DIR, name), 'utf8');

    try {
      acorn.parse(source, { ecmaVersion: 5 });
    } catch (error) {
      failures.push({ name, message: error.message });
    }
  });

  if (failures.length > 0) {
    console.error('These bundles are not ES5, so the app will not start on the target browser:\n');
    failures.forEach((failure) => {
      console.error(`  ${failure.name}: ${failure.message}`);
    });
    console.error(
      '\nThe position in the message is into the minified bundle. To find the culprit, build with' +
        '\n`GENERATE_SOURCEMAP=true` and look up that offset, or bisect by removing recent dependency' +
        '\nchanges. A dependency shipping syntax newer than the browserslist target is the usual cause.',
    );
    process.exit(1);
  }

  console.log(`All ${bundles.length} bundles parse as ES5.`);
}

main();
