const MAX_TIME = 2n ** 63n - 1n;
export function isTime(value: unknown): value is string {
  return typeof value === 'string' && /^\d+$/.test(value) && value.length <= 19 && BigInt(value) <= MAX_TIME;
}
export type Request = {op:'open'} | {op:'select'; signal:string; time:string; end?:string} | {op:'source'; file:string; line:number} | {op:'trace'; signal:string; time:string};
export function isRequest(v: unknown): v is Request {
  if (!v || typeof v !== 'object') return false;
  const a = v as Record<string, unknown>;
  if (a.op === 'open') return true;
  if (a.op === 'source') return typeof a.file === 'string' && Number.isSafeInteger(a.line) && Number(a.line) > 0;
  return (a.op === 'select' || a.op === 'trace') && typeof a.signal === 'string' && a.signal.trim().length > 0 && isTime(a.time) &&
    (a.end === undefined || (isTime(a.end) && BigInt(a.end) >= BigInt(a.time)));
}
export const body = `<header><label>Signal <input id="signal" list="signals"></label><datalist id="signals"></datalist>
<label>Time <input id="time" value="0" inputmode="numeric"></label><button id="jump">Jump</button><button id="trace">Trace active driver</button></header>
<p id="status" role="status"></p><main><section aria-labelledby="wave-heading"><h2 id="wave-heading">Indexed wave</h2><div id="wave"></div></section>
<section aria-labelledby="source-heading"><h2 id="source-heading">Scala source</h2><div id="source"></div></section><section aria-labelledby="diagram-heading"><h2 id="diagram-heading">SpinalBlocks</h2><div id="diagram"></div></section>
<section aria-labelledby="dependencies-heading"><h2 id="dependencies-heading">Dependency trace</h2><div id="dependencies"></div></section></main>`;
