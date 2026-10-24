// A laid-out diagram: absolute positions for everything a renderer draws. Renderer-independent.

import type { VBlock, VEdge, VPort, ViewGraph } from './graph.ts';

export interface Point { x: number; y: number }

/** Sizes shared by layout and rendering, so text fits the boxes the layout made. */
export interface Metrics {
  fontFamily: string;
  /** Average glyph width (px) per font size unit; width ≈ chars * size * charWidth. */
  charWidth: number;
  titleSize: number;
  sublabelSize: number;
  portLabelSize: number;
  edgeLabelSize: number;
  /** Instance header height (title + sublabel). */
  headerHeight: number;
  /** Vertical distance between instance ports. */
  portPitch: number;
  /** Port marker size. */
  portSize: number;
  /** Space above an expanded area's children for its title. */
  areaHeader: number;
  modulePortHeight: number;
}

export const defaultMetrics: Metrics = {
  fontFamily: 'ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif',
  charWidth: 0.58,
  titleSize: 13,
  sublabelSize: 11,
  portLabelSize: 11,
  edgeLabelSize: 10,
  headerHeight: 40,
  portPitch: 18,
  portSize: 8,
  areaHeader: 30,
  modulePortHeight: 20,
};

export function textWidth(text: string, size: number, m: Metrics = defaultMetrics): number {
  return Math.ceil(text.length * size * m.charWidth);
}

/** A port of the module itself, drawn at the left (inputs) or right (outputs) of the diagram. */
export interface SceneModulePort {
  id: string;
  x: number; y: number; width: number; height: number;
  side: 'left' | 'right';
  port: VPort;
}

/** A port on an instance block; (x, y) is the connection point on the block border. */
export interface SceneBlockPort {
  id: string;
  x: number; y: number;
  side: 'left' | 'right';
  port: VPort;
}

export interface SceneBlock {
  id: string;
  x: number; y: number; width: number; height: number;
  /** Nesting depth (0 = module body); parents come before children in Scene.blocks. */
  depth: number;
  block: VBlock;
  ports: SceneBlockPort[];
}

export interface SceneEdge {
  id: string;
  /** Orthogonal polyline, absolute coordinates; one entry per ELK section. */
  sections: Point[][];
  /** Junction points where branches of the same net split. */
  junctions: Point[];
  /** Suggested label anchor (left end of the longest horizontal run), or null if no room. */
  labelAt: Point | null;
  edge: VEdge;
}

export interface Scene {
  module: string;
  width: number;
  height: number;
  ports: SceneModulePort[];
  blocks: SceneBlock[];
  edges: SceneEdge[];
  graph: ViewGraph;
  metrics: Metrics;
}
