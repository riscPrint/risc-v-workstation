// ELK setups for hosts. Kept out of the main entry so hosts that bring their own ELK don't ship it twice.
import ELK from 'elkjs/lib/elk-api.js';
import type { LayoutEngine } from './core/layout.ts';

/** ELK in a Web Worker. `workerUrl` points at dist/elk-worker.js (in VS Code: `webview.asWebviewUri(...)`;
 *  cross-origin URLs need a same-origin blob wrapper, which `workerFromUrl` makes). */
export function workerLayout(workerUrl: string): LayoutEngine {
  return new ELK({ workerFactory: () => workerFromUrl(workerUrl) }) as unknown as LayoutEngine;
}

/** A classic worker that imports a script, usable when the script is on another origin (VS Code webviews). */
export function workerFromUrl(url: string): Worker {
  const blob = new Blob([`importScripts(${JSON.stringify(url)});`], { type: 'text/javascript' });
  return new Worker(URL.createObjectURL(blob));
}
