import { randomBytes } from 'node:crypto';
import * as vscode from 'vscode';
export function html(webview: vscode.Webview, dist: vscode.Uri, kind: 'block' | 'fsm' = 'block', test = false): string {
  const nonce = randomBytes(24).toString('base64');
  const uri = (file: string) => webview.asWebviewUri(vscode.Uri.joinPath(dist, file)).toString();
  // The worker imports only the blob made from packaged ELK. The empty-style hash lets the renderer
  // attach an empty stylesheet before filling it through CSSOM under a strict CSP.
  const csp = `default-src 'none'; script-src 'nonce-${nonce}' ${webview.cspSource} blob:; style-src ${webview.cspSource} 'nonce-${nonce}' 'sha256-47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU='; worker-src blob:; connect-src ${webview.cspSource}; img-src ${webview.cspSource} data: blob:;`;
  return `<!DOCTYPE html><html><head><meta charset="UTF-8"><meta http-equiv="Content-Security-Policy" content="${csp}"><meta name="viewport" content="width=device-width, initial-scale=1"><link rel="stylesheet" href="${uri('webview.css')}"></head><body data-test="${test}">
  <header><nav id="crumbs" aria-label="Instance breadcrumb"></nav><div id="toolbar" role="toolbar" aria-label="Diagram controls">
  ${kind === 'block' ? '<button id="up">Up</button>' : ''}<button id="fit">Fit</button>${kind === 'block' ? '<button id="collapse">Collapse areas</button><button id="expand">Expand areas</button><label><input id="clocks" type="checkbox">Clocks</label><label><input id="control" type="checkbox">Control nets</label><label><input id="labels" type="checkbox" checked>Net labels</label>' : '<label>Machine <select id="machines" aria-label="State machine"></select></label><label><input id="conditions" type="checkbox" checked>Conditions</label><label><input id="comments" type="checkbox">Comments</label>'}<button id="export">Save SVG</button><button id="png">Save PNG</button>
  </div><div id="busy" role="status" hidden>Computing layout…</div></header>
  <main><div id="canvas" data-worker="${uri('elk-worker.js')}" aria-label="Block diagram"></div><aside id="details" aria-label="Selection details" hidden></aside></main>
  <div id="menu" role="menu" hidden></div><div id="status" role="status"></div>
  <script nonce="${nonce}" src="${uri(kind === 'block' ? 'webview.js' : 'fsm-webview.js')}"></script></body></html>`;
}
