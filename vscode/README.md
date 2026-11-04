# RISC-V Workstation for VS Code

One VS Code extension for the tools in this repository. Each tool adds a **feature**: its commands, editors, views and settings. Users install one extension and get all of them.

| Feature | What it adds | Docs |
|---|---|---|
| `spinalblocks` | Block and state machine diagrams for elaborated SpinalHDL designs, linked to the Scala source | [features/spinalblocks/README.md](features/spinalblocks/README.md) |
| `regress` | Saved C3 tests and C4 verdicts, with full causes | [features/regress/README.md](features/regress/README.md) |
| `coverage` | Saved coverage reports, holes and limits | [features/coverage/README.md](features/coverage/README.md) |
| `perf` | Saved perf measurements and scope | [features/perf/README.md](features/perf/README.md) |

The result views include manual source navigation through `rvw query where`.
They also open selected waves in Surfer and selected dependency traces in SpinalTrace.
They show saved producer data. They do not validate run-set identity or issue verdicts.
See each feature README for commands and limits.

## Build and install

```sh
npm install
npm run build          # updates package.json from the features, then bundles everything into dist/
npm run package        # writes risc-v-workstation-<version>.vsix
code --install-extension risc-v-workstation-*.vsix
```

To try changes, open this folder in VS Code and run **Run RISC-V Workstation** (F5).

## Checks

```sh
npm run typecheck
npm run build
npm test                               # manifest check + every feature's unit tests
npm run test:integration:spinalblocks  # SpinalBlocks in a real VS Code (see its README)
```

## Layout

```
vscode/
  src/api.ts            Feature and FeatureContext: the interface between the extension and features
  src/extension.ts      starts every feature; one failing feature doesn't stop the others
  src/features.ts       the list of features
  features/<id>/        one folder per feature
    feature.json        what the feature contributes (see below)
    src/feature.ts      default export: the Feature
    test/               unit tests (*.test.ts) and an optional integration test
  scripts/manifest.mjs  merges every feature.json into package.json
  build.mjs             bundles the extension and every feature
```

Feature code may import from its tool's folder in the repository (SpinalBlocks imports `SpinalBlocks/engine/src`). It is bundled into the extension at build time.

## Adding a feature

1. Create `features/<id>/feature.json`. The id is lowercase, for example `spinaltrace`.

   ```json
   {
     "id": "spinaltrace",
     "title": "SpinalTrace",
     "description": "What the feature does.",
     "activationEvents": ["onCommand:spinaltrace.open"],
     "contributes": { "commands": [{ "command": "spinaltrace.open", "title": "SpinalTrace: Open Trace" }] },
     "webviews": ["src/webview.ts"],
     "assets": { "src/webview.css": "webview.css" },
     "tests": { "unit": ["test/thing.test.ts"], "integration": "test/integration.ts" }
   }
   ```

   - `contributes` uses VS Code's normal [contribution points](https://code.visualstudio.com/api/references/contribution-points). Command, custom editor, view and setting ids must start with `<id>.`, so features never collide.
   - Each feature's `configuration` becomes its own settings section, titled after the feature.
   - `webviews` are browser entry points, bundled to `dist/<id>/<name>.js`.
   - `assets` are copied to `dist/<id>/`. A source path is a file in the feature folder, or else a package path from `node_modules`.
   - `tests.unit` run under `node --test`. `tests.integration` is bundled to `dist/<id>/test/` for a VS Code test runner.

2. Write `features/<id>/src/feature.ts`:

   ```ts
   import * as vscode from 'vscode';
   import type { Feature } from '../../../src/api';

   const feature: Feature = {
     id: 'spinaltrace',
     activate(context) {
       context.subscriptions.push(vscode.commands.registerCommand('spinaltrace.open', () => context.log.info('open')));
     },
   };
   export default feature;
   ```

   The `FeatureContext` gives the feature:
   - `subscriptions`: disposed when the extension stops.
   - `workspaceState` and `globalState`: keys private to the feature.
   - `dist`: the feature's bundled webviews and assets.
   - `log`: the shared output channel, with lines tagged by feature.
   - `testMode`: true under the test runner.

   Whatever `activate` returns is available to tests and other features as `extension.exports.features.<id>`.

3. Add the feature to `src/features.ts`.

4. Run `npm run build`. `package.json`'s `activationEvents` and `contributes` are generated from the features; edit `feature.json`, not those fields. `npm test` fails if `package.json` is out of date or a feature is missing from `src/features.ts`.

All features start when any feature's activation event fires. If start-up cost becomes a problem, features can defer their heavy work until first use.
