"""Suggest designer-reviewed datapath bindings from captured design structure."""
from copy import copy
import json
import re
import sys
from pathlib import Path

UNITS = ('mul','mulh','mulhu','mulhsu','div','divu','rem','remu',
         'fpu-add','fpu-mul','fpu-fma','fpu-div','fpu-sqrt','fpu-convert')
ROLES = {
 'a':('a','lhs','rs1','operand_a','input_a','cmd_a','numerator'),
 'b':('b','rhs','rs2','operand_b','input_b','cmd_b','denominator'),
 'c':('c','rs3','operand_c','input_c','cmd_c'),
 'y':('y','result','quotient','remainder','output_result','rsp_result'),
 'flags':('flags','fflags','exception_flags'),
 'rm':('rm','rounding','rounding_mode'),
 'clk':('clk','clock'), 'reset':('reset','rst'),
 'start':('start','cmd_valid','input_valid'),
 'done':('done','rsp_valid','output_valid'),
}


def propose(db, unit, width=None):
    if unit not in UNITS:
        raise ValueError('unknown datapath unit')
    floating = unit.startswith('fpu-')
    kind = unit[4:] if floating else ('mul' if unit.startswith('mul') else 'div')
    hints = {'mul':('mul','multiplier'), 'div':('div','divider'),
             'add':('add','adder'), 'fma':('fma','madd'), 'sqrt':('sqrt',),
             'convert':('convert','conversion','cvt')}[kind]
    rows = []
    for comp in db.conn.execute('SELECT id,path,module,class_name,name FROM components ORDER BY path'):
        cid,path,module,cls,name = comp
        areas = [r[0] for r in db.conn.execute('SELECT name FROM areas WHERE component_id=?',(cid,))]
        text = ' '.join(str(x or '') for x in (path,module,cls,name,*areas)).lower()
        matches = [hint for hint in hints if hint in text]
        if not matches:
            continue
        ports = [{'name':n,'direction':d,'width':w,'path':p} for n,d,w,p in db.conn.execute(
            "SELECT name,direction,width,path FROM signals WHERE component_id=? AND direction IN ('in','out','input','output') AND pruned=0 ORDER BY name",(cid,))]
        required = ['a','y'] + ([] if unit in ('fpu-sqrt','fpu-convert') else ['b'])
        if unit=='fpu-fma':
            required.append('c')
        if floating:
            required += ['rm','flags']
        roles = required + ['clk','reset','start','done']
        bindings, ambiguous, port_matches = {}, {}, {}
        for role in roles:
            direction = ('out','output') if role in ('y','flags','done') else ('in','input')
            names = []
            for port in ports:
                normal = re.sub(r'^(io_)','',port['name'].lower())
                aliases = ROLES[role]
                if role=='y' and unit.startswith('rem'):
                    aliases = ('y','result','remainder','output_result','rsp_result')
                elif role=='y' and unit.startswith('div'):
                    aliases = ('y','result','quotient','output_result','rsp_result')
                expected = 1 if role in ('clk','reset','start','done') else 3 if role=='rm' else 5 if role=='flags' else width
                if normal in aliases and port['direction'] in direction and (expected is None or port['width']==expected):
                    names.append(port['name'])
            if len(names)==1:
                bindings[role]=names[0]
                port = next(p for p in ports if p['name']==names[0])
                port_matches[role] = dict(port=names[0], path=port['path'], direction=port['direction'],
                                          width=port['width'], criterion=('exact alias and direction; width unconstrained' if expected is None else 'exact alias, direction and requested width'))
            elif names:
                ambiguous[role]=names
        # Never assign one physical port to two reference arguments.
        duplicates = {n for n in bindings.values() if list(bindings.values()).count(n)>1}
        for role in list(bindings):
            if bindings[role] in duplicates:
                ambiguous[role]=[bindings.pop(role)]
        extras = [p['name'] for p in ports if p['name'] not in bindings.values()]
        missing = [r for r in required if r not in bindings]
        widths = {p['width'] for p in ports if p['name'] in [bindings.get(r) for r in ('a','b','c','y')]}
        rows.append({'component':path,'module':module,'evidence':{'name_hints':matches,'areas':areas,'ports':ports},
            'binding':{'top':module,'ports':bindings},'port_matches':{r:v for r,v in port_matches.items() if r in bindings},'missing_roles':missing,
            'ambiguous_roles':ambiguous,'unbound_ports':extras,
            'width_consistent':len(widths)==1,'requires_confirmation':True,
            'review':['operation and signedness','operand/result formats','reset polarity',
                      'transaction protocol and latency','extra ports and constants','reference model and FP flags']})
    return {'schema':'rvw.datapath-kit/1','status':'needs_confirmation' if rows else 'no_candidates',
            'unit':unit,'width':width,'candidates':rows,'proof_ran':False,
            'scope':'name and port structure hints only; no operation or protocol is inferred'}


