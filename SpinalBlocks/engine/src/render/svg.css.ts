// Stylesheets of the SVG renderers. Everything is scoped under `.sb-root` (the renderer's own element) or
// `.sb-svg` (the drawing, also used by exported SVGs).
//
// The look follows Sigasi's diagrams: a white sheet, dark 1 px outlines, solid port triangles, light
// fills, thin wires for single bits and thick ones for buses.
//
// Colours are CSS custom properties. Hosts override any `--sb-<name>` on the container or an ancestor
// (a VS Code webview maps them to `--vscode-*` theme colours); unset ones fall back to the defaults
// below for the current light/dark theme. Rules read the private `--_sb-<name>` copies.

/** name -> [light default, dark default]. Public variable: `--sb-<name>`. */
export const themeVars: Record<string, [string, string]> = {
  'bg': ['#ffffff', '#1e1e1e'],
  'text': ['#1f2328', '#d4d4d4'],
  'text-muted': ['#59636e', '#9da5ae'],
  // Module frame
  'frame-fill': ['#ffffff', '#1e1e1e'],
  'frame-header': ['#f0f2f4', '#2a2d31'],
  'frame-stroke': ['#3d444d', '#8b949e'],
  'frame-title': ['#1f2328', '#e6e6e6'],
  // Blocks: one outline colour, light per-kind fills
  'inst-fill': ['#ffffff', '#252526'],
  'inst-header': ['#eef1f4', '#30343a'],
  'inst-stroke': ['#3d444d', '#a0a8b2'],
  'reg-fill': ['#fff8ec', '#2f2a20'],
  'reg-stroke': ['#4d4a42', '#a8a090'],
  'comb-fill': ['#f1f8f3', '#202b24'],
  'comb-stroke': ['#434a45', '#98a69c'],
  'mixed-fill': ['#f6f3fb', '#29252f'],
  'mixed-stroke': ['#47444d', '#a39cae'],
  'mem-fill': ['#fbf1f1', '#30242a'],
  'mem-stroke': ['#4d4446', '#ae9ca0'],
  'logic-fill': ['#f5f6f8', '#26292d'],
  'logic-stroke': ['#454b52', '#a0a8b2'],
  'area-fill': ['#f3f5f7', '#26292d'],
  'area-stroke': ['#57606a', '#8b949e'],
  'glyph': ['#3d444d', '#b7bdc4'],
  // Ports
  'port-in-fill': ['#24292f', '#d0d7de'],
  'port-out-fill': ['#24292f', '#d0d7de'],
  'port-inout-fill': ['#24292f', '#d0d7de'],
  'marker-fill': ['#24292f', '#c9d1d9'],
  // Wires
  'edge': ['#3d444d', '#9aa3ad'],
  'edge-control': ['#7d858f', '#7c858f'],
  'edge-clock': ['#7a4fbf', '#b392f0'],
  'edge-label': ['#59636e', '#9da5ae'],
  // Controls, highlight, selection
  'control': ['#57606a', '#9da5ae'],
  'control-fill': ['#ffffff', '#1e1e1e'],
  'highlight': ['#0969da', '#4ea1ff'],
  'select': ['#0550ae', '#79c0ff'],
  // Tooltip
  'tip-bg': ['#ffffff', '#252526'],
  'tip-text': ['#1f2328', '#d4d4d4'],
  'tip-border': ['#d0d7de', '#454545'],
  // State machines
  'state-fill': ['#ffffff', '#252526'],
  'state-stroke': ['#3d444d', '#a0a8b2'],
  'state-bad': ['#c62828', '#f47067'],
  'state-unused-fill': ['#e9a7a7', '#5c2b2b'],
  'transition': ['#3d444d', '#a0a8b2'],
  'condition': ['#1f2328', '#d4d4d4'],
  'comment': ['#6e7781', '#8b949e'],
};

const v = (name: string) => `var(--_sb-${name})`;

function varRules(): string[] {
  const decl = (i: 0 | 1) => Object.entries(themeVars).map(([k, d]) => `--_sb-${k}:var(--sb-${k},${d[i]})`).join(';');
  return [`.sb-root{${decl(0)}}`, `.sb-root.sb-dark{${decl(1)}}`];
}

