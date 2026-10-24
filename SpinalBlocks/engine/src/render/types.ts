// Contract between the engine and a renderer. A renderer draws a Scene and reports user gestures;
// it holds no design state of its own.

import type { Scene } from '../core/scene.ts';
import type { FsmScene } from '../core/fsm.ts';

/** Something in the diagram the user can point at. */
export type Target =
  | { kind: 'block'; id: string }
  | { kind: 'modulePort'; id: string }
  | { kind: 'blockPort'; block: string; port: string }
  | { kind: 'edge'; id: string };

export interface RendererEvents {
  /** Single click (null = background). */
  select(target: Target | null): void;
  /** Pointer enters/leaves something (null = nothing). */
  hover(target: Target | null): void;
  /** Double click: descend into an instance, toggle an area, open/close a bundle. */
  activate(target: Target): void;
  /** Click on an area's collapse chevron. */
  toggleArea(blockId: string): void;
  /** Click on a bundle port's expand control. owner = "" for module ports, else the block id. */
  toggleBundle(owner: string, portId: string): void;
  /** Right click / context menu request, in client coordinates. */
  contextMenu(target: Target | null, clientX: number, clientY: number): void;
  /** Click on an instance's "open" glyph: show the instance's module (Sigasi: Open Module). */
  open(blockId: string): void;
}

export interface RenderOptions {
  showEdgeLabels: boolean;
  /** Colour scheme; renderers use CSS variables so hosts (VS Code themes) can override them. */
  theme: 'light' | 'dark';
}

export interface Viewport { x: number; y: number; zoom: number }

export interface Renderer {
  /** Replace the drawing. Keeps the viewport when `keepViewport` (same module redrawn), else fits. */
  render(scene: Scene, keepViewport: boolean): void;
  setOptions(options: Partial<RenderOptions>): void;
  /** Emphasise these targets and everything connected to them (edges: whole edge + both ends). */
  highlight(targets: Target[]): void;
  /** Selection outline. */
  select(targets: Target[]): void;
  fit(): void;
  /** Pan/zoom so the target is visible and centred. */
  reveal(target: Target): void;
  getViewport(): Viewport;
  setViewport(v: Viewport): void;
  /** Standalone SVG document of the current drawing (inline styles, no external CSS). */
  exportSvg(): string;
  /** PNG of the whole drawing at `scale` (1 = scene pixels). */
  exportPng(scale?: number): Promise<Blob>;
  dispose(): void;
}

// ---------------------------------------------------------------------------------------------
// State machine diagrams

export type FsmTarget = { kind: 'state'; name: string } | { kind: 'transition'; id: string };

export interface FsmRendererEvents {
  select(target: FsmTarget | null): void;
  hover(target: FsmTarget | null): void;
  /** Double click: open the source (Sigasi). */
  activate(target: FsmTarget): void;
  contextMenu(target: FsmTarget | null, clientX: number, clientY: number): void;
}

export interface FsmRenderer {
  render(scene: FsmScene, keepViewport: boolean): void;
  setOptions(options: Partial<RenderOptions>): void;
  /** A state with its transitions, or a transition with its two states. */
  highlight(targets: FsmTarget[]): void;
  select(targets: FsmTarget[]): void;
  fit(): void;
  reveal(target: FsmTarget): void;
  getViewport(): Viewport;
  setViewport(v: Viewport): void;
  exportSvg(): string;
  exportPng(scale?: number): Promise<Blob>;
  dispose(): void;
}
