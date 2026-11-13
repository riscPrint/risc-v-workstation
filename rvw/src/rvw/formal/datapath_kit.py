"""Suggest designer-reviewed datapath bindings from captured design structure."""
import json
import re
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
        bindings, ambiguous = {}, {}
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
            'binding':{'top':module,'ports':bindings},'missing_roles':missing,
            'ambiguous_roles':ambiguous,'unbound_ports':extras,
            'width_consistent':len(widths)==1,'requires_confirmation':True,
            'review':['operation and signedness','operand/result formats','reset polarity',
                      'transaction protocol and latency','extra ports and constants','reference model and FP flags']})
    return {'schema':'rvw.datapath-kit/1','status':'needs_confirmation' if rows else 'no_candidates',
            'unit':unit,'width':width,'candidates':rows,'proof_ran':False,
            'scope':'name and port structure hints only; no operation or protocol is inferred'}


def run(args):
    from rvw.query.db import run_on, QueryError, default_db
    import sqlite3
    try:
        if any(getattr(args,n,None) for n in ('rtl','model','binding')):
            raise ValueError('--unit proposes a binding; it excludes --rtl, --model and --binding')
        report=run_on(args.db or default_db(),lambda db:propose(db,args.unit,args.width))
        out=Path(args.out)
        out.mkdir(parents=True,exist_ok=False)
        (out/'proposal.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2) if args.json else f"datapath: {report['status']} ({out/'proposal.json'})")
        return 0
    except (ValueError,OSError,QueryError,sqlite3.DatabaseError) as exc:
        print(f'datapath kit: {exc}')
        return 2
