"""Bounded candidate execution. Only complete reference checks can earn hits."""
from hashlib import sha256
import json
import os
import shutil
from pathlib import Path
import time

from rvw.common.proc import run_group
from rvw.cosim.cli import execute_json as cosim
from rvw.cosim.elf import Elf
from rvw.regress.config import Suite, load_config
from rvw.regress.plan import source_for
from rvw.regress.runner import PlanItem, RunOptions, run_plan
from rvw.regress.random_stream import complete, digest
from rvw.regress.run_evidence import owned_run_paths
from rvw.results import load_run
from rvw.results.generation import open_current, publish
from . import captured
from .functional import functional
from .isa import plan
from .stimulus import generate, profile
from .campaign_artifacts import implementation_id,execution_identity,seal_attempt,verify_attempt,seal_inputs,verify_inputs


def execution_options(data):
    options={}
    if data.get('coverage') or data.get('code_plan'):options['coverage']=True
    if data.get('probe_plan'):options['probes']=True
    return options


def identifiers(report):
    return {name+':'+json.dumps(hit['bin'], separators=(',', ':'))
            for name, group in report['groups'].items() for hit in group['hits'] if hit['count'] > 0}


def payload(elf_path, candidate):
    """Bind the solved word to the executable, never to assembler source alone."""
    elf = Elf(elf_path)
    start, end = (elf.symbols[k] for k in ('rvw_payload_start', 'rvw_payload_end'))
    expected = candidate.get('instructions', [candidate.get('model',{}).get('instruction')])
    if end-start != 4*len(expected) or start % 4 or elf.xlen != candidate['xlen']:
        raise ValueError('invalid ELF payload range or XLEN')
    words = [data[start-base:end-base] for base, data, _ in elf.segments
             if base <= start and end <= base+len(data)]
    if len(words) != 1 or words[0] != b''.join(w.to_bytes(4,'little') for w in expected):
        raise ValueError('ELF payload differs from solved instruction')
    return {'elf_sha256': digest(elf_path), 'ranges': [[start, end]], 'policy': 'payload-pc-v1'}


def qualify(elf, results, platform, manifest, source_root, candidate, coverage_plan=None):
    region = payload(elf, candidate)
    matches = [r for p in owned_run_paths(results)
               if (r := load_run(p)).elf_sha256 == region['elf_sha256']]
    if len(matches) != 1:
        return {'status': 'adapter_error', 'new_hits': []}
    run = matches[0]
    if run.why_inconclusive:
        return {'status':'inconclusive', 'new_hits':[]}
    if run.status != 'pass':
        return {'status':'core_failure', 'new_hits':[]}
    trace = run.artifact('rvfi_trace')
    if trace is None:
        return {'status': 'trace_error', 'new_hits': []}
    comparison = cosim('check', elf=str(elf), trace=str(trace), platform=str(platform), model='spike', strict=True, core=getattr(run,'core',None))
    if not complete(comparison, run) or comparison.get('synchronized', 0):
        return {'status': 'mismatch' if comparison.get('status') == 'mismatch' else 'inconclusive',
                'comparison': comparison, 'new_hits': []}
    try:
        native_identity = execution_identity(run,comparison)
    except ValueError as exc:
        return {'status':'identity_error','comparison':comparison,'new_hits':[],'reason':str(exc)}
    coverage = functional([trace], run_results={str(Path(trace).resolve()): run.path/'result.json'}, platform=platform, manifest=manifest, source_root=source_root,
                          payload_regions={digest(trace): region}, config=coverage_plan)
    visits = next(iter(coverage['traces'].values())).get('payload_visits',{})
    expected_visits = {hex(pc):1 for start,end in region['ranges'] for pc in range(start,end,4)}
    if coverage['retired'] != len(candidate.get('instructions', [0])) or visits != expected_visits:
        return {'status': 'inconclusive', 'reason': 'each payload instruction must retire exactly once', 'new_hits': []}
    return {'status': 'qualified', 'execution_identity':native_identity, 'comparison': comparison, 'coverage': coverage,
            'region': region, 'trace_sha256': digest(trace), 'c1_sha256': digest(run.path/'result.json')}


