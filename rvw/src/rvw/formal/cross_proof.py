"""Two-clock Boolean implication in a discrete global-step formal model.

Inputs transition at global samples. Properties sample the settled values from
before each transition, as native timed replay does. No clock fairness is added.
"""
from argparse import Namespace
import json
import math
from pathlib import Path
import re

from rvw.common.proc import run_group
from .cross_clock import rewrite
from .temporal import Unsupported, lower


def monitor(row, step='$global_clock', simulation=False, activation=False):
    p = row['monitor']
    terms = row['terms']
    lines = [f'reg {p}_started=0, {p}_pending=0;',
             f'reg {p}_request=0, {p}_response=0;']
    for index, term in enumerate(terms):
        lines += [f'reg {p}_previous{index}=0;']
    edges = [f'(!{p}_previous{i} && {t["signal"]})' if t['edge']=='posedge'
             else f'({p}_previous{i} && !{t["signal"]})' for i,t in enumerate(terms)]
    lines += [f'wire {p}_born = {p}_started && {edges[0]} && {p}_request;',
              f'wire {p}_target = {p}_started && {edges[1]};',
              f'wire {p}_due = {p}_target && ({p}_pending' +
              (f' || {p}_born' if row['overlap'] else '') + ');']
    if not simulation:
        clocks = ' && '.join('!'+t['signal'] for t in terms)
        lines += [f'always @* if ($initstate) assume({clocks});']
    if simulation:
        check = f'if ({p}_due) $display("CHECK %0d", {p}_response);'
    elif activation:
        check = f'cover({p}_due);'
    else:
        check = f'if ({p}_due) assert({p}_response);'
    lines += [f'always @({step}) begin', check,
              f'  {p}_started <= 1;',
              f'  {p}_request <= !(!({row["antecedent"]}));',
              f'  {p}_response <= !(!({row["consequent"]}));']
    for i,t in enumerate(terms):
        lines += [f'  {p}_previous{i} <= {t["signal"]};']
    lines += [f'  {p}_pending <= {p}_target ? '+
              ("1'b0" if row['overlap'] else p+'_born')+
              f' : ({p}_pending || {p}_born);', 'end']
    return '\n'.join(lines)+'\n'


def prepare(source, top, activation=False):
    if '`' in source:
        raise Unsupported('preprocessor', 'use preprocessed source')
    stripped, rows = rewrite(source, top)
    if len(rows) != 1 or rows[0]['kind'] != 'assert':
        raise Unsupported('cross_proof_scope', 'one two-clock assert property per job')
    row = rows[0]
    if row['clock'] == row['target_clock']:
        raise Unsupported('cross_proof_clocks', 'two distinct top-level input clocks required')
    # Other property checks must not be silently stripped or counted as this job.
    if re.search(r'\b(assert|assume|cover)\s*(?:property\b|\()', stripped):
        raise Unsupported('cross_proof_scope', 'use a separate job for other checks')
    stripped, finite = lower(stripped)
    if finite:
        raise Unsupported('cross_proof_scope')
    for signal in ('tick','from','to'):
        stripped = stripped.replace(f'reg {row["monitor"]}_{signal}=0;', '')
    match = re.search(r'\bmodule\s+'+re.escape(top)+r'\b.*?\bendmodule\b', stripped,re.S)
    end = match.end()-len('endmodule')
    return stripped[:end]+monitor(row,activation=activation)+stripped[end:], row


def run(args):
    from .regression import run as regress
    from .common import check_ident
    check_ident('top', args.top)
    if args.depth < 1 or not math.isfinite(args.timeout) or args.timeout <= 0:
        raise ValueError('depth and timeout must be positive')
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    source = Path(args.source).read_text()
    rtl, row = prepare(source,args.top)
    (out/'input.sv').write_text(source)
    (out/'model.sv').write_text(rtl)
    # Check the actual elaborated ports rather than guessing from HDL syntax.
    with (out/'ports.log').open('w') as log:
        proc = run_group(['nice','-n','10','yosys','-Q','-T','-p',
                          'read_verilog -formal -sv model.sv; prep -top '+args.top+'; write_json ports.json'],
                         cwd=out,stdout=log,stderr=log,timeout=args.timeout)
    if proc.returncode:
        raise ValueError('cross-clock elaboration failed; see ports.log')
    ports = json.loads((out/'ports.json').read_text())['modules'][args.top]['ports']
    for term in row['terms']:
        port = ports.get(term['signal'],{})
        if port.get('direction') != 'input' or len(port.get('bits',[])) != 1:
            raise Unsupported('cross_proof_clock_port', term['signal'])
    activation = out/'activation'
    activation.mkdir()
    (activation/'model.sv').write_text(prepare(source,args.top,activation=True)[0])
    def job(mode):
        return f'[options]\nmode {mode}\ndepth {args.depth}\nmulticlock on\n\n[engines]\n'+args.engine.replace(':',' ')+f'\n\n[script]\nread_verilog -formal -sv model.sv\nprep -top {args.top}\n\n[files]\nmodel.sv\n'
    (out/'job.sby').write_text(job(args.mode))
    (activation/'job.sby').write_text(job('cover'))
    (out/'regress.toml').write_text('[[property]]\n'+f'id = "{row["id"]}"\ntop = "{args.top}"\n'
        'sby = "job.sby"\nactivation_sby = "activation/job.sby"\n'
        'assumptions = ["clock inputs initially low; global-step pre-update sampling; no clock fairness"]\n')
    return regress(Namespace(manifest=str(out/'regress.toml'),out=str(out/'proof'),jobs=1,
                             timeout=args.timeout,proof_cache=args.proof_cache,json=True))
