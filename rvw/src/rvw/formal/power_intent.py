"""Explicit project low-power intent. This generator does not infer UPF semantics."""
import json
import re
from pathlib import Path
from . import power_checks


def validate(obj):
    if obj.get('schema') != 'rvw.power-intent/1' or obj.get('event_model') != 'always_on_sampled':
        raise ValueError('require rvw.power-intent/1 and always_on_sampled event model')
    if set(obj) - {'schema', 'event_model', 'domains', 'dft'}:
        raise ValueError('unsupported intent attribute')
    if not obj.get('domains'):
        raise ValueError('declare power domains')
    names = set()
    for d in obj['domains']:
        if set(d) != {'name', 'width', 'wake_bound', 'checks', 'states', 'transitions', 'initial'}:
            raise ValueError('unsupported or missing domain attribute')
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', d['name']) or d['name'] in names:
            raise ValueError('invalid or duplicate domain name')
        names.add(d['name'])
        if not 1 <= d['width'] <= 64 or not 1 <= d['wake_bound'] <= 1024:
            raise ValueError('invalid state width or wake bound')
        if not d['checks'] or set(d['checks']) - set(power_checks.NAMES) or len(d['checks']) != len(set(d['checks'])):
            raise ValueError('unknown or duplicate power check')
        if not d['states'] or d['initial'] not in d['states']:
            raise ValueError('declare initial supply state')
        for s in d['states'].values():
            if set(s) != {'power_good', 'isolated'} or any(type(v) is not bool for v in s.values()):
                raise ValueError('state needs boolean power_good and isolated')
            if not s['power_good'] and not s['isolated']:
                raise ValueError('off state needs isolation')
        if not d['transitions'] or any(len(t) != 2 or any(s not in d['states'] for s in t) for t in d['transitions']):
            raise ValueError('invalid declared supply transition')
    for path in obj.get('dft', []):
        if set(path) != {'signal', 'role', 'controllability', 'observability'}:
            raise ValueError('declare DFT access constraints')
        if path['role'] not in ('test_clock', 'test_reset', 'scan_mode', 'test_enable', 'access'):
            raise ValueError('unknown DFT role')
        if any(not isinstance(v, str) or not v for v in path.values()):
            raise ValueError('DFT entries need nonempty text')
    return obj


def transitions(d):
    states = list(d['states'])
    width = max(1, (len(states)-1).bit_length())
    allowed = [f'(previous == {width}\'d{states.index(a)} && supply_state == {width}\'d{states.index(b)})'
               for a, b in d['transitions']]
    allowed.append('(previous == supply_state)')
    lines = [f'module rvw_{d["name"]}_supply(input clk, reset, power_good, isolated, input [{width-1}:0] supply_state);',
             f'reg [{width-1}:0] previous;', 'reg armed=0;', 'always @(posedge clk) begin',
             f' if(reset) begin previous <= {width}\'d{states.index(d["initial"])}; armed<=0; end',
             ' else begin', f'  assert(supply_state < {len(states)});',
             f'  if(!armed) assert(supply_state == {width}\'d{states.index(d["initial"])});',
             '  if(armed) assert(' + ' || '.join(allowed) + ');']
    for i, value in enumerate(d['states'].values()):
        lines += [f'  if(supply_state == {width}\'d{i}) begin',
                  f'   assert(power_good == {int(value["power_good"])});',
                  f'   assert(isolated == {int(value["isolated"])});', '  end']
    return '\n'.join(lines + ['  previous<=supply_state; armed<=1;', ' end', 'end', 'endmodule', ''])


def generate(intent, out, db=None):
    obj = validate(json.loads(Path(intent).read_text()))
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    (out/'intent.json').write_text(json.dumps(obj, indent=2)+'\n')
    text = []
    for d in obj['domains']:
        text.append(transitions(d))
        for kind in d['checks']:
            source = power_checks.render(kind, d['width'], d['wake_bound'])
            text.append(source.replace('module rvw_'+kind+'(', 'module rvw_'+d['name']+'_'+kind+'('))
    (out/'power.sv').write_text('\n'.join(text))
    inventory = []
    database = None
    try:
        if db:
            from rvw.query.db import DesignDB
            database = DesignDB(db)
        for path in obj.get('dft', []):
            row = dict(path, binding='not_verified')
            if database:
                from rvw.query.db import QueryError
                try:
                    sig = database.resolve_one(path['signal'])
                    row.update(binding='found', rtl_path=sig.path, width=sig.width, clock_role=sig.clock_role)
                except QueryError as exc:
                    row.update(binding='unresolved', reason=str(exc))
            inventory.append(row)
    finally:
        if database:
            database.close()
    report = {'schema': 'rvw.power-generation/1', 'status': 'generated', 'dft': inventory,
              'states': {d['name']: list(d['states']) for d in obj['domains']},
              'limits': ['Sampled RTL controls only; no analog glitch or physical power model.',
                         'Off-state storage is unconstrained by the isolation monitor; consumers need valid or isolated outputs.',
                         'DFT path presence is not ATPG, scan coverage or proof of access.',
                         'No UPF import, DUT binding or proof run.']}
    (out/'result.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


def run(args):
    from rvw.query.db import QueryError
    try:
        print(json.dumps(generate(args.intent, args.out, args.db)))
        return 0
    except (ValueError, KeyError, TypeError, OSError, QueryError) as exc:
        print(f'Power intent error: {exc}')
        return 2
