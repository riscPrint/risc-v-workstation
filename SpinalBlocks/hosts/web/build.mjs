// Bundles the host and copies the ELK worker next to it: dist/ is a static site.
import { build } from 'esbuild';
import { copyFileSync, mkdirSync } from 'node:fs';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
mkdirSync('dist', { recursive: true });
await build({ entryPoints: ['src/main.ts'], bundle: true, format: 'esm', target: 'es2022', sourcemap: true, outfile: 'dist/main.js', logLevel: 'info' });
copyFileSync('index.html', 'dist/index.html');
copyFileSync('style.css', 'dist/style.css');
copyFileSync(require.resolve('elkjs/lib/elk-worker.min.js', { paths: ['../../engine'] }), 'dist/elk-worker.js');
