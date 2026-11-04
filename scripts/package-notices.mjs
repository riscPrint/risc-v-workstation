// Shared package notices. Keep the pinned ELK text beside every copied worker.
import { copyFileSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const elk = fileURLToPath(new URL('../third_party/elkjs/', import.meta.url));
export function copyElkNotices(dist, packageFile) {
  const pkg = JSON.parse(readFileSync(packageFile, 'utf8'));
  if (pkg.version !== '0.12.0') throw new Error('Review ELK notices for the new version');
  const out = join(dist, 'third_party', 'elkjs');
  mkdirSync(out, { recursive: true });
  for (const name of ['LICENSE.md', 'NOTICE.txt']) copyFileSync(join(elk, name), join(out, name));
}

export function writeLockNotices(lockFile, output) {
  const lock = JSON.parse(readFileSync(lockFile, 'utf8'));
  if (!lock.packages) throw new Error('Expected an npm lockfile with packages');
  const lines = [
    '# Third-party notices', '',
    'Generated from package-lock.json. Do not edit by hand.',
    'This inventory includes build, test, optional and runtime dependencies.',
    'An entry does not mean that the package is present in the extension.',
    'License labels come from the lockfile. They do not establish release clearance.',
    'ELK license text and source notice: dist/third_party/elkjs/.', '',
  ];
  for (const path of Object.keys(lock.packages).filter(p => p).sort()) {
    const p = lock.packages[path];
    lines.push(`## ${path}`, '', `Version: ${p.version ?? 'not recorded'}`,
      `License: ${p.license ?? 'not recorded'}`, `Source archive: ${p.resolved ?? 'not recorded'}`,
      `Integrity: ${p.integrity ?? 'not recorded'}`, '');
  }
  writeFileSync(output, lines.join('\n'));
}
