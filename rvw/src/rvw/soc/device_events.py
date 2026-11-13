"""Independent register state at accepted-request linearization points."""
import json
from pathlib import Path
from .model import load
from .bridge import uint


def check(map_path, trace_path):
    model = load(map_path)
    trace = json.loads(Path(trace_path).read_text())
    if trace.get('schema') != 'rvw.device-events/1' or trace.get('linearization') != 'accepted_request':
        raise ValueError('require rvw.device-events/1 and accepted_request linearization')
    registers = {r['base']+reg['offset']: reg for r in model['regions'] for reg in r['registers']}
    state = {a: r['reset'] for a,r in registers.items()}
    pending, checks, masters = {}, [], set()
    previous = -1
    def record(event, rule, actual, expected):
        checks.append(dict(event=event, rule=rule, actual=actual, expected=expected, match=actual == expected))
    for index,event in enumerate(trace['events']):
        cycle = event['cycle']
        if type(cycle) is not int or cycle < 0 or cycle < previous:
            raise ValueError('event cycles must be nonnegative and ordered')
        previous = cycle
        kind = event['kind']
        if kind in ('request','response'):
            master, tag = event['master'], event['id']
            if not isinstance(master,str) or not master or type(tag) is not int or tag < 0:
                raise ValueError('declare master name and nonnegative transaction id')
            key = master,tag
            masters.add(master)
        if kind == 'request':
            record(index,'unique_request', key not in pending, True)
            if key in pending:
                continue
            address = int(event['address'],0) if isinstance(event['address'],str) else event['address']
            reg = registers.get(address)
            if type(event['write']) is not bool:
                raise ValueError('write must be boolean')
            error = reg is None or event['size']*8 != reg['width'] or ('w' if event['write'] else 'r') not in reg['access']
            old = state[address] if reg is not None else 0
            pending[key] = dict(error=error, write=event['write'], data=old, width=reg['width'] if reg else 0)
            if not error:
                if event['write']:
                    value = uint(event['data'],reg['width'])
                    mask = uint(event.get('write_mask',(1 << reg['width'])-1),reg['width'])
                    state[address] = (old & ~(value & mask) if reg['write_action'] == 'one_to_clear'
                                      else (old & ~mask) | (value & mask))
                elif reg['read_action'] == 'clear':
                    state[address] = 0
        elif kind == 'response':
            record(index,'response_pending',key in pending,True)
            if key not in pending:
                continue
            expected = pending.pop(key)
            if type(event['error']) is not bool:
                raise ValueError('error must be boolean')
            record(index,'response_error',event['error'],expected['error'])
            if not expected['error'] and not expected['write']:
                record(index,'read_data',uint(event['data'],expected['width']),expected['data'])
        elif kind in ('hardware','state'):
            address = int(event['address'],0) if isinstance(event['address'],str) else event['address']
            if address not in registers:
                raise ValueError('state and hardware events need a mapped register')
            width = registers[address]['width']
            if kind == 'state':
                record(index,'register_state',uint(event['value'],width),state[address])
            else:
                delta = event.get('increment',0)
                if type(delta) is not int or delta < 0:
                    raise ValueError('hardware increment must be nonnegative')
                state[address] = (((state[address]+delta) & ((1 << width)-1)) &
                                  ~uint(event.get('clear',0),width)) | uint(event.get('set',0),width)
        else:
            raise ValueError('unsupported device event kind')
    mismatch = any(not c['match'] for c in checks)
    return dict(schema='rvw.device-event-check/1',status='mismatch' if mismatch else 'inconclusive',
                checks=checks, outstanding=[dict(master=m,id=t) for m,t in pending],masters=sorted(masters),
                limits=['Independent reset model; effects linearize at accepted requests in array order.',
                        'Only exact full-width mapped registers; no device-specific timing or interrupt semantics.',
                        'Capture completeness, real-device binding and event independence are not established.'])


def run(args):
    try:
        result = check(args.model,args.trace)
        Path(args.out).write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result))
        return 1 if result['status'] == 'mismatch' else 3
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print(f'device event check error: {exc}')
        return 2