@captured.command
def campaign(settings, work_dir, resume=False, replay=None):
    """Run a bounded integer campaign from project-owned runtime and adapter data."""
    if replay is not None:
        if type(replay) is not int or replay<0:
            raise ValueError('replay must be a nonnegative attempt index')
        resume=True
    settings = Path(settings).resolve()
    data = json.loads(captured.read_text(settings))
    required = {'schema', 'manifest', 'source_root', 'project', 'config', 'registers',
                'runtime', 'linker', 'platform', 'compiler', 'isa', 'abi', 'attempts', 'seed'}
    optional = {'timeout_s', 'max_cycles', 'timeout_ms', 'sequences', 'memory', 'rtl_plan', 'code_plan', 'probe_plan', 'coverage', 'recipes', 'strategy', 'initial_results'}
    if data.keys()-required-optional or required-data.keys() or data['schema'] != 'rvw.stimulus-loop/1':
        raise ValueError('expected rvw.stimulus-loop/1 with declared fields')
    if type(data['attempts']) is not int or not 1 <= data['attempts'] <= 1000:
        raise ValueError('attempts must be 1..1000')
    strategy = data.get('strategy', 'directed')
    if strategy not in ('directed', 'random'):
        raise ValueError('strategy must be directed or random')
    if strategy == 'random' and (data.get('sequences') or data.get('recipes')):
        raise ValueError('random control supports integer ISA bins only')
    def path(key):
        p = Path(data[key]).expanduser()
        return p.resolve() if p.is_absolute() else (settings.parent/p).resolve()
    manifest, root = path('manifest'), path('source_root')
    pinned = plan(manifest, root)
    profile_goals=set(profile(pinned['isa_plan']))
    declared={group['name']+':'+json.dumps(value,separators=(',',':'))
              for group in pinned['groups'] for value in group.get('bins',[])}
    supported = profile_goals & declared
    sequence_settings = data.get('sequences')
    sequence_groups = []
    if sequence_settings is not None:
        from .sequence import groups
        sequence_groups = groups(sequence_settings)
        supported.update('sequence:'+json.dumps(b,separators=(',',':')) for b in sequence_groups[0]['bins'])
    runtime = captured.read_text(path('runtime'))
    if runtime.count('{payload}') != 1:
        raise ValueError('runtime must contain exactly one {payload} marker')
    compiler = shutil.which(data['compiler'])
    if compiler is None:
        raise ValueError('compiler is not installed: '+data['compiler'])
    inputs = {'compiler': captured.sha256(compiler)}
    inputs.update({key: captured.sha256(path(key)) for key in ('manifest','runtime','linker','platform','project')})
    guidance_keys=[key for key in ('rtl_plan','code_plan','probe_plan') if data.get(key)]
    if len(guidance_keys)>1:raise ValueError('select one RTL, code or probe guidance plan')
    guidance_key=next(iter(guidance_keys),None)
    if 'coverage' in data and type(data['coverage']) is not bool:
        raise ValueError('coverage must be boolean')
    if bool(guidance_key)!=bool(data.get('recipes')):
        raise ValueError('guidance plan and recipes must be declared together')
    guide=None
    if guidance_key:
        inputs.update({key:captured.sha256(path(key)) for key in (guidance_key,'recipes')})
        from .guidance import load_guide
        guide=load_guide(path(guidance_key),path('recipes'))
    initial = None
    if 'initial_results' in data:
        paths = data['initial_results']
        if not isinstance(paths, list) or not paths or any(not isinstance(p, str) for p in paths):
            raise ValueError('initial_results must list C1 result paths')
        from .initial_coverage import measure
        initial_core = load_config(project=path('project'))
        initial = measure([(settings.parent / Path(p).expanduser()).resolve() for p in paths],
                          path('platform'), manifest, root, initial_core.name, data['config'])
        initial_identity = {'execution_identity':initial['execution_identity'],
                            'records':[{k:v for k,v in r.items() if k != 'comparison'}
                                       for r in initial['records']]}
        inputs['initial_results'] = sha256(json.dumps(initial_identity, sort_keys=True).encode()).hexdigest()
    implementation = implementation_id()
    identity = sha256(json.dumps([data, inputs, pinned, implementation], sort_keys=True).encode()).hexdigest()
    out = Path(work_dir).resolve()
    report = {'schema': 'rvw.stimulus-loop/1', 'identity': identity, 'attempts': [], 'hits': [],
              'supported_bins': len(supported), 'generation_profile_bins':len(profile_goals),
              'generation_groups':[{'group':g['name'],'declared_bins':len(g.get('bins',[])),
                  'supported_bins':sum(g['name']+':'+json.dumps(b,separators=(',',':')) in supported for b in g.get('bins',[]))}
                  for g in pinned['groups']+sequence_groups], 'full_plan_bins': sum(len(g.get('bins', [])) for g in pinned['groups']+sequence_groups),
              'implementation_sha256':implementation, 'status': 'inconclusive', 'cpu_accounting': 'inconclusive', 'bins_per_cpu_hour': None,
              'notes': ['os.times includes reaped child CPU; descendant completeness is not qualified.',
                        'No C4 acceptance or comparative closure rate is granted.',
                        'Attempt cost samples exclude raw sealing and state publication; total costs remain unqualified.']}
    if initial is not None:
        report['initial'] = initial
        report['hits'] = sorted(identifiers(initial['coverage']) & supported)
        report['execution_identity'] = initial['execution_identity']
    pair_settings = {k:data.get(k) for k in ('config','registers','isa','abi','attempts','seed',
                                             'timeout_s','max_cycles','timeout_ms','sequences','memory','coverage')}
    report['pair_context'] = sha256(json.dumps([inputs,pinned,pair_settings,implementation],
                                               sort_keys=True).encode()).hexdigest()
    report['initial_hits'] = list(report['hits'])
    report['strategy'] = strategy
    report['attempt_budget'] = data['attempts']
    if resume:
        previous = open_current(out/'state')
        report = json.loads(previous.read_bytes('report.json'))
        if report['identity'] != identity:
            raise ValueError('resume inputs or plan changed')
        verify_inputs(out,report['input_generation'],identity)
        for attempt in report['attempts']:
            verify_attempt(out,attempt)
            if replay is None:
                for name, expected in attempt.get('artifacts', {}).items():
                    if digest(out/name) != expected:
                        raise ValueError('resume artifact changed: '+name)
    else:
        out.mkdir(parents=True, exist_ok=False)
        report['input_generation']=seal_inputs(out,identity)
    selected = load_config(project=path('project'))
    if data['config'] not in selected.configs:
        raise ValueError('unknown core configuration')
    if replay is not None:
        from .campaign_replay import replay_attempt
        return replay_attempt(out,report,replay,selected,data,manifest,root,path('platform'))
    if guide is not None:
        guide.history=list(report.get('guidance_history',[]))
        report['unsupported_recipes'] = sorted(set(guide.recipes)-supported)
    hits = set(report['hits'])
    attempted = {a['goal'] for a in report['attempts']}
    def save():
        report['hits'] = sorted(hits)
        if guide is not None:
            report['guidance_history'] = guide.history
            report['guidance_coverage'] = guide.coverage_summary(supported)
        publish(out/'state', lambda directory: (directory/'report.json').write_text(json.dumps(report, indent=2)+'\n'))
    save()
    for index in range(len(report['attempts']), data['attempts']):
        holes = sorted(supported-hits-attempted, key=lambda goal: (not goal.startswith('sequence:'),goal))
        if guide is not None:
            holes = sorted(set(holes) | (guide.pending_goals() & supported))
        if not holes and strategy != 'random':
            break
        goal = 'random' if strategy == 'random' else guide.choose(holes) if guide is not None else holes[0]
        attempted.add(goal)
        directory = out/f'attempt-{index:04d}'
        if directory.exists():
            # An interrupted attempt has unknown cost and cannot be reused.
            report['attempts'].append({'goal': goal, 'status': 'interrupted', 'new_hits': []})
            save()
            continue
        directory.mkdir()
        attempt = {'goal': goal, 'seed': data['seed']+index, 'status': 'inconclusive', 'new_hits': []}
        report['attempts'].append(attempt)
        before, wall = os.times(), time.monotonic()
        try:
            if strategy == 'random':
                from .random_candidate import generate as generate_random
                candidate = generate_random(manifest, root, directory/'candidate',
                                            data['registers'], attempt['seed'])
            elif goal.startswith('sequence:'):
                from .actions import generate as generate_actions
                candidate = generate_actions(goal,directory/'candidate',data['registers'],
                    sequence_settings.get('distances',[1,2,4]),data.get('memory',False))
                candidate['xlen'] = int(data['isa'][2:4])
            else:
                candidate = generate(manifest, root, goal, directory/'candidate', data['registers'],
                                     attempt['seed'], data.get('timeout_ms', 1000))
            attempt['candidate'] = candidate
            attempt['status'] = candidate['status']
            if candidate['status'] == 'generated':
                assembly = directory/'program.S'
                assembly.write_text(runtime.replace('{payload}', Path(candidate['source']).read_text()))
                elf_dir = directory/'elfs'; elf_dir.mkdir()
                elf = elf_dir/'program.elf'
                argv = [compiler, '-march='+data['isa'], '-mabi='+data['abi'], '-nostdlib',
                        '-nostartfiles', '-static', '-T', str(path('linker')), str(assembly), '-o', str(elf)]
                attempt['compile_argv'] = argv
                with (directory/'compile.log').open('w') as log:
                    compiled = run_group(argv, timeout=data.get('timeout_s',60), stdout=log, stderr=log)
                if compiled.returncode or compiled.timed_out or not elf.is_file():
                    attempt['status'] = 'compile_error'
                else:
                    suite = Suite('closure', dir=elf_dir, glob='program.elf', strip_suffix='.elf',
                                  timeout_s=data.get('timeout_s',60), max_cycles=data.get('max_cycles',100000),
                                  options=execution_options(data))
                    run_plan(selected, [PlanItem(suite, data['config'])], directory/'run', source_for(selected,None),
                             RunOptions(seeds=1,seed_base=attempt['seed'],rvfi_trace=True,use_cache=False,
                                        jobs=1,index=False,tier='closure'))
                    coverage_plan = None
                    if sequence_settings is not None:
                        coverage_plan = directory/'coverage-plan.json'
                        coverage_plan.write_text(json.dumps({'groups':[], 'sequences':sequence_settings}))
                    evidence = qualify(elf, directory/'run', path('platform'), manifest, root, candidate, coverage_plan)
                    if evidence['status']=='qualified':
                        native=evidence.get('execution_identity')
                        if not native or (report.get('execution_identity') and report['execution_identity']!=native):
                            evidence={'status':'identity_error','new_hits':[],
                                      'reason':'missing or changed C1/reference native identity'}
                        else:
                            report['execution_identity']=native
                    attempt.update(evidence)
                    if guide is not None:
                        from .feedback_campaign import collect
                        attempt['feedback'] = collect(guide,goal,elf,directory/'run',path(guidance_key),
                                                      evidence['status']=='qualified',
                            **({'platform':path('platform')} if guidance_key=='probe_plan' else {}))
                    if evidence['status'] == 'qualified':
                        measured = identifiers(evidence['coverage']) & supported
                        attempt['new_hits'] = sorted(measured-hits)
                        hits.update(measured)
                        attempt['status'] = 'hit' if (attempt['new_hits'] if strategy == 'random' else goal in measured) else 'miss'
        except (OSError, ValueError, KeyError, TypeError) as exc:
            attempt.update(status='inconclusive', reason=str(exc))
        except BaseException:
            attempt.update(status='interrupted', reason='execution cancelled; descendant cost may be incomplete')
            raise
        finally:
            if guide is not None and 'feedback' not in attempt:
                record = {'goal':goal,'new_events':[],'samples':[],'status':'unsupported',
                          'reason':attempt.get('reason',attempt['status'])}
                guide.history.append(record)
                attempt['feedback'] = record
            after = os.times()
            attempt['elapsed_s'] = time.monotonic()-wall
            attempt['controller_cpu_s'] = after.user+after.system-before.user-before.system
            attempt['reaped_child_cpu_s'] = after.children_user+after.children_system-before.children_user-before.children_system
            attempt['artifacts'] = {str(p.relative_to(out)): digest(p) for p in sorted(directory.rglob('*')) if p.is_file()}
            attempt['sealed_generation']=seal_attempt(out,directory,attempt)
            save()
        if attempt['status'] in ('mismatch','core_failure','identity_error'):
            break
    report['status'] = 'fail' if any(a['status'] in ('mismatch','core_failure') for a in report['attempts']) else 'inconclusive'
    report['remaining_supported'] = sorted(supported-hits)
    save()
    return report