/** Rules shared by both diagrams: text, module/FSM frame, controls, hit areas. */
function commonRules(): string[] {
  return [
    `.sb-svg text{fill:${v('text')};pointer-events:none}`,
    `.sb-svg .sb-frame{fill:${v('frame-fill')};stroke:${v('frame-stroke')};stroke-width:1}`,
    `.sb-svg .sb-fhead{fill:${v('frame-header')};stroke:${v('frame-stroke')};stroke-width:1}`,
    `.sb-svg .sb-ftitle{fill:${v('frame-title')};font-weight:600}`,
    `.sb-svg .sb-sub{fill:${v('text-muted')}}`,
    `.sb-svg .sb-title{font-weight:600}`,
    `.sb-svg .sb-hit{fill:none;visibility:hidden;pointer-events:all}`,
    // Controls (chevrons, bundle +/-, open module)
    `.sb-svg .sb-ctl{cursor:pointer}`,
    `.sb-svg .sb-ctl>rect{fill:${v('control-fill')};stroke:${v('control')};stroke-width:1}`,
    `.sb-svg .sb-ctl>path{fill:none;stroke:${v('control')};stroke-width:1.2;stroke-linecap:round;stroke-linejoin:round}`,
    `.sb-svg .sb-ctl>path.sb-chev{fill:${v('control')};stroke:none}`,
    `.sb-svg .sb-ctl>.sb-hit{fill:none}`,
    `.sb-svg .sb-ctl:hover>rect{stroke:${v('highlight')}}`,
    `.sb-svg .sb-ctl:hover>path{stroke:${v('highlight')}}`,
    `.sb-svg .sb-ctl:hover>path.sb-chev{fill:${v('highlight')}}`,
  ];
}

