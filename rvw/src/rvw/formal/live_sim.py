"""Finite native observations for eventual-response and Boolean until SVA.

Each activated request is counted. No finite deadline replaces eventuality.
Outstanding assertion or assumption obligations prevent a passing C1 result.
"""
import re

from .property_names import expand
from .raw_events import parse
from .sampled import emit,validate
from .sva import _group,_expression,_EXPR
from .temporal import Unsupported,split,unwrap

PREFIX='rvw_live_sim_'
MARKER=re.compile(r'\bs_eventually\b|\b(?:s_)?until(?:_with)?\b')


def rewrite(source,top,simulation=False):
    source=expand(source,lambda body: bool(MARKER.search(body)))
    text=re.sub(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"',lambda m:' '*len(m[0]),source,flags=re.S)
    if PREFIX in text:
        raise Unsupported('reserved_identifier',PREFIX)
    edits,rows=[],[]
    for module in re.finditer(r'\bmodule\s+(\w+)\b.*?\bendmodule\b',text,re.S):
        for prop in re.finditer(r'\b(assert|assume|cover)\s+property\s*\(',module[0]):
            start=module.start()+prop.start()
            body,end=_group(text,module.start()+prop.end()-1)
            if not MARKER.search(body):
                continue
            if module[1]!=top:
                raise Unsupported('native_liveness_scope')
            clock=re.match(r'\s*@\s*\(',body)
            if not clock:
                raise Unsupported('native_liveness_clock')
            event,offset=_group(body,clock.end()-1)
            terms=parse(event)
            expression=body[offset:].strip()
            disable=None
            inputs=[]
            dm=re.match(r'disable\s+iff\s*',expression)
            if dm:
                disable,finish=_group(expression,dm.end())
                _expression(disable)
                if '$' in disable:
                    raise Unsupported('native_disable_sampled')
                inputs=sorted({token[0] for token in _EXPR.finditer(disable)
                               if re.fullmatch(r'[A-Za-z_]\w*',token[0])})
                expression=expression[finish:].strip()
            parts=split(unwrap(expression),r'\|->|\|=>')
            if len(parts) not in (1,3):
                raise Unsupported('native_liveness_implication')
            request=unwrap(parts[0]) if len(parts)==3 else '1'
            nonoverlap=len(parts)==3 and parts[1]=='|=>'
            rhs=unwrap(parts[-1])
            eventual=re.fullmatch(r's_eventually\s+(.+)',rhs,re.S)
            if eventual:
                operator,left,right='s_eventually','1',unwrap(eventual[1])
            else:
                until=split(rhs,r'\b(?:s_)?until(?:_with)?\b')
                if len(until)!=3:
                    raise Unsupported('native_liveness_form')
                left,operator,right=until
            for value in (request,left,right):
                validate(value)
            semi=re.match(r'\s*;',text[end:])
            if not semi:
                raise Unsupported('action_block')
            label=re.search(r'\b(\w+)\s*:\s*$',text[module.start():start])
            name=label[1] if label else f'native_liveness_{len(rows)}'
            if label:
                start=module.start()+label.start()
            prefix=PREFIX+str(len(rows))
            row=dict(id=name,kind=prop[1],clock=prefix+'_tick',event=event.strip(),terms=terms,
                     operator=operator,nonoverlap=nonoverlap,monitor=prefix,
                     disable_iff=disable,disable_inputs=inputs)
            rows.append(row)
            declaration=f'reg {prefix}_tick=0;\n'
            if simulation:
                declaration+=monitor(prefix,request,left,right,operator,prop[1],nonoverlap,disable)
            edits.append((start,end+semi.end(),declaration+'\n'))
    for start,end,replacement in sorted(edits,reverse=True):
        source=source[:start]+replacement+source[end:]
    return source,rows


def monitor(prefix,request,left,right,operator,kind,nonoverlap,disable=None):
    history=[]
    values=[]
    for i,expression in enumerate((request,left,right)):
        value,lines=emit(expression,prefix+'_tick',prefix+'_sample'+str(i))
        history+=lines
        values.append(f'((!(!({value}))) === 1\'b1)')
    req,a,b=values
    success=b if not operator.endswith('_with') else f'({a} && {b})'
    # An eventual-response operand can remain false forever without a finite
    # failure. Until has a finite failure when its hold condition is false.
    failure="1'b0" if operator=='s_eventually' else f'!({a})'
    yes='cover' if kind=='cover' else 'pass'
    no='miss' if kind=='cover' else 'fail'
    delayed=f'reg {prefix}_delayed=0;\n' if nonoverlap else ''
    born=prefix+'_delayed' if nonoverlap else req
    update=f'  {prefix}_delayed = {req};\n' if nonoverlap else ''
    cancel=''
    sensitivity=f'posedge {prefix}_tick'
    before=after=''
    if disable is not None:
        cancel=(f"wire {prefix}_cancel = ((!(!({disable}))) === 1'b1);\n"
                f'reg [63:0] {prefix}_cancelled=0;\n')
        sensitivity+=f' or posedge {prefix}_cancel'
        outstanding=prefix+'_pending'+(' + '+prefix+'_delayed' if nonoverlap else '')
        before=(f'  if ({prefix}_cancel) begin\n'
                f'    {prefix}_cancelled = {prefix}_cancelled + {outstanding};\n'
                f'    {prefix}_pending = 0;\n'
                +(f'    {prefix}_delayed = 0;\n' if nonoverlap else '')+'  end else begin\n')
        after='  end\n'
    return '\n'.join(history)+'\n'+delayed+cancel+f'''reg [63:0] {prefix}_pending=0;
reg [63:0] {prefix}_total=0;
integer {prefix}_i;
always @({sensitivity}) begin
{before}  {prefix}_total = {prefix}_pending + {born};
  if ({success}) begin
    for ({prefix}_i=0; {prefix}_i<{prefix}_total; {prefix}_i={prefix}_i+1)
      $display("RVW_SVA {prefix} {kind} {yes}");
    {prefix}_pending = 0;
  end else if ({failure}) begin
    for ({prefix}_i=0; {prefix}_i<{prefix}_total; {prefix}_i={prefix}_i+1)
      $display("RVW_SVA {prefix} {kind} {no}");
    {prefix}_pending = 0;
  end else {prefix}_pending = {prefix}_total;
{update}{after}end
'''


def validate_events(rows,properties,inputs):
    """Current disable inputs must be stable across the property event slot."""
    from .raw_events import pulses
    bindings=[dict(clock=p['clock'],terms=p['terms']) for p in properties]
    events=pulses(rows,bindings,inputs)
    for prop in properties:
        deps=set(prop['disable_inputs'])
        if not deps<=inputs.keys():
            raise Unsupported('native_disable_inputs','use top-level input controls')
        if deps & {term['signal'] for term in prop['terms']}:
            raise Unsupported('native_disable_clock','disable condition must not read its event input')
    previous={}
    for index,(_,changes) in enumerate(rows):
        changed={name for name,value in changes.items() if previous.get(name)!=value.lower()}
        for prop in properties:
            if prop['clock'] in events[index] and changed & set(prop['disable_inputs']):
                raise Unsupported('native_disable_timestamp','change disable inputs separately from property events')
        previous.update({name:value.lower() for name,value in changes.items()})
