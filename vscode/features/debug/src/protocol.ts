export type Request = {op:'open'} | {op:'select'; signal:string; time:string; end?:string} | {op:'source'; file:string; line:number} | {op:'trace'; signal:string; time:string};
export function isRequest(v: unknown): v is Request {
  if (!v || typeof v !== 'object') return false;
  const a = v as Record<string, unknown>;
  if (a.op === 'open') return true;
  if (a.op === 'source') return typeof a.file === 'string' && Number.isSafeInteger(a.line) && Number(a.line) > 0;
  return (a.op === 'select' || a.op === 'trace') && typeof a.signal === 'string' && /^\d+$/.test(String(a.time)) &&
    (a.end === undefined || /^\d+$/.test(String(a.end)));
}
export const body = `<header><label>Signal <input id="signal" list="signals"></label><datalist id="signals"></datalist>
<label>Time <input id="time" value="0" inputmode="numeric"></label><button id="jump">Jump</button><button id="trace">Trace active driver</button></header>
<p id="status" role="status"></p><main><section><h2>Indexed wave</h2><div id="wave"></div></section>
<section><h2>Scala source</h2><div id="source"></div></section><section><h2>SpinalBlocks</h2><div id="diagram"></div></section>
<section><h2>Dependency trace</h2><div id="dependencies"></div></section></main>`;
