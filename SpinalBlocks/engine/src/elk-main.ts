// ELK on the calling thread (Node, tests, CLI tools). Blocks while laying out.
import ELK from 'elkjs/lib/elk.bundled.js';
import type { LayoutEngine } from './core/layout.ts';

export function mainThreadLayout(): LayoutEngine {
  return new ELK() as unknown as LayoutEngine;
}
