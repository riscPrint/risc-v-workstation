"""Build each SV agent once, then measure good and corrupt fixture runs."""
import argparse
import ast
import hashlib
import json
import re
import urllib.request
from pathlib import Path
from rvw.common.proc import run_group
from rvw.sim.uvm import unpack, URL, COMMIT


def cases(source):
    """Reuse the protocol smoke runner's declared seed/fault matrix."""
    tree = ast.parse(source.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.For) and isinstance(node.target, ast.Tuple):
            if [v.id for v in node.target.elts] == ['fault', 'diagnostic']:
                return ast.literal_eval(node.iter)
    raise ValueError(f'no fault matrix: {source}')


def checked(text, result, marker, diagnostic, negative):
    if result.timed_out:
        return False
    if negative:
        return (result.returncode != 0 and re.search(r'(?<![A-Za-z0-9_])'+re.escape(diagnostic)+r'(?![A-Za-z0-9_])', text) is not None
                and marker not in text)
    errors = re.search(r'^\s*UVM_(ERROR|FATAL)\b(?!\s*:\s*0\s*$)', text, re.M)
    return result.returncode == 0 and not errors and text.count(marker) == 1


def assessment(runs):
    normal=[r for r in runs if r['fault']=='']
    corrupt=[r for r in runs if r['fault']=='buggy']
    good=bool(normal) and all(r['checked'] for r in normal)
    return dict(runs_good=good,catches_bad_dut=good and bool(corrupt) and all(r['checked'] for r in corrupt))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--archive', type=Path)
    p.add_argument('--verilator', default='verilator')
    p.add_argument('--build-timeout', type=float, default=1800)
    p.add_argument('--agents', nargs='+')
    a = p.parse_args()
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    archive = a.archive or out/'uvm.tar.gz'
    if not a.archive:
        urllib.request.urlretrieve(URL, archive)
    lib = unpack(archive, out/'library')
    root = Path(__file__).resolve().parents[1]
    version = run_group([a.verilator, '--version'], capture=True, timeout=10).stdout.strip()
    report = dict(engine=version, uvm_commit=COMMIT, build_timeout=a.build_timeout, agents=[])
    for src in sorted(root.iterdir()):
        if not (src/'test.sv').exists() or (a.agents and src.name not in a.agents):
            continue
        folder = out/src.name
        folder.mkdir()
        sources = [src/f'{src.name}_if.sv', src/f'{src.name}_pkg.sv', src/'fixture.sv', src/'test.sv']
        row = dict(agent=src.name, sources={str(s.relative_to(root)):hashlib.sha256(s.read_bytes()).hexdigest() for s in sources}, runs=[])
        cmd = [a.verilator, '--binary', '--timing', '--assert', '--coverage', '-Wno-fatal',
               '-j', '2', '--top-module', 'top', '+define+UVM_NO_DPI',
               f'+incdir+{lib / "src"}', str(lib/'src/uvm_pkg.sv'), *map(str,sources),
               '--Mdir', str(folder/'build'), '-MAKEFLAGS', 'OPT_FAST=-O0 OPT_SLOW=-O0']
        row['build_command'] = cmd
        print('BUILD', src.name, flush=True)
        with (folder/'build.log').open('w') as log:
            result = run_group(cmd, stdout=log, stderr=log, timeout=a.build_timeout)
        row['compiles'] = result.returncode == 0 and not result.timed_out
        if not row['compiles']:
            log = (folder/'build.log').read_text(errors='replace')
            row['limitation'] = 'build timeout' if result.timed_out else '\n'.join(line for line in log.splitlines() if '%Error' in line)[-4000:]
        elif not (src/'smoke.py').exists():
            row['limitation'] = 'No UVM runtime test, completion check or corrupt-DUT checker in this SV fixture.'
            with (folder/'empty.log').open('w') as log:
                result = run_group([str(folder/'build/Vtop')], stdout=log, stderr=log, timeout=2, cwd=folder)
            row['empty_fixture_timed_out'] = result.timed_out
        else:
            matrix = cases(src/'smoke.py')
            marker = matrix[0][1]
            for seed in (1, 2, 3):
                for fault, diagnostic in matrix:
                    name = f'{seed}-{fault or "good"}'
                    cmd = [str(folder/'build/Vtop'), f'+verilator+seed+{seed}']
                    if fault:
                        cmd.append('+'+fault)
                    with (folder/f'{name}.log').open('w') as log:
                        result = run_group(cmd, stdout=log, stderr=log, timeout=20, cwd=folder)
                    text = (folder/f'{name}.log').read_text(errors='replace')
                    negative = diagnostic != marker
                    row['runs'].append(dict(seed=seed, fault=fault, diagnostic=diagnostic,
                        negative=negative, checked=checked(text,result,marker,diagnostic,negative),
                        returncode=result.returncode, timed_out=result.timed_out, log=name+'.log'))
            for key, negative in [('runs_good',False), ('catches_bad',True)]:
                runs = [r for r in row['runs'] if r['negative']==negative]
                row[key] = bool(runs) and all(r['checked'] for r in runs)
            row.update(assessment(row['runs']))
        report['agents'].append(row)
        (out/'matrix.json').write_text(json.dumps(report, indent=2)+'\n')
        print('RESULT', src.name, row['compiles'], row.get('runs_good'), row.get('catches_bad'), flush=True)
    return report


if __name__ == '__main__':
    main()
