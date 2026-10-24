// Browser entry point: the engine with the default SVG renderer. Layout is supplied by the host;
// see elk.ts for ready-made ELK setups.
export * from './core.ts';
export * from './engine.ts';
export type * from './render/types.ts';
export { SvgRenderer } from './render/svg.ts';
export * from './fsm-view.ts';
export { SvgFsmRenderer } from './render/fsm-svg.ts';

import type { EngineOptions, Host } from './engine.ts';
import { BlockDiagramEngine } from './engine.ts';
import { SvgRenderer } from './render/svg.ts';

/** Engine with the SVG renderer. */
export function createEngine(container: HTMLElement, host: Host,
                             options: Omit<EngineOptions, 'renderer'> & Partial<Pick<EngineOptions, 'renderer'>>): BlockDiagramEngine {
  return new BlockDiagramEngine(container, host, {
    renderer: (el, events) => new SvgRenderer(el, events),
    ...options,
  });
}

import type { FsmHost, FsmViewOptions } from './fsm-view.ts';
import { FsmView } from './fsm-view.ts';
import { SvgFsmRenderer } from './render/fsm-svg.ts';

/** State machine view with the SVG renderer. */
export function createFsmView(container: HTMLElement, host: FsmHost,
                              options: Omit<FsmViewOptions, 'renderer'> & Partial<Pick<FsmViewOptions, 'renderer'>>): FsmView {
  return new FsmView(container, host, { renderer: (el, events) => new SvgFsmRenderer(el, events), ...options });
}
