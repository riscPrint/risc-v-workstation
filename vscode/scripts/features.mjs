// Reads features/*/feature.json and merges their contributions into one extension manifest.
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

export const root = join(dirname(fileURLToPath(import.meta.url)), '..');

export function loadFeatures() {
  const dir = join(root, 'features');
  return readdirSync(dir, {withFileTypes: true})
    .filter(e => e.isDirectory() && existsSync(join(dir, e.name, 'feature.json')))
    .map(e => {
      const path = join(dir, e.name);
      const feature = JSON.parse(readFileSync(join(path, 'feature.json'), 'utf8'));
      if (feature.id !== e.name) throw new Error(`features/${e.name}/feature.json: id must be "${e.name}", found "${feature.id}"`);
      if (!/^[a-z][a-z0-9-]*$/.test(feature.id)) throw new Error(`features/${e.name}: id must be lowercase letters, digits and dashes`);
      return {...feature, path};
    })
    .sort((a, b) => a.id.localeCompare(b.id));
}

// Ids a feature defines must start with "<feature id>." so features never collide.
function checkNamespace(feature, kind, id) {
  if (!id.startsWith(`${feature.id}.`)) throw new Error(`${feature.id}: ${kind} "${id}" must start with "${feature.id}."`);
}

function checkFeature(feature) {
  const c = feature.contributes ?? {};
  for (const x of c.commands ?? []) checkNamespace(feature, 'command', x.command);
  for (const x of c.customEditors ?? []) checkNamespace(feature, 'custom editor', x.viewType);
  for (const views of Object.values(c.views ?? {})) for (const x of views) checkNamespace(feature, 'view', x.id);
  for (const cfg of [c.configuration ?? []].flat()) for (const key of Object.keys(cfg.properties ?? {})) checkNamespace(feature, 'setting', key);
}

// Arrays concatenate, objects merge key by key, and two different scalars for the same key are an error.
function merge(a, b, at) {
  if (a === undefined) return structuredClone(b);
  if (Array.isArray(a) && Array.isArray(b)) {
    const out = [...a];
    for (const x of b) if (!out.some(y => JSON.stringify(y) === JSON.stringify(x))) out.push(structuredClone(x));
    return out;
  }
  if (a && b && typeof a === 'object' && typeof b === 'object' && !Array.isArray(a) && !Array.isArray(b)) {
    const out = {...a};
    for (const [k, v] of Object.entries(b)) out[k] = merge(a[k], v, `${at}.${k}`);
    return out;
  }
  if (JSON.stringify(a) !== JSON.stringify(b)) throw new Error(`conflicting values at ${at}`);
  return a;
}

export function mergeManifest(features) {
  let contributes = {};
  const configuration = [];
  const activationEvents = [];
  for (const feature of features) {
    checkFeature(feature);
    const {configuration: cfg, ...rest} = feature.contributes ?? {};
    // Each feature keeps its own settings section, titled after the feature.
    for (const c of [cfg ?? []].flat()) configuration.push({title: feature.title, ...c});
    contributes = merge(contributes, rest, `contributes(${feature.id})`);
    for (const e of feature.activationEvents ?? []) if (!activationEvents.includes(e)) activationEvents.push(e);
  }
  if (configuration.length) contributes.configuration = configuration;
  const seen = new Map();
  for (const x of contributes.commands ?? []) {
    if (seen.has(x.command)) throw new Error(`duplicate command ${x.command}`);
    seen.set(x.command, true);
  }
  return {activationEvents, contributes};
}
