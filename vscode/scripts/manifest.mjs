// Writes the features' contributions into package.json (`activationEvents` and `contributes`).
// `--check` only verifies that package.json and src/features.ts are up to date.
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { root, loadFeatures, mergeManifest } from './features.mjs';

const check = process.argv.includes('--check');
const features = loadFeatures();
const file = join(root, 'package.json');
const before = readFileSync(file, 'utf8');
const pkg = JSON.parse(before);
const {activationEvents, contributes} = mergeManifest(features);
pkg.activationEvents = activationEvents;
pkg.contributes = contributes;
const after = JSON.stringify(pkg, null, 2) + '\n';

const problems = [];
const registry = readFileSync(join(root, 'src', 'features.ts'), 'utf8');
for (const f of features) if (!registry.includes(`features/${f.id}/`)) problems.push(`src/features.ts does not import features/${f.id}`);
if (check && after !== before) problems.push('package.json is out of date: run `npm run manifest`');
if (problems.length) { for (const p of problems) console.error(p); process.exit(1); }
if (!check && after !== before) { writeFileSync(file, after); console.log('package.json updated'); }
