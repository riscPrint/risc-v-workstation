"""Run source mutations in a private core copy and measure causal-chain hits."""
from collections import deque
import json
from pathlib import Path
import os
import time
import shutil
import tempfile
import uuid

from rvw.common.capture import Capture, canonical_json, sha256_file
from hashlib import sha256
from rvw.regress.source import describe
from rvw.cov.campaign_artifacts import seal_attempt, verify_attempt

from rvw.common.proc import run_group
from rvw.runs import open_run
from .failure import compare, explain_run


def source_matches(actual, expected):
    a, b = Path(actual).parts, Path(expected).parts
    return a == b or (not Path(expected).is_absolute() and len(a) >= len(b) and a[-len(b):] == b)


def statement_depth(report, file, line):
    """Minimum dependency depth of an active statement, or None when absent."""
    found = []
    for chain in report.get('chains', []):
        graph = chain.get('dynamic', {}).get('graph')
        if graph:
            vertices = graph.get('vertices', [])
            roots = [i for i, v in enumerate(vertices) if v.get('assigns_to') == chain['signal']]
            if roots:
                latest = max(vertices[i].get('timestamp', -1) for i in roots)
                roots = [i for i in roots if vertices[i].get('timestamp', -1) == latest]
            edges = {}
            for edge in graph.get('edges', []):
                edges.setdefault(edge['from'], []).append(edge['to'])
            queue, seen = deque((i, 0) for i in roots), set()
            while queue:
                i, depth = queue.popleft()
                if i in seen or not 0 <= i < len(vertices):
                    continue
                seen.add(i)
                v = vertices[i]
                if source_matches(v.get('file', ''), file) and v.get('line') == line:
                    found.append(depth)
                queue.extend((child, depth+1) for child in edges.get(i, []))
        else:
            queue = deque([(chain.get('driver_walk', {}).get('trace', {}), 0)])
            while queue:
                node, depth = queue.popleft()
                for assignment in node.get('assignments', []):
                    loc = assignment.get('loc')
                    if assignment['id'] == node.get('active') and loc:
                        source, number = loc.rsplit(':', 1)
                        if source_matches(source, file) and int(number) == line:
                            found.append(depth)
                queue.extend((child, depth+1) for child in node.get('children', []))
    return min(found) if found else None


def _identity(source, case, compile_command, simulate_command, *, project, db, binding,
              env, compile_cwd, window, elf, build_inputs, native_tools, inputs_complete, evidence):
    """Reuse is opt-in: callers must enumerate all external inputs and tools.

    Include ignored build inputs, JARs, native libraries, adapter scripts and project
    dependencies in build_inputs. Incomplete enumeration must leave reuse disabled.
    """
    if not compile_command or not simulate_command or not all(Path(c[0]).is_absolute() for c in (compile_command, simulate_command)):
        return None
    if not inputs_complete or not elf or not project or not db or not binding or not native_tools or not build_inputs:
        return None
    with tempfile.TemporaryDirectory(prefix='rvw-trace-inputs-') as temporary:
        capture = Capture(Path(temporary) / 'capture')
        state = describe(source)
        if not state.reusable:
            return None
        capture.tree(source, git=state.rev is not None)
        for path in [elf, project, db, binding, *build_inputs]:
            path = Path(path).resolve(strict=True)
            if path.is_dir():
                capture.tree(path, git=False)
            else:
                capture.file(path)
        for tool in [compile_command[0], simulate_command[0], *native_tools]:
            resolved = shutil.which(str(tool), path=env.get('PATH', os.defpath))
            if resolved is None:
                return None
            capture.tool(resolved, identity_only=True)
        # Bind the workstation implementation, including reference and trace code.
        for path in sorted(Path(__file__).parents[1].rglob('*.py')):
            capture.file(path)
        capture.verify_tools()
        options = dict(source=state.to_dict(), case=case,
            compile=list(compile_command), simulate=list(simulate_command),
            compile_cwd=str(compile_cwd), env_sha256=sha256(canonical_json(dict(env))).hexdigest(),
            reference_env_sha256=sha256(canonical_json(dict(os.environ))).hexdigest(), window=window,
            depth=64, max_nodes=1024, compile_timeout=300, simulation_timeout=120)
        key = capture.cache_key(options, complete=True)
        shutil.copytree(capture.root, evidence)
        (evidence/"capture.json").write_text(json.dumps(capture.record(), indent=2))
        (evidence/"identity.json").write_text(json.dumps(dict(key=key, options=options), indent=2))
        return key


