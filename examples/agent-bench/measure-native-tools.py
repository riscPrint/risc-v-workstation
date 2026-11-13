#!/usr/bin/env python3
"""Measure the five-tool MCP workflow on a verified private native workspace."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from rvw.agent_bench.native import git, load_pack, mutate, verify_workspace
from rvw.agent_bench.tool_trial import run_evidence_trial


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--core', choices=['vexriscv', 'ooo-mini'], required=True)
    p.add_argument('--pack', type=Path, required=True)
    p.add_argument('--source', type=Path, required=True, help='Original checkout at the pack pin')
    p.add_argument('--workspace', type=Path, required=True, help='Clean private workspace from native-qualify')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--task', action='append')
    a = p.parse_args()
    home = Path(__file__).resolve().parents[2]
    pack, _, base = load_pack(a.pack)
    workspace, outroot = a.workspace.resolve(), a.out.resolve()
    verify_workspace(pack, a.source, workspace)
    tasks = [t for t in pack['tasks'] if not a.task or t['id'] in a.task]
    if not tasks or a.task and set(a.task) != {t['id'] for t in tasks}:
        p.error('unknown task ID')
    outroot.mkdir(parents=True, exist_ok=False)
    example = home / 'examples' / a.core
    os.environ[pack['source']['env']] = str(workspace)
    for task in tasks:
        out = outroot / task['id']
        out.mkdir()
        change = task['private']['mutation']
        original = (workspace / change['file']).read_text()
        pos = -1
        for _ in range(change.get('occurrence', 1)):
            pos = original.find(change['find'], pos + 1)
            if pos < 0:
                raise ValueError('mutation text not found')
        truth = {'file': change['file'], 'line': original[:pos].count('\n') + 1}
        mutate(workspace, change)
        git(workspace, 'add', change['file'])
        git(workspace, 'commit', '-qm', 'seed tool measurement ' + task['id'])
        try:
            text = (example / 'rvw.toml').read_text()
            text = text.replace('root = "."', f'root = "{example}"')
            for prefix in ('./rvw/', 'rvw/'):
                text = text.replace('"' + prefix, '"' + str(example / 'rvw') + '/')
            text = re.sub(r'^lock = .*$', 'lock = "vex-agentbench"', text, flags=re.M)
            text = re.sub(r'^source_repo = .*$', f'source_repo = "{workspace}"', text, flags=re.M)
            if a.core == 'ooo-mini':
                project_source = workspace / 'examples/ooo-mini'
                text = text.replace('"src", "build.sbt", "project/build.properties"',
                                    f'"{project_source}/src", "{project_source}/build.sbt", "{project_source}/project/build.properties"')
                text += '\n[query]\nbuild = ["' + str(Path(__file__).with_name('ooo-build-db.sh')) + '"]\n'
            for key, value in [('identity_timeout_s', 100), ('build_timeout_s', 100), ('startup_s', 80)]:
                text = re.sub(r'^' + key + r' = .*$', f'{key} = {value}', text, flags=re.M)
            test = task['private']['fail_to_pass'][0]
            programs = (base / pack['programs']).resolve()
            if a.core == 'ooo-mini':
                text += '\n[debug]\nconfig = \"' + str(Path(__file__).with_name('ooo-debug.toml')) + '\"\n'
            text += (f'\n[suites.agentbench]\ndir = "{programs}"\ninclude = ["^{test}$"]\n'
                     f'configs = ["{pack["config"]}"]\nmax_cycles = 10000\ntimeout_s = 30\n'
                     'mem_latency = 0\noptions = {wave = true}\n')
            project, db = out / 'rvw.toml', out / 'design.db'
            project.write_text(text)
            command = [sys.executable, str(Path(__file__).with_name('mcp-call.py')), 'query_build_db',
                       json.dumps({'project': str(project), 'config': pack['config'], 'out': str(db)}),
                       str(out / 'db-build.json')]
            with (out / 'db-build.log').open('w') as log:
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=False)
            signal = 'rvfi_rd_wdata' if a.core == 'vexriscv' else 'io_retire_rd_wdata'
            prefix = 'rvfi_' if a.core == 'vexriscv' else 'io_retire_'
            bindings = {'rd_wdata': prefix + 'rd_wdata', 'pc': prefix + 'pc_rdata', 'pc_next': prefix + 'pc_wdata', 'rs1_rdata': prefix + 'rs1_rdata', 'rs2_rdata': prefix + 'rs2_rdata', 'mem_rdata': prefix + 'mem_rdata'}
            regression = out / 'regression'
            rundir = regression / 'agentbench' / pack['config'] / 'tests' / test
            steps = [
                {'tool': 'regress_run', 'arguments': {'project': str(project), 'suite': 'agentbench', 'config': pack['config'], 'out': str(regression), 'rvfi_trace': True, 'jobs': 1, 'no_cache': True, 'no_index': True}},
                {'tool': 'cosim_check', 'arguments': {'trace': str(rundir / 'rvfi.jsonl'), 'elf': str(programs / test), 'core': 'native-task', 'platform': str((base / pack['platform']).resolve()), 'strict': True, 'timeout': 15}},
                {'tool': 'bundle_make', 'arguments': {'run_dir': str(rundir), 'out': str(out / 'bundle'), 'project': str(project), 'no_rerun': True, 'no_spinaltrace': True, 'timeout': 15}},
                {'tool': 'query_drivers', 'arguments': {'db': str(db), 'signal': signal}, 'mismatch_signals': bindings},
                {'tool': 'wave_why', 'arguments': {'db': str(db), 'wave': str(rundir / 'wave.fst'), 'signal': signal, 'at': '0', 'depth': 12, 'max_nodes': 256}, 'mismatch_signals': bindings, 'wave_time': {'order_signal': prefix + 'order', 'valid_signal': prefix + 'valid'}},
            ]
            plan = out / 'plan.json'
            plan.write_text(json.dumps({'id': task['id'], 'steps': steps, 'truth': truth}, indent=2) + '\n')
            run_evidence_trial(plan, [sys.executable, '-m', 'rvw.agent_bench.solver_client'], out / 'trial',
                               budget_s=110, max_calls=32, model='scripted five-tool MCP client')
        finally:
            mutate(workspace, change, reverse=True)
            git(workspace, 'add', change['file'])
            git(workspace, 'commit', '-qm', 'restore tool measurement baseline')
            if (workspace / change['file']).read_text() != original:
                raise RuntimeError('source round trip failed')


if __name__ == '__main__':
    main()
