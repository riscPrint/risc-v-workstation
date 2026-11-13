"""Refine a physical memory implementation against an explicit logical model."""
from copy import copy
import hashlib
import io
import contextlib
import json
from pathlib import Path
from .common import check_ident

ROLES = ('clock','reset','write_enable','write_address','write_data','read_address','read_data')


def validate(spec):
    allowed={'schema','word_width','address_width','read_latency','unwritten','reset_active','ports'}
    if set(spec)-allowed or spec.get('schema')!='rvw.memory-refinement/1':
        raise ValueError('expected rvw.memory-refinement/1 with supported fields only')
    w,a=spec['word_width'],spec['address_width']
    if type(w) is not int or not 1<=w<=64 or type(a) is not int or not 1<=a<=8:
        raise ValueError('word_width must be 1..64 and address_width 1..8')
    if type(spec.get('read_latency')) is not int or spec['read_latency'] not in (0,1):
        raise ValueError('read_latency must be 0 or 1')
    if spec.get('unwritten')!='zero' or spec.get('reset_active','high') not in ('high','low'):
        raise ValueError('declare unwritten=zero and a high or low reset')
    ports=spec['ports']
    if not isinstance(ports,dict) or set(ports)!=set(ROLES) or len(set(ports.values()))!=len(ROLES):
        raise ValueError('declare all seven distinct logical memory ports')
    for name in ports.values(): check_ident('memory port',name)
    return w,a,ports


def model(spec,top):
    w,a,p=validate(spec);check_ident('memory top',top)
    n=1<<a
    widths={'clock':1,'reset':1,'write_enable':1,'write_address':a,'write_data':w,'read_address':a,'read_data':w}
    declarations=[f"{'output reg' if role=='read_data' else 'input wire'} [{widths[role]-1}:0] {p[role]}" for role in ROLES]
    reset=('!' if spec.get('reset_active','high')=='low' else '')+p['reset']
    # Collision handling is explicit: read_latency=1 sees old data at a write
    # edge. The asynchronous model sees the new stored word after that edge.
    read=f"(valid[{p['read_address']}] ? words[{p['read_address']}] : {w}'d0)"
    body=[f'module {top}('+','.join(declarations)+');',f'reg [{w-1}:0] words [0:{n-1}];',
          f'reg [{n-1}:0] valid;',f'always @(posedge {p["clock"]}) begin',
          f'if ({reset}) valid <= 0; else if ({p["write_enable"]}) begin',
          f'words[{p["write_address"]}] <= {p["write_data"]};',f'valid[{p["write_address"]}] <= 1;', 'end end']
    if spec['read_latency']==0:
        body.append(f'always @* {p["read_data"]} = {read};')
    else:
        body.append(f'always @(posedge {p["clock"]}) if ({reset}) {p["read_data"]} <= 0; else {p["read_data"]} <= {read};')
    return '\n'.join([*body,'endmodule',''])


def run(args):
    out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=False)
    result=dict(schema='rvw.memory-refinement/1',status='inconclusive',
                scope='exact finite logical word memory against physical RTL; no shared initial RAM assumptions')
    try:
        if not args.gate or any(getattr(args,k,None) for k in ('gold','gold_rev','gate_rev','config','blackbox_contract','state_encoding','pair','output_map','latency_map')) or args.latency or args.settle or getattr(args,'sampled_events',False):
            raise ValueError('memory-spec requires explicit --gate files and excludes gold, generated revisions, cuts, mappings and latency overrides')
        raw=Path(args.memory_spec).read_bytes();spec=json.loads(raw);w,a,p=validate(spec)
        (out/'spec.json').write_bytes(raw)
        (out/'abstract.v').write_text(model(spec,args.top))
        result.update(spec=spec,spec_sha256=hashlib.sha256(raw).hexdigest(),
                      model_sha256=hashlib.sha256((out/'abstract.v').read_bytes()).hexdigest())
        proof=copy(args);proof.memory_spec=None
        proof.gold=[str(out/'abstract.v')];proof.out=str(out/'proof')
        proof.memory_map=True;proof.unmatched_state='prove'
        proof.clock=p['clock'];proof.reset=p['reset'];proof.reset_active=spec.get('reset_active','high')
        from .equiv import run as equiv
        with contextlib.redirect_stdout(io.StringIO()): equiv(proof)
        data=json.loads((out/'proof/result.json').read_text())
        result['proof']=data
        result['status']=data['status']
    except (OSError,ValueError,KeyError,TypeError) as exc:
        result['reason']=str(exc)
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2) if args.json else f"memory refinement: {result['status']} ({out/'result.json'})")
    return 0 if result['status']=='equivalent' else 1
