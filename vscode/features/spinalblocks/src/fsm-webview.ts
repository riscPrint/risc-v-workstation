import { createFsmView, type FsmDetails } from '../../../../SpinalBlocks/engine/src/index.ts';
import { workerLayout } from '../../../../SpinalBlocks/engine/src/elk.ts';
import { isToWebview, type FromWebview, type ToWebview } from './protocol';

declare function acquireVsCodeApi(): {postMessage(value: FromWebview): void; getState(): SavedFsm | undefined; setState(value: SavedFsm): void};
interface SavedFsm { module: string; fsm: string; conditions: boolean; comments: boolean }
const vscode = acquireVsCodeApi();
async function main(): Promise<void> {
  const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
  const canvas = $('canvas'), status = $('status'), menu = $('menu'), details = $('details');
  const picker = $<HTMLSelectElement>('machines');
  const post = (message: FromWebview) => vscode.postMessage(message);
  const theme = () => document.body.classList.contains('vscode-light') || document.body.classList.contains('vscode-high-contrast-light') ? 'light' as const : 'dark' as const;
  let saved = vscode.getState(), loads = 0, failed = false, loaded = false;
  const response = await fetch(canvas.dataset.worker!);
  if (!response.ok) throw new Error(`Could not load ELK worker: ${response.status}`);
  const workerUrl = URL.createObjectURL(new Blob([await response.text()], {type:'text/javascript'}));
  function button(text: string, action: () => void): HTMLButtonElement {
    const button = document.createElement('button'); button.textContent = text; button.onclick = action; return button;
  }
  const openSource = (loc: NonNullable<FsmDetails['loc']>) => post({type:'openSource', loc});
  const view = createFsmView(canvas, {
    openSource,
    selectionChanged(value) {
      details.replaceChildren(); details.hidden = !value;
      if (!value) return;
      const title = document.createElement('h3'); title.textContent = value.title;
      const kind = document.createElement('p'); kind.textContent = value.kind;
      details.append(button('Close', () => {details.hidden = true;}), title, kind);
      if (value.loc) details.append(button(`Open Source (${value.loc.line})`, () => openSource(value.loc!)));
      for (const t of value.transitions.slice(0,200)) { const row = document.createElement('p'); row.textContent = `${t.from ?? 'any'} → ${t.to ?? '?'}${t.condition ? `: ${t.condition}` : ''}${t.comment ? ` // ${t.comment}` : ''}`; details.append(row); }
    },
    contextMenu(value, x, y) {
      menu.replaceChildren();
      if (value?.loc) menu.append(button('Open Source', () => openSource(value.loc!)));
      menu.hidden = !menu.childElementCount;
      menu.style.left = `${Math.max(0, Math.min(x, innerWidth-menu.offsetWidth))}px`;
      menu.style.top = `${Math.max(0, Math.min(y, innerHeight-menu.offsetHeight))}px`;
    },
    busy(value) { $('busy').hidden = !value; canvas.setAttribute('aria-busy', String(value)); post({type:'busy', value}); },
    error(error) { failed = true; status.textContent = error.message; post({type:'error', message:error.message}); },
  }, {layout:workerLayout(workerUrl)});
  function report(): void { if (!loaded || failed) return; post({type:'rendered', path:[], blocks:view.currentScene?.states.length ?? 0, theme:theme(), loads, fsm:view.shown?.fsm.id}); }
  function persist(): void {
    if (!view.shown) return;
    saved = {module:view.shown.module, fsm:view.shown.fsm.id, conditions:view.fsmOptionsValue.showConditions, comments:view.fsmOptionsValue.showComments};
    vscode.setState(saved);
  }
  function sync(): void {
    picker.value = JSON.stringify([view.shown?.module, view.shown?.fsm.id]);
    $<HTMLInputElement>('conditions').checked = view.fsmOptionsValue.showConditions;
    $<HTMLInputElement>('comments').checked = view.fsmOptionsValue.showComments;
    $('crumbs').textContent = view.shown ? `${view.shown.module} / ${view.shown.fsm.name}` : 'No state machines in this design';
  }
  let queue = Promise.resolve();
  function run(action: () => Promise<void> | void): void {
    queue = queue.then(async () => {
      failed = false; await action();
      if (!failed) {persist(); sync(); status.textContent = view.shown ? `${view.shown.fsm.name} · ${view.currentScene?.states.length ?? 0} states` : 'No state machines in this design'; report();}
    }).catch(error => {status.textContent = String(error); post({type:'error', message:String(error)});});
  }
  async function show(module: string, fsm: string): Promise<void> {
    if (view.shown?.module !== module || view.shown.fsm.id !== fsm) { details.hidden = true; await view.show(module, fsm); }
  }
  async function exportImage(format: 'svg' | 'png'): Promise<void> {
    if (!view.currentScene) return;
    const name = `${view.shown!.module}-${view.shown!.fsm.name}`;
    if (format === 'svg') post({type:'export', svg:view.exportSvg(), name});
    else post({type:'exportPng', bytes:await (await view.exportPng(2)).arrayBuffer(), name});
  }
  view.setRenderOptions({theme:theme()});
  new MutationObserver(() => {view.setRenderOptions({theme:theme()}); report();}).observe(document.body, {attributes:true, attributeFilter:['class']});
  window.addEventListener('message', (event: MessageEvent<unknown>) => {
    if (!isToWebview(event.data)) return;
    const message: ToWebview = event.data;
    run(async () => {
      switch (message.type) {
        case 'load': {
          loads++; await view.setDesign(new Uint8Array(message.bytes));
          const entries = view.list(); picker.replaceChildren();
          canvas.hidden = entries.length === 0;
          for (const id of ['fit','export','png']) $<HTMLButtonElement>(id).disabled = entries.length === 0;
          for (const entry of entries) {const option = document.createElement('option'); option.value = JSON.stringify([entry.module,entry.fsm.id]); option.textContent = `${entry.module} / ${entry.fsm.name}`; picker.append(option);}
          const entry = entries.find(e => e.module === saved?.module && e.fsm.id === saved.fsm) ?? entries[0];
          await view.setOptions({showConditions:saved?.conditions ?? true, showComments:saved?.comments ?? false});
          if (entry) await show(entry.module, entry.fsm.id);
          loaded = true;
          break;
        }
        case 'showFsm': await show(message.module, message.fsm); break;
        case 'showLocation': {
          const found = view.showLocation(message.file, message.line);
          if (document.body.dataset.test === 'true') post({type:'selected', file:message.file, line:message.line, found, kind:'fsm'});
          break;
        }
        case 'exportImage': await exportImage(message.format); break;
        case 'openModuleSource': { const loc = view.shown?.fsm.loc; if (loc) openSource(loc); break; }
      }
    });
  });
  picker.onchange = () => run(async () => { const [module, fsm] = JSON.parse(picker.value) as [string,string]; await show(module, fsm); });
  $('fit').onclick = () => view.fit();
  $<HTMLInputElement>('conditions').onchange = event => run(() => view.setOptions({showConditions:(event.target as HTMLInputElement).checked}));
  $<HTMLInputElement>('comments').onchange = event => run(() => view.setOptions({showComments:(event.target as HTMLInputElement).checked}));
  $('export').onclick = () => run(() => exportImage('svg'));
  $('png').onclick = () => run(() => exportImage('png'));
  document.addEventListener('click', event => {if (!menu.contains(event.target as Node)) menu.hidden = true;});
  menu.addEventListener('click', () => {menu.hidden = true;});
  document.addEventListener('keydown', event => {if (event.key === 'Escape') menu.hidden = true;});
  post({type:'ready'});
}
void main().catch(error => vscode.postMessage({type:'error', message:String(error)}));