def _verdict(report, case, line):
    comparison = report.get('cosim', {}).get('status')
    depth = None
    if comparison == 'match':
        status = 'no_mismatch' if report['cosim'].get('trace_complete') is True else 'comparison_inconclusive'
    elif comparison != 'mismatch':
        status = 'comparison_inconclusive'
    elif report.get('status') != 'explained' or not report.get('chains'):
        status = 'tracing_unresolved'
    else:
        depth = statement_depth(report, case['file'], line)
        # A bounded/inferred chain cannot establish absence of the mutation.
        status = 'hit' if depth is not None else 'tracing_unresolved'
    return dict(status=status, comparison=comparison, depth=depth, cause=report.get('cause'))


def run_cases(source, cases, compile_command, simulate_command, *, work, project,
              db, binding, env, compile_cwd=None, window=80, resume=False,
              elf=None, build_inputs=(), native_tools=(), inputs_complete=False):
    """Run private-source edits. Never reuse a verdict; recheck retained evidence.

    Reuse requires a complete dependency list. Old and incomplete attempts remain
    on disk. Each invalid reuse starts a new directory. Callers own native locks
    and scheduling priority through their command vectors.
    """
    source, work = Path(source).resolve(), Path(work).resolve()
    if work.is_relative_to(source) or source.is_relative_to(work):
        raise ValueError('source and evidence directories must be separate')
    compile_cwd = Path(compile_cwd or source).resolve()
    all_cases = [{'name': 'baseline'}, *cases]
    names = [c['name'] for c in all_cases]
    if len(set(names)) != len(names) or any(Path(n).name != n or n in ('', '.', '..') for n in names):
        raise ValueError('case names must be unique path components')
    paths = {c['file']: (source / c['file']).resolve() for c in cases}
    if any(not path.is_relative_to(source) for path in paths.values()):
        raise ValueError('mutation source is outside private source directory')
    originals = {file: path.read_bytes() for file, path in paths.items()}
    work.mkdir(parents=True, exist_ok=resume)
    try:
        saved = {r['name']: r for r in json.loads((work/'summary.json').read_text())} if resume else {}
    except (OSError, ValueError, KeyError, TypeError):
        saved = {}
    rows = []
    try:
        for case in all_cases:
            for file, content in originals.items():
                paths[file].write_bytes(content)
            line = None
            identity = None
            fresh = work / ('attempt-' + uuid.uuid4().hex)
            fresh.mkdir()
            try:
                identity = _identity(source, case, compile_command, simulate_command,
                    project=project, db=db, binding=binding, env=env, compile_cwd=compile_cwd,
                    window=window, elf=elf, build_inputs=build_inputs, native_tools=native_tools,
                    inputs_complete=inputs_complete, evidence=fresh/'inputs')
            except (OSError, ValueError):
                pass  # An uncovered dependency disables reuse, never permits it.
            if 'file' in case:
                text = originals[case['file']].decode()
                if not case['before'] or text.count(case['before']) != 1 or case['before'] == case['after']:
                    raise ValueError(f"mutation must change exactly one match: {case['name']}")
                prefix = os.path.commonprefix([case['before'], case['after']])
                line = text[:text.index(case['before'])].count('\n') + prefix.count('\n') + 1
                paths[case['file']].write_bytes(text.replace(case['before'], case['after'], 1).encode())
            previous = saved.get(case['name'], {})
            reused = False
            if identity and previous.get('identity') == identity and previous.get('native_complete') is True:
                try:
                    verify_attempt(work, previous)
                    directory = work / previous['attempt']
                    if not directory.resolve().is_relative_to(work) or not previous.get('sealed_generation'):
                        raise ValueError('invalid attempt')
                    if json.loads((directory/'inputs/identity.json').read_text()).get('key') != identity:
                        raise ValueError('sealed input identity differs')
                    for name, expected in previous['artifacts'].items():
                        if sha256_file(work/name) != expected:
                            raise ValueError('attempt evidence changed')
                    reused = True
                except (OSError, ValueError, KeyError, TypeError):
                    pass
            if not reused:
                directory = fresh
            row = dict(name=case['name'], line=line, depth=None, status='build_error',
                       identity=identity, native_reused=reused, native_complete=False,
                       attempt=directory.name)
            start = time.monotonic()
            try:
                if not reused:
                    with (directory/'compile.log').open('w') as log:
                        compiled = run_group(compile_command, cwd=str(compile_cwd), env=env,
                                             timeout=300, stdout=log, stderr=log)
                    if compiled.timed_out:
                        row['status'] = 'build_timeout'
                    elif compiled.returncode:
                        row['status'] = 'build_error'
                    else:
                        lines = (directory/'compile.log').read_text().splitlines()
                        cp = next((s for s in lines if s.startswith('/') and 'scala-library' in s), None)
                        if cp is None:
                            raise ValueError('compile did not export Runtime/fullClasspath')
                        argv = [s.replace('{classpath}', cp).replace('{out}', str(directory/'run'))
                                for s in simulate_command]
                        row['status'] = 'simulation_error'
                        with (directory/'simulation.log').open('w') as log:
                            simulated = run_group(argv, cwd=str(source), env=env, timeout=120, stdout=log, stderr=log)
                        row['status'] = 'simulation_timeout' if simulated.timed_out else 'simulation_error'
                        row['native_complete'] = not simulated.timed_out and simulated.returncode == 0
                else:
                    row['native_complete'] = True
                if row['native_complete']:
                    try:
                        run = open_run(directory/'run')
                    except (OSError, ValueError) as exc:
                        row.update(status='c1_incomplete', cause=str(exc), native_complete=False)
                        run = None
                if row['native_complete']:
                    row.update(c1_status=run.get('status'), c1_limit=run.inconclusive)
                    if run.inconclusive or run.get('status') not in ('pass', 'fail'):
                        row.update(status='c1_incomplete', native_complete=False)
                    elif line is None and run.get('status') != 'pass':
                        row.update(status='baseline_c1_failed', native_complete=False)
                    elif line is None:
                        row['status'] = 'baseline_inconclusive'
                        report = compare(run, project, None, 120)
                        row.update(status='baseline_match' if report.get('status') == 'match' and
                                   report.get('trace_complete') is True else
                                   'baseline_mismatch' if report.get('status') == 'mismatch' else 'baseline_inconclusive',
                                   comparison=report.get('status'))
                        (directory/'comparison.json').write_text(json.dumps(report, indent=2))
                    else:
                        row['status'] = 'tracing_unresolved'
                        report = explain_run(str(run.dir), db, binding, str(directory/'replay'),
                            project=project, rerun=False, window=window, depth=64, max_nodes=1024)
                        row.update(_verdict(report, case, line))
                        (directory/'explanation.json').write_text(json.dumps(report, indent=2))
                    artifacts = run.get('artifacts') or {}
                    local = all((run.dir / path).resolve().is_relative_to(directory) and
                                (run.dir / path).is_file() for path in artifacts.values())
                    for name in ('wave', 'pdg', 'rvfi_trace'):
                        artifact = run.artifact(name)
                        if artifact is not None:
                            local = local and artifact.resolve().is_relative_to(directory) and artifact.is_file()
                    details_pdg = (run.get('details') or {}).get('pdg')
                    if details_pdg:
                        pdg = Path(details_pdg)
                        local = local and pdg.resolve().is_relative_to(directory) and pdg.is_file()
                    causal = line is None or (run.artifact('wave') is not None and
                                              run.artifact('wave').is_file())
                    if row['status'] in ('baseline_match', 'hit', 'no_mismatch') and identity and local and causal:
                        # All run files and causal data stay available and are sealed.
                        row['artifacts'] = {str(p.relative_to(work)): sha256_file(p)
                                            for p in directory.rglob('*') if p.is_file()}
                        row['sealed_generation'] = seal_attempt(work, directory, row)
                    else:
                        row['native_complete'] = False
            except (OSError, ValueError) as exc:
                row.update(cause=str(exc), native_complete=False)
            row['seconds'] = round(time.monotonic()-start, 2)
            rows.append(row)
            temporary = work/'summary.json.tmp'
            temporary.write_text(json.dumps(rows, indent=2)+'\n')
            temporary.replace(work/'summary.json')
            print(json.dumps(row), flush=True)
            if line is None and row['status'] != 'baseline_match':
                break
    finally:
        for file, content in originals.items():
            paths[file].write_bytes(content)
    return rows