/** Rules of the block diagram (selectors start with `.sb-svg`); exported SVGs embed these. */
export function diagramRules(): string[] {
  const kinds = ['reg', 'comb', 'mixed', 'mem', 'logic'];
  return [
    ...commonRules(),
    // Blocks
    `.sb-svg .sb-box{stroke-width:1}`,
    `.sb-svg .sb-inst>.sb-box{fill:${v('inst-fill')};stroke:${v('inst-stroke')}}`,
    `.sb-svg .sb-inst>.sb-head{fill:${v('inst-header')};stroke:none}`,
    `.sb-svg .sb-inst>.sb-sep{stroke:${v('inst-stroke')};stroke-width:1}`,
    ...kinds.map(k => `.sb-svg .sb-${k}>.sb-box{fill:${v(`${k}-fill`)};stroke:${v(`${k}-stroke`)}}`),
    `.sb-svg .sb-area>.sb-box{fill:${v('area-fill')};stroke:${v('area-stroke')}}`,
    // Expanded areas: dashed containers, like Sigasi's generate blocks.
    `.sb-svg .sb-compound>.sb-box{fill:none;stroke:${v('area-stroke')};stroke-dasharray:4 3}`,
    `.sb-svg .sb-compound>.sb-title{fill:${v('text-muted')}}`,
    `.sb-svg .sb-glyph{fill:none;stroke:${v('glyph')};stroke-width:1}`,
    `.sb-svg .sb-assign{fill:${v('glyph')};font-weight:700}`,
    // Ports
    `.sb-svg .sb-mark{fill:${v('marker-fill')};stroke:none}`,
    `.sb-svg .sb-mp>.sb-pm{stroke:none}`,
    `.sb-svg .sb-mp.sb-in>.sb-pm{fill:${v('port-in-fill')}}`,
    `.sb-svg .sb-mp.sb-out>.sb-pm{fill:${v('port-out-fill')}}`,
    `.sb-svg .sb-mp.sb-inout>.sb-pm{fill:${v('port-inout-fill')}}`,
    `.sb-svg .sb-mp>.sb-stub{fill:none;stroke:${v('edge')}}`,
    `.sb-svg .sb-mp>text{font-weight:500}`,
    // Edges
    `.sb-svg .sb-el{fill:none;stroke:${v('edge')};stroke-linejoin:miter;pointer-events:none}`,
    `.sb-svg .sb-eh{fill:none;stroke:#000;stroke-width:10;visibility:hidden;pointer-events:stroke}`,
    `.sb-svg .sb-jn{fill:${v('edge')};pointer-events:none}`,
    `.sb-svg .sb-ctrl>.sb-el{stroke:${v('edge-control')};stroke-dasharray:4 3}`,
    `.sb-svg .sb-ctrl>.sb-jn{fill:${v('edge-control')}}`,
    `.sb-svg .sb-clk>.sb-el{stroke:${v('edge-clock')}}`,
    `.sb-svg .sb-clk>.sb-jn{fill:${v('edge-clock')}}`,
    `.sb-svg .sb-elabel{fill:${v('edge-label')};paint-order:stroke;stroke:${v('bg')};stroke-width:3;stroke-linejoin:round}`,
    // Hover, highlight, selection
    `.sb-svg .sb-e:hover>.sb-el{stroke:${v('highlight')}}`,
    `.sb-svg .sb-e.sb-hl>.sb-el,.sb-svg .sb-mp.sb-hl>.sb-stub{stroke:${v('highlight')}}`,
    `.sb-svg .sb-e.sb-hl>.sb-jn{fill:${v('highlight')}}`,
    `.sb-svg .sb-elabel.sb-hl{fill:${v('highlight')}}`,
    `.sb-svg .sb-blk.sb-hl>.sb-box{stroke:${v('highlight')};stroke-width:2}`,
    `.sb-svg .sb-mp.sb-hl>.sb-pm,.sb-svg .sb-bp.sb-hl>.sb-mark{fill:${v('highlight')}}`,
    `.sb-svg .sb-mp.sb-hl>text,.sb-svg .sb-bp.sb-hl>text{fill:${v('highlight')}}`,
    `.sb-svg .sb-dimming .sb-e:not(.sb-hl),.sb-svg .sb-dimming .sb-elabel:not(.sb-hl){opacity:.28}`,
    `.sb-svg .sb-dimming .sb-leaf:not(.sb-hl),.sb-svg .sb-dimming .sb-mp:not(.sb-hl){opacity:.5}`,
    `.sb-svg .sb-dimming .sb-bp:not(.sb-hl)>text{opacity:.6}`,
    `.sb-svg .sb-e.sb-sel>.sb-el{stroke:${v('select')};stroke-width:3px}`,
    `.sb-svg .sb-elabel.sb-sel{fill:${v('select')};font-weight:600}`,
    `.sb-svg .sb-blk.sb-sel>.sb-box{stroke:${v('select')};stroke-width:2.5}`,
    `.sb-svg .sb-mp.sb-sel>.sb-pm,.sb-svg .sb-bp.sb-sel>.sb-mark{fill:${v('select')}}`,
    `.sb-svg .sb-mp.sb-sel>text,.sb-svg .sb-bp.sb-sel>text{fill:${v('select')};font-weight:600}`,
    // Zoom levels and options
    `.sb-svg.sb-nolabels .sb-elabel,.sb-svg.sb-far .sb-elabel{display:none}`,
    // Far out, block titles keep a constant screen size (the renderer sets --sb-far-size) and edges fade.
    `.sb-svg.sb-farther .sb-inst>.sb-title,.sb-svg.sb-farther .sb-area>.sb-title{font-size:var(--sb-far-size);paint-order:stroke;stroke:${v('bg')};stroke-width:var(--sb-far-halo);stroke-linejoin:round}`,
    `.sb-svg.sb-farther .sb-e>.sb-el{opacity:.6}`,
    `.sb-svg.sb-farther .sb-bp>text,.sb-svg.sb-farther .sb-sub,.sb-svg.sb-farther .sb-ctl{display:none}`,
  ];
}

