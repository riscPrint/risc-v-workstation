#!/usr/bin/env node
// Serves the web host and one design file, then opens the browser:
//   node serve.mjs <design.json|design.json.gz> [--port 8737] [--no-open]
import { createServer } from 'node:http';
import { existsSync, readFileSync, statSync } from 'node:fs';
import { execFileSync, spawn } from 'node:child_process';
import { extname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = fileURLToPath(new URL('.', import.meta.url));
const args = process.argv.slice(2);
const design = args.find(a => !a.startsWith('--') && !/^\d+$/.test(a));
const portArg = args.indexOf('--port');
const port = portArg >= 0 ? Number(args[portArg + 1]) : 8737;
if (!design || !existsSync(design)) {
  console.error('usage: serve.mjs <design.json|design.json.gz> [--port N] [--no-open]');
  process.exit(1);
}

const dist = join(here, 'dist');
const sources = ['src/main.ts', 'index.html', 'style.css'].map(f => join(here, f));
const stale = !existsSync(join(dist, 'main.js')) ||
  sources.some(f => statSync(f).mtimeMs > statSync(join(dist, 'main.js')).mtimeMs);
if (stale) execFileSync(process.execPath, [join(here, 'build.mjs')], { cwd: here, stdio: 'inherit' });

const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.map': 'application/json' };
const designPath = resolve(design);
createServer((req, res) => {
  const url = new URL(req.url ?? '/', 'http://localhost');
  if (url.pathname === '/design') {
    res.writeHead(200, { 'content-type': 'application/octet-stream', 'cache-control': 'no-store' });
    res.end(readFileSync(designPath)); // read per request so a regenerated design shows on reload
    return;
  }
  const file = join(dist, url.pathname === '/' ? 'index.html' : url.pathname);
  if (!file.startsWith(dist) || !existsSync(file) || statSync(file).isDirectory()) { res.writeHead(404); res.end(); return; }
  res.writeHead(200, { 'content-type': types[extname(file)] ?? 'application/octet-stream' });
  res.end(readFileSync(file));
}).listen(port, '127.0.0.1', () => {
  const link = `http://127.0.0.1:${port}/?file=/design`;
  console.log(`SpinalBlocks: ${designPath}\n  ${link}`);
  if (!args.includes('--no-open')) {
    const opener = process.platform === 'darwin' ? 'open' : process.platform === 'win32' ? 'start' : 'xdg-open';
    spawn(opener, [link], { stdio: 'ignore', detached: true, shell: process.platform === 'win32' }).unref();
  }
});