def select(report, component=None):
    candidates = [c for c in report['candidates'] if component is None or c['component']==component]
    if len(candidates) != 1:
        raise ValueError('confirmation needs one candidate; select its --component path or supply an edited --binding')
    candidate = candidates[0]
    if candidate['missing_roles'] or candidate['ambiguous_roles']:
        raise ValueError('missing or ambiguous required roles need an edited --binding')
    return candidate['binding']


def describe(report):
    lines = [f"datapath: {report['status']}"]
    for c in report['candidates']:
        lines.append(f"component {c['component']} (top {c['module']})")
        for role, match in c['port_matches'].items():
            lines.append(f"  {role} <- {match['port']}: {match['direction']} {match['width']} bits; "
                         f"{match['criterion']}; {match['path']}")
        for label in ('missing_roles', 'ambiguous_roles', 'unbound_ports'):
            if c[label]: lines.append(f"  {label}: {c[label]}")
    return '\n'.join(lines)


def run(args):
    from rvw.query.db import run_on, QueryError, default_db
    import sqlite3
    try:
        confirm = getattr(args, 'confirm', False)
        if not confirm and any(getattr(args,n,None) for n in ('rtl','model','binding')):
            raise ValueError('--unit proposes a binding; proof inputs require --confirm')
        if confirm and (not args.rtl or not args.model or args.width is None):
            raise ValueError('--confirm requires --rtl, --model and --width')
        report=run_on(args.db or default_db(),lambda db:propose(db,args.unit,args.width))
        binding = None
        if confirm:
            binding = json.loads(Path(args.binding).read_text()) if args.binding else select(report, getattr(args,'component',None))
            if not isinstance(binding, dict) or 'top' not in binding or 'ports' not in binding:
                raise ValueError('edited binding needs top and ports')
            report['confirmation'] = {'binding': binding, 'source': 'edited binding' if args.binding else 'selected proposal'}
        out=Path(args.out)
        out.mkdir(parents=True,exist_ok=False)
        (out/'proposal.json').write_text(json.dumps(report,indent=2)+'\n')
        if not confirm:
            print(json.dumps(report,indent=2) if args.json else describe(report))
            return 0
        print(describe(report), file=sys.stderr if args.json else sys.stdout)
        print('confirmed binding: ' + json.dumps(binding, sort_keys=True), file=sys.stderr if args.json else sys.stdout)
        path = out/'confirmed-binding.json'
        path.write_text(json.dumps(binding,indent=2)+'\n')
        proof = copy(args)
        proof.unit = None; proof.confirm = False; proof.component = None
        proof.binding = str(path.resolve()); proof.out = str(out/'proof')
        from .datapath import run as prove
        return prove(proof)
    except (ValueError,OSError,QueryError,sqlite3.DatabaseError) as exc:
        print(f'datapath kit: {exc}')
        return 2
