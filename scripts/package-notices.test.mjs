// Local package inspection. This does not approve a public release or its license.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { writeLockNotices } from './package-notices.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const run = (cmd, args, cwd) => execFileSync(cmd, args, { cwd, encoding: 'utf8' });
const license = readFileSync(join(root, 'third_party/elkjs/LICENSE.md'), 'utf8');
const notice = readFileSync(join(root, 'third_party/elkjs/NOTICE.txt'), 'utf8');

test('built VSIX and engine archive retain ELK license and source notice', () => {
  const temp = mkdtempSync(join(tmpdir(), 'rvw-notices-'));
  try {
    const vscode = join(root, 'vscode');
    const engine = join(root, 'SpinalBlocks/engine');
    run('node', ['build.mjs'], vscode);
    run('node', ['build.mjs'], engine);
    // The project license is unresolved (#37). This archive is for local inspection only.
    run('node', ['node_modules/@vscode/vsce/vsce', 'package', '--no-dependencies',
      '--skip-license', '--out', join(temp, 'test.vsix')], vscode);
    const packed = JSON.parse(run('npm', ['pack', '--ignore-scripts', '--json', '--pack-destination', temp], engine));
    const inspect = `import sys,zipfile,tarfile,json
with zipfile.ZipFile(sys.argv[1]) as z:
 v={n:z.read(n).decode() for n in z.namelist() if n.endswith(('third_party/elkjs/LICENSE.md','third_party/elkjs/NOTICE.txt','THIRD_PARTY_NOTICES.md'))}
with tarfile.open(sys.argv[2]) as t:
 e={n:t.extractfile(n).read().decode() for n in t.getnames() if n.endswith(('dist/third_party/elkjs/LICENSE.md','dist/third_party/elkjs/NOTICE.txt'))}
print(json.dumps([v,e]))`;
    const [v, e] = JSON.parse(run('python3', ['-c', inspect, join(temp, 'test.vsix'), join(temp, packed[0].filename)], root));
    for (const [files, prefix] of [[v, 'extension/dist'], [e, 'package/dist']]) {
      assert.equal(files[`${prefix}/third_party/elkjs/LICENSE.md`], license);
      assert.equal(files[`${prefix}/third_party/elkjs/NOTICE.txt`], notice);
    }
    const inventory = v['extension/THIRD_PARTY_NOTICES.md'];
    assert.ok(inventory, 'VSIX must contain the lockfile inventory');
    const lock = JSON.parse(readFileSync(join(vscode, 'package-lock.json'), 'utf8'));
    for (const path of Object.keys(lock.packages).filter(p => p)) assert.ok(inventory.includes(`## ${path}\n`), path);
    const regenerated = join(temp, 'notices.md');
    writeLockNotices(join(vscode, 'package-lock.json'), regenerated);
    assert.equal(inventory, readFileSync(regenerated, 'utf8'));
  } finally { rmSync(temp, { recursive: true, force: true }); }
});