/** Rules of the state machine diagram; exported SVGs embed these. */
export function fsmRules(): string[] {
  return [
    ...commonRules(),
    `.sb-svg .sb-st>.sb-shape{fill:${v('state-fill')};stroke:${v('state-stroke')};stroke-width:1.2}`,
    `.sb-svg .sb-st>text{font-weight:500}`,
    `.sb-svg .sb-st.sb-dead>.sb-shape{stroke:${v('state-bad')};stroke-width:1.6}`,
    `.sb-svg .sb-st.sb-unused>.sb-shape{fill:${v('state-unused-fill')};stroke:${v('state-bad')};stroke-width:1.6}`,
    `.sb-svg .sb-tr>.sb-tl{fill:none;stroke:${v('transition')};stroke-width:1.2}`,
    `.sb-svg .sb-tr>.sb-ah,.sb-svg .sb-reset>.sb-ah,.sb-svg .sb-reset>circle{fill:${v('transition')};stroke:none}`,
    `.sb-svg .sb-reset>.sb-tl{fill:none;stroke:${v('transition')};stroke-width:1.2;stroke-dasharray:5 4}`,
    `.sb-svg .sb-tr.sb-unres>.sb-tl{stroke-dasharray:5 4}`,
    `.sb-svg .sb-eh{fill:none;stroke:#000;stroke-width:10;visibility:hidden;pointer-events:stroke}`,
    `.sb-svg .sb-tlabel>text{fill:${v('condition')};paint-order:stroke;stroke:${v('bg')};stroke-width:3;stroke-linejoin:round}`,
    `.sb-svg .sb-tlabel>text.sb-cmt{fill:${v('comment')};font-style:italic}`,
    `.sb-svg .sb-pseudo>rect{fill:${v('state-fill')};stroke:${v('text-muted')};stroke-width:1}`,
    `.sb-svg .sb-pseudo>text{fill:${v('text-muted')}}`,
    `.sb-svg .sb-unknown>text{fill:${v('text')};font-weight:600}`,
    // Hover, highlight, selection
    `.sb-svg .sb-tr:hover>.sb-tl{stroke:${v('highlight')}}`,
    `.sb-svg .sb-tr:hover>.sb-ah{fill:${v('highlight')}}`,
    `.sb-svg .sb-tr.sb-hl>.sb-tl{stroke:${v('highlight')};stroke-width:2}`,
    `.sb-svg .sb-tr.sb-hl>.sb-ah{fill:${v('highlight')}}`,
    `.sb-svg .sb-tlabel.sb-hl>text{fill:${v('highlight')}}`,
    `.sb-svg .sb-st.sb-hl>.sb-shape{stroke:${v('highlight')};stroke-width:2}`,
    `.sb-svg .sb-st:hover>.sb-shape{stroke:${v('highlight')}}`,
    `.sb-svg .sb-dimming .sb-tr:not(.sb-hl),.sb-svg .sb-dimming .sb-tlabel:not(.sb-hl){opacity:.28}`,
    `.sb-svg .sb-dimming .sb-st:not(.sb-hl),.sb-svg .sb-dimming .sb-reset,.sb-svg .sb-dimming .sb-pseudo{opacity:.5}`,
    `.sb-svg .sb-tr.sb-sel>.sb-tl{stroke:${v('select')};stroke-width:2.5}`,
    `.sb-svg .sb-tr.sb-sel>.sb-ah{fill:${v('select')}}`,
    `.sb-svg .sb-tlabel.sb-sel>text{fill:${v('select')}}`,
    `.sb-svg .sb-st.sb-sel>.sb-shape{stroke:${v('select')};stroke-width:2.5}`,
    `.sb-svg.sb-nolabels .sb-tlabel{display:none}`,
  ];
}

/** Rules for the root element, tooltip and live interaction, before the drawing rules. */
function viewBase(): string[] {
  return [
    ...varRules(),
    `.sb-root{position:relative;overflow:hidden;width:100%;height:100%;background:${v('bg')};user-select:none;-webkit-user-select:none;touch-action:none}`,
    `.sb-root>.sb-svg{display:block;width:100%;height:100%;cursor:grab;outline:none}`,
    `.sb-root>.sb-svg.sb-panning{cursor:grabbing}`,
    `.sb-svg .sb-blk,.sb-svg .sb-mp,.sb-svg .sb-bp,.sb-svg .sb-e,.sb-svg .sb-st,.sb-svg .sb-tr,.sb-svg .sb-tlabel{cursor:pointer}`,
    `.sb-root>.sb-svg.sb-panning *{cursor:grabbing}`,
    `.sb-root>.sb-tip{position:absolute;left:0;top:0;display:none;pointer-events:none;z-index:2;max-width:420px;padding:5px 8px;` +
      `background:${v('tip-bg')};color:${v('tip-text')};border:1px solid ${v('tip-border')};border-radius:4px;` +
      `box-shadow:0 2px 8px rgba(0,0,0,.18);font:12px/1.45 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;white-space:pre-wrap;word-break:break-word}`,
    `.sb-root>.sb-tip.sb-on{display:block}`,
    `.sb-root>.sb-tip>.sb-tip-title{font-weight:600}`,
  ];
}

/** Rules for the live block diagram. */
export function viewRules(): string[] {
  return [...viewBase(), ...diagramRules()];
}

/** Rules for the live state machine diagram. */
export function fsmViewRules(): string[] {
  return [...viewBase(), ...fsmRules()];
}
