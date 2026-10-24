// Builds the extension host and, for every feature, its webview bundles, assets and tests.
// Output: dist/extension.js, dist/<feature id>/..., dist/<feature id>/test/...
import { build } from 'esbuild';
import { copyFileSync, existsSync, mkdirSync, rmSync } from 'node:fs';
import { createRequire } from 'node:module';
import { basename, join } from 'node:path';
import { root, loadFeatures } from './scripts/features.mjs';

const require = createRequire(import.meta.url);
const dist = join(root, 'dist');
rmSync(dist, {recursive: true, force: true});
mkdirSync(dist, {recursive: true});
const log = {logLevel: 'info'};

await build({entryPoints: [join(root, 'src/extension.ts')], bundle: true, platform: 'node', format: 'cjs', target: 'node20',
  external: ['vscode'], outfile: join(dist, 'extension.js'), ...log});

for (const feature of loadFeatures()) {
  const out = join(dist, feature.id);
  mkdirSync(out, {recursive: true});
  if (feature.webviews?.length) await build({entryPoints: feature.webviews.map(w => join(feature.path, w)), bundle: true,
    platform: 'browser', format: 'iife', target: 'es2022', outdir: out, nodePaths: [join(root, 'node_modules')], ...log});
  // An asset is a file in the feature folder, or else a package path resolved from node_modules.
  for (const [from, to] of Object.entries(feature.assets ?? {})) {
    const local = join(feature.path, from);
    copyFileSync(existsSync(local) ? local : require.resolve(from), join(out, to));
  }
  const tests = [...(feature.tests?.unit ?? []), ...[feature.tests?.integration ?? []].flat()];
  if (tests.length) await build({entryPoints: tests.map(t => join(feature.path, t)), bundle: true, platform: 'node', format: 'cjs',
    target: 'node20', external: ['vscode', 'playwright-core'], outdir: join(out, 'test'), ...log});
}
console.log(`built ${basename(dist)}/`);
