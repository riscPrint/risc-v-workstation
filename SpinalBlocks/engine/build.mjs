// Builds dist/: ESM bundles for hosts plus the ELK worker script.
import { build } from 'esbuild';
import { copyFileSync, mkdirSync } from 'node:fs';

mkdirSync('dist', { recursive: true });
const common = { bundle: true, format: 'esm', target: 'es2022', sourcemap: true, logLevel: 'info' };
await build({ ...common, entryPoints: { index: 'src/index.ts', core: 'src/core.ts', elk: 'src/elk.ts', 'elk-main': 'src/elk-main.ts' }, outdir: 'dist' });
// The worker is a classic script; elkjs ships it ready to use.
copyFileSync('node_modules/elkjs/lib/elk-worker.min.js', 'dist/elk-worker.js');
