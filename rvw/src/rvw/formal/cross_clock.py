"""Finite native replay of Boolean two-clock SVA implication.

A single replay-step process samples both domains before input updates. Counts
retain every request until the nearest eligible target-clock event.
"""
import re

from .sva import _expression, _group
from .temporal import Unsupported, split, unwrap
from .raw_events import parse, pulses

PREFIX='rvw_cross_'


def boolean(text):
    text=unwrap(text)
    _expression(text)
    if '$' in text:
        raise Unsupported('cross_clock_sampled_function')
    return text


def rewrite(source,top,simulation=False):
    from .property_names import expand
    source=expand(source,lambda body: body.count('@')>1)
    text=re.sub(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"',lambda m:' '*len(m[0]),source,flags=re.S)
    if PREFIX in text:
        raise Unsupported('reserved_identifier',PREFIX)
    edits,rows=[],[]
    for module in re.finditer(r'\bmodule\s+(\w+)\b.*?\bendmodule\b',text,re.S):
        for prop in re.finditer(r'\b(assert|assume|cover)\s+property\s*\(',module[0]):
            start=module.start()+prop.start()
            body,end=_group(text,module.start()+prop.end()-1)
            clock=re.match(r'\s*@\s*\(',body)
            if not clock:
                continue
            first,offset=_group(body,clock.end()-1)
            expr=unwrap(body[offset:])
            if '@' not in expr:
                continue
            if module[1]!=top:
                raise Unsupported('cross_clock_scope')
            parts=split(expr,r'\|->|\|=>')
            if len(parts)!=3:
                raise Unsupported('cross_clock_implication')
            second=re.match(r'@\s*\(',unwrap(parts[2]))
            if not second:
                raise Unsupported('cross_clock_target_event')
            rhs=unwrap(parts[2])
            target,finish=_group(rhs,second.end()-1)
            clocks=[parse(first),parse(target)]
            if any(len(terms)!=1 or terms[0]['edge']=='change' for terms in clocks):
                raise Unsupported('cross_clock_event', 'one posedge or negedge per clock')
            antecedent,consequent=boolean(parts[0]),boolean(rhs[finish:])
            semi=re.match(r'\s*;',text[end:])
            if not semi:
                raise Unsupported('action_block')
            label=re.search(r'\b(\w+)\s*:\s*$',text[module.start():start])
            name=label[1] if label else f'cross_clock_{len(rows)}'
            if label:
                start=module.start()+label.start()
            prefix=PREFIX+str(len(rows))
            row=dict(id=name,kind=prop[1],clock=clocks[0][0]['signal'],
                     target_clock=clocks[1][0]['signal'],clock_events=[first,target],
                     terms=[terms[0] for terms in clocks],monitor=prefix,
                     overlap=parts[1]=='|->', antecedent=antecedent, consequent=consequent)
            rows.append(row)
            declarations=f'reg {prefix}_tick=0, {prefix}_from=0, {prefix}_to=0;\n'
            if simulation:
                yes='cover' if prop[1]=='cover' else 'pass'
                no='miss' if prop[1]=='cover' else 'fail'
                emitted=declarations+f'''reg [63:0] {prefix}_pending=0;
reg [63:0] {prefix}_due=0;
reg {prefix}_born=0;
integer {prefix}_i;
always @(posedge {prefix}_tick) begin
  {prefix}_born = {prefix}_from && ((!(!({antecedent}))) === 1'b1);
  {prefix}_due = {prefix}_to ? ({prefix}_pending + {prefix+"_born" if row['overlap'] else "0"}) : 0;
  for ({prefix}_i=0; {prefix}_i<{prefix}_due; {prefix}_i={prefix}_i+1) begin
    if ((!(!({consequent}))) === 1'b1) $display("RVW_SVA {prefix} {prop[1]} {yes}");
    else $display("RVW_SVA {prefix} {prop[1]} {no}");
  end
  {prefix}_pending = {prefix}_to ? {"0" if row['overlap'] else prefix+"_born"} : ({prefix}_pending + {prefix}_born);
end
'''
            else:
                # Interface probing must not reinterpret two clocks as one
                # formal clock. The actual monitor is emitted only for replay.
                emitted=declarations
            edits.append((start,end+semi.end(),emitted+'\n'))
    for start,end,replacement in sorted(edits,reverse=True):
        source=source[:start]+replacement+source[end:]
    return source,rows


def schedule(rows,properties,inputs):
    bindings=[]
    for prop in properties:
        bindings += [dict(clock=prop['monitor']+'_from',terms=[prop['terms'][0]]),
                     dict(clock=prop['monitor']+'_to',terms=[prop['terms'][1]])]
    from .raw_events import validate
    validate(bindings,inputs)
    events=pulses(rows,bindings,inputs)
    return [(dict((binding['clock'],int(binding['clock'] in triggered)) for binding in bindings),
             [prop['monitor']+'_tick' for prop in properties
              if prop['monitor']+'_from' in triggered or prop['monitor']+'_to' in triggered])
            for triggered in events]
