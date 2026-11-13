"""Seeded architectural-contract program pairs through project RTL adapters."""
import hashlib
import json
from pathlib import Path
import random
from rvw.cosim.trace import Trace
from .common import native, publish

CONTRACTS = ('constant-time','sandboxing','speculative-constant-time')


def generate(seed, count):
    rng = random.Random(seed)
    # Public instruction stream; only secret input values differ.
    return [f'{rng.choice(("add","xor","and","or"))} x{rng.randrange(8,16)}, x6, x7' for _ in range(count)]


def trace(path):
    reader = Trace(path)
    try:
        rows = list(reader)
    finally:
        reader.file.close()
    if not rows or rows[-1].get('event') != 'end' or rows[-1].get('status') != 'pass':
        raise ValueError('complete passing C2 evidence required')
    rows = [r for r in rows if 'event' not in r]
    if not rows:
        raise ValueError('empty C2 trace')
    return rows


def projection(rows, clauses):
    result = []
    for r in rows:
        item = {}
        for clause in clauses:
            if clause == 'pc': item['pc'] = r['pc']
            elif clause == 'memory':
                item['memory'] = r['mem_addr'] if r['mem_rmask'] or r['mem_wmask'] else None
            elif clause == 'branch':
                insn = r['insn']
                if insn & 127 == 0x63:
                    if 'pc_next' not in r: raise ValueError('branch contract requires pc_next')
                    item['branch'] = r['pc_next'] != r['pc']+4
            else: raise ValueError('unknown architectural observation clause')
        result.append(item)
    return result


def compare(a,b,plan):
    if a['public'] != b['public'] or a['secret'] == b['secret']:
        raise ValueError('pairs need equal public context and different secrets')
    clauses = plan.get('clauses',['pc','memory','branch'])
    if not clauses or plan['contract'] not in CONTRACTS:
        raise ValueError('declare an architectural leakage contract')
    def region(rows):
        start=plan.get('contract_start_pc')
        if start is None: return rows
        if isinstance(start,str): start=int(start,0)
        for i,row in enumerate(rows):
            if row['pc']==start: return rows[i:]
        raise ValueError('contract start PC was not reached')
    if projection(region(a['reference']),clauses) != projection(region(b['reference']),clauses):
        return dict(status='ineligible', channels=[])
    channels = [k for k in plan['observations'] if a['observations'][k] != b['observations'][k]]
    return dict(status='violation' if channels else 'no_leak_observed',channels=channels)


def run(manifest, out):
    manifest = Path(manifest).resolve()
    plan = json.loads(manifest.read_text())
    out = Path(out).resolve(); out.mkdir(parents=True, exist_ok=False)
    (out/'manifest.json').write_bytes(manifest.read_bytes())
    if not plan.get('observations') or len(set(plan['observations'])) != len(plan['observations']):
        raise ValueError('declare distinct observation channels')
    if not plan.get('adapter_command') or not isinstance(plan['adapter_command'],list):
        raise ValueError('adapter_command must be an argv list')
    timeout = plan.get('timeout',90)
    if not 0 < timeout <= 120: raise ValueError('timeout must be in (0,120]')
    def invoke(program,secret,label):
        folder = out/label; folder.mkdir()
        request = dict(schema='rvw.sec-case/1', program=program,secret=secret,
                       public=plan['public'],contract=plan['contract'])
        (folder/'request.json').write_text(json.dumps(request))
        argv = [s.replace('{request}',str(folder/'request.json')).replace('{out}',str(folder))
                for s in plan['adapter_command']]
        log = native(argv,manifest.parent,timeout)
        (folder/'adapter.log').write_text(log)
        r = json.loads((folder/'response.json').read_text())
        if r.get('complete') is not True or r.get('reset_complete') is not True:
            raise ValueError('adapter must confirm completion and reset')
        def local(name):
            p = Path(r[name]); return p if p.is_absolute() else folder/p
        reference = trace(local('reference_c2'))
        rtl = trace(local('rtl_c2'))
        keys = ('pc','insn','rd','rd_wdata','mem_addr','mem_rmask','mem_wmask','mem_wdata','trap','mode')
        if [[x.get(k) for k in keys] for x in reference] != [[x.get(k) for k in keys] for x in rtl]:
            raise ValueError('RTL differs from independent reference')
        if set(r['observations']) != set(plan['observations']):
            raise ValueError('missing or extra microarchitectural observation channels')
        # Observations can contain complete cache/branch/TLB/bus event lists.
        return dict(reference=reference,observations=r['observations'], public=plan['public'],secret=secret)
    count = plan.get('instructions',16)
    if type(count) is not int or not 1<=count<=1000: raise ValueError('instructions must be 1..1000')
    program = plan.get('program',generate(plan.get('seed',1),count))
    secrets = plan['secrets']
    if len(secrets)!=2 or secrets[0]==secrets[1]: raise ValueError('two different secrets required')
    findings=[]; errors=[]; comparison={}; calls=0
    def pair(p,label):
        nonlocal calls
        calls+=2
        return compare(invoke(p,secrets[0],label+'-a'),invoke(p,secrets[1],label+'-b'),plan)
    try:
        comparison = pair(program,'initial')
        if comparison['status']=='violation':
            # Greedy deletion with actual reference and RTL replay for every trial.
            # Bounded search; no claim of a global minimum.
            budget=plan.get('minimize_runs',16)
            if type(budget) is not int or not 0<=budget<=100: raise ValueError('minimize_runs must be 0..100')
            index=0; attempts=0
            while len(program)>1 and index<len(program) and attempts<budget:
                trial=program[:index]+program[index+1:]; attempts+=1
                try:
                    c=pair(trial,f'reduce-{attempts}')
                    if c['status']=='violation': program=trial; comparison=c; continue
                except (ValueError,OSError,KeyError) as e:
                    errors.append(str(e))
                index+=1
            counterexample=dict(program=program,secrets=secrets,public=plan['public'],comparison=comparison)
            (out/'counterexample.json').write_text(json.dumps(counterexample,indent=2)+'\n')
            findings.append(counterexample)
    except (ValueError,OSError,KeyError) as e:
        errors.append(str(e))
    return publish(out,'contract',findings,comparison.get('status') in ('violation','no_leak_observed') and not errors,
                   comparison=comparison, errors=errors, adapter_runs=calls,
                   manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest())
