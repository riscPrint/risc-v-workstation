/** Map integer simulator times to a bounded viewport without losing time precision. */
export function position(t:string, start:string, end:string, width=800):number {
  const lo=BigInt(start), span=BigInt(end)-lo;
  return span > 0n ? Number((BigInt(t)-lo)*BigInt(width*1000)/span)/1000 : 0;
}
export function lane(initial:string|null, changes:{time:string;value:string}[], start:string, end:string, width:number):SVGSVGElement {
  const ns='http://www.w3.org/2000/svg';
  const svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox',`0 0 ${width} 60`);svg.setAttribute('role','img');svg.setAttribute('aria-label','Wave value lane');
  const events=[{time:start,value:initial ?? 'unknown'},...changes];
  for(let i=0;i<events.length;i++) {
    const e=events[i], x=position(e.time,start,end,width), next=i+1<events.length?position(events[i+1].time,start,end,width):width;
    const path=document.createElementNS(ns,'path');
    path.setAttribute('d',`M ${x} 20 L ${Math.min(x+3,next)} 8 H ${Math.max(x,next-3)} L ${next} 20 L ${Math.max(x,next-3)} 32 H ${Math.min(x+3,next)} Z`);
    path.setAttribute('fill','none');path.setAttribute('stroke','currentColor');svg.append(path);
    const text=document.createElementNS(ns,'text');text.setAttribute('x',String(x+4));text.setAttribute('y','24');text.setAttribute('fill','currentColor');text.textContent=e.value;svg.append(text);
  }
  return svg;
}
