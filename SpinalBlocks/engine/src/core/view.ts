// What the user is looking at: which module, which areas are collapsed, which bundles are open.
// Plain data so hosts can persist it (VS Code webview state, localStorage, URL).

export interface ViewOptions {
  /** Draw clock/reset/clock-enable nets. */
  showClocks: boolean;
  /** Draw nets that only carry when/switch conditions or mux selects. */
  showControl: boolean;
  /** Fold ports by bundle until a block side has at most this many ports. */
  maxPortsPerSide: number;
  /** Collapse areas automatically until the module shows at most this many blocks. */
  maxBlocks: number;
  /** Merge the wires between two blocks into one bus when there are at least this many (0 = never). */
  busThreshold: number;
}

export const defaultOptions: ViewOptions = {
  showClocks: false,
  showControl: true,
  maxPortsPerSide: 10,
  maxBlocks: 80,
  busThreshold: 3,
};

/** Per-module choices. Absent entries mean "automatic". */
export interface ModuleView {
  /** Area ids the user collapsed (true) or expanded (false). */
  areas: Record<string, boolean>;
  /** Port bundles the user opened (true) or closed (false), keyed by `<owner>|<group>`;
   *  owner is "" for the module's own ports, else the instance id. */
  bundles: Record<string, boolean>;
}

export interface ViewState {
  /** Instance names from the top module. */
  path: string[];
  options: ViewOptions;
  modules: Record<string, ModuleView>;
}

export function initialView(): ViewState {
  return { path: [], options: { ...defaultOptions }, modules: {} };
}

export function moduleView(state: ViewState, module: string): ModuleView {
  return state.modules[module] ?? { areas: {}, bundles: {} };
}

/** Returns a new state with one module's view changed. */
export function updateModuleView(state: ViewState, module: string, f: (v: ModuleView) => ModuleView): ViewState {
  const cur = moduleView(state, module);
  return { ...state, modules: { ...state.modules, [module]: f({ areas: { ...cur.areas }, bundles: { ...cur.bundles } }) } };
}
