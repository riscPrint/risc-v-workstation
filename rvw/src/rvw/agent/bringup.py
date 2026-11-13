"""End-to-end bring-up check: walk the agent guide on a scratch copy of a tiny seeded core.

The check copies `bringup/core` (a tiny multi-cycle RV32I Spinal core), seeds a `sub` bug in
the copy and makes it a new Git repository, then follows the `bring-up` workflow from `rvw doctor` to the
committed gate, and the `test-fails` workflow from the failing `arith` program to the fixed and
accepted revision. Manual guide steps (mapping the adapter, building ELFs, reviewing the cosim
platform, the fix) are done by the check with prepared files. Each step records its command,
exit code, the decision the guide expects, what happened and its log. The report says which
steps work. It is a setup test, not core evidence.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from rvw.common.proc import run_group

from . import guide

SCHEMA = 'rvw.agent-bringup/1'
HERE = Path(__file__).with_name('bringup')
WORKSTATION = Path(__file__).resolve().parents[4]
NAME = 'tinycore'
BUG = 'Mux(alt, (x.asUInt + (~y).asUInt).asBits, (x.asUInt + y.asUInt).asBits)'
FIX = 'Mux(alt, (x.asUInt - y.asUInt).asBits, (x.asUInt + y.asUInt).asBits)'


class Walk:
    def __init__(self, out, *, timeout, env):
        self.out = Path(out)
        self.core = self.out / 'core'
        self.logs = self.out / 'logs'
        self.logs.mkdir(parents=True)
        self.timeout = timeout
        self.env = env
        self.steps = []
        self.guide = guide.load()

    def guide_step(self, workflow, step_id):
        w = next(w for w in self.guide['workflows'] if w['id'] == workflow)
        return next(s for s in w['steps'] if s['id'] == step_id)

    def command(self, argv, *, cwd=None, timeout=None):
        started = time.monotonic()
        result = run_group(argv, cwd=str(cwd or self.core), env=self.env, timeout=timeout or self.timeout,
                           capture=True, text=True)
        return result, time.monotonic() - started

    def record(self, workflow, step_id, *, argv=None, expect=None, check=None, note=None, cli_extra=(), subst=None,
               timeout=None):
        """Run a guide step (its cli with placeholders replaced, plus project inputs) or a script action."""
        entry = {'workflow': workflow, 'step': step_id}
        if argv is None:
            step = self.guide_step(workflow, step_id)
            argv = [str(Path(sys.executable).with_name('rvw')), *[_subst(a, subst or {}) for a in step['cli']],
                    *cli_extra]
            entry['guide_cli'] = step['cli']
        entry['command'] = [str(a) for a in argv]
        result, seconds = self.command(entry['command'], timeout=timeout)
        log = self.logs / f'{len(self.steps):02d}-{workflow}-{step_id}.log'
        log.write_text((result.stdout or '') + '\n--- stderr ---\n' + (result.stderr or ''))
        entry.update(exit=result.returncode, timed_out=result.timed_out, seconds=round(seconds, 1),
                     log=str(log.relative_to(self.out)))
        observed = check(result) if check else (result.returncode == 0)
        entry['expected'] = expect or 'exit 0'
        entry['status'] = 'works' if observed is True else 'rough_edge'
        if isinstance(observed, str):
            entry['observed'] = observed
        if note:
            entry['note'] = note
        self.steps.append(entry)
        return result

    def action(self, workflow, step_id, description, fn):
        entry = {'workflow': workflow, 'step': step_id, 'action': description}
        started = time.monotonic()
        try:
            detail = fn()
            entry['status'] = 'works'
            if detail:
                entry['detail'] = detail
        except Exception as exc:  # a failed manual step is a finding, not a crash of the check
            entry.update(status='rough_edge', observed=f'{type(exc).__name__}: {exc}')
        entry['seconds'] = round(time.monotonic() - started, 1)
        self.steps.append(entry)
        return entry['status'] == 'works'

    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.core, check=True, capture_output=True, text=True,
                              env={**self.env, 'GIT_AUTHOR_NAME': 'bringup', 'GIT_AUTHOR_EMAIL': 'bringup@example.invalid',
                                   'GIT_COMMITTER_NAME': 'bringup', 'GIT_COMMITTER_EMAIL': 'bringup@example.invalid'}).stdout.strip()


INIT_EXTRA = ['--name', NAME, '--linker-script', 'link.ld', '--ram-region', 'ram', '--reset-pc', '0x80000000',
              '--db-top', 'tiny.TinyCore']


def apply_adapter(core, env):
    """The guide's manual mapping step, done with prepared files. Returns notes."""
    core = Path(core)
    shutil.copy(HERE / 'CoreAdapter.scala', core / 'rvw/src/main/scala/rvwcore/CoreAdapter.scala')
    run = core / 'rvw/run.sh'
    text = run.read_text()
    notes = []
    # The scaffold answers `info` from a static block that claims `scaffold: true`. A mapped
    # adapter must answer from the Driver, so the block goes once the signals are mapped.
    block = re.search(r'if \[ "\$\{1:-\}" = info \].*?\nfi\n', text, re.S)
    if block:
        run.write_text(text.replace(block.group(0), ''))
        notes.append('removed the static scaffold info block from rvw/run.sh')
    built = run_group([str(core / 'tests/build.sh')], env=env, timeout=120, capture=True, text=True)
    if built.returncode:
        raise RuntimeError('tests/build.sh failed: ' + (built.stderr or '')[-400:])
    cosim = core / 'rvw/cosim.json'
    if cosim.is_file():
        data = json.loads(cosim.read_text())
        if data.pop('review_required', None) is not None:
            cosim.write_text(json.dumps(data, indent=2) + '\n')
            notes.append('reviewed rvw/cosim.json: M-only RV32I, no MMIO, no traps; removed review_required')
    return notes


def prepare_project(core, *, rvw_home=None):
    """A clean tiny-core repository with mapped rvw project files, committed (for native tasks)."""
    core = Path(core)
    env = environment(Path(rvw_home or WORKSTATION).resolve())
    shutil.copytree(HERE / 'core', core)
    def git(*args):
        subprocess.run(['git', *args], cwd=core, check=True, capture_output=True, text=True,
                       env={**env, 'GIT_AUTHOR_NAME': 'rvw-bench', 'GIT_AUTHOR_EMAIL': 'bench@example.invalid',
                            'GIT_COMMITTER_NAME': 'rvw-bench', 'GIT_COMMITTER_EMAIL': 'bench@example.invalid'})
    git('init', '-q')
    git('add', '-A')
    git('commit', '-qm', 'tiny core')
    result = run_group([str(Path(sys.executable).with_name('rvw')), 'init', '--isa', 'rv32i', '--wire-build', *INIT_EXTRA],
                       cwd=str(core), env=env, timeout=120, capture=True, text=True)
    if result.returncode:
        raise RuntimeError('rvw init failed: ' + (result.stdout or '')[-400:] + (result.stderr or '')[-400:])
    toml = core / 'rvw.toml'
    toml.write_text(toml.read_text().replace("include = ['^smoke$']", "include = ['^(smoke|arith|branch|mem)$']"))
    apply_adapter(core, env)
    git('add', '-A')
    git('commit', '-qm', 'rvw project')
    return core


def seed(core, replacement, original=FIX, path='src/main/scala/tiny/TinyCore.scala'):
    """Replace one statement of the clean fixture core (the seeded defect)."""
    source = Path(core) / path
    text = source.read_text()
    if text.count(original) != 1:
        raise ValueError(f'{path}: the statement to seed must occur once')
    source.write_text(text.replace(original, replacement))


def _subst(arg, values):
    return re.sub(r'<([A-Z_]+)>', lambda m: str(values.get(m.group(1), m.group(0))), arg)


def _json(result):
    try:
        return json.loads(result.stdout)
    except (TypeError, ValueError):
        return None


def environment(rvw_home):
    env = {k: v for k, v in os.environ.items() if k not in ('RVW_PROJECT', 'RVW_CORE', 'RVW_CORE_SOURCE')}
    env['RVW_HOME'] = str(rvw_home)
    env['RVW_PYTHON'] = sys.executable
    env['RVW_LOCK_PYTHON'] = sys.executable
    env['PATH'] = os.pathsep.join([str(Path(sys.executable).parent), env.get('PATH', '')])
    return env


def run_check(out, *, rvw_home=None, timeout=1800, workflows=('bring-up', 'test-fails')):
    out = Path(out)
    if out.exists():
        raise ValueError(f'{out} exists; use a new output directory')
    rvw_home = Path(rvw_home or WORKSTATION).resolve()
    walk = Walk(out, timeout=timeout, env=environment(rvw_home))
    started = time.monotonic()
    shutil.copytree(HERE / 'core', walk.core)
    seed(walk.core, BUG)
    walk.git('init', '-q')
    walk.git('add', '-A')
    walk.git('commit', '-qm', 'tiny core')
    smoke = walk.core / 'rvw/out/programs/smoke'
    values = {'ISA': 'rv32i', 'ELF': smoke, 'RUN': out / 'runs/quick', 'REV': walk.git('rev-parse', 'HEAD')}

    # bring-up: doctor before any project file must say what is missing.
    walk.record('bring-up', 'doctor', expect='exit 1; project not ready',
                check=lambda r: r.returncode == 1 or f'exit {r.returncode}')
    init_extra = INIT_EXTRA
    walk.record('bring-up', 'init-plan', subst=values, cli_extra=init_extra, expect='exit 0; status planned',
                check=lambda r: (_json(r) or {}).get('status') == 'planned' or f'exit {r.returncode}')
    walk.record('bring-up', 'init', subst=values, cli_extra=init_extra, expect='exit 0; files written',
                check=lambda r: (r.returncode == 0 and (walk.core / 'rvw.toml').is_file()) or f'exit {r.returncode}')
    if not (walk.core / 'rvw.toml').is_file():
        return finish(walk, started, rvw_home)
    walk.record('bring-up', 'doctor', expect='exit 1; project ready, adapter not ready',
                check=lambda r: r.returncode == 1 or f'exit {r.returncode}',
                note='second doctor run after init')

    def map_adapter():
        notes = apply_adapter(walk.core, walk.env)
        walk.git('add', '-A')
        walk.git('commit', '-qm', 'map the adapter')
        values['REV'] = walk.git('rev-parse', 'HEAD')
        return '; '.join(notes)
    if not walk.action('bring-up', 'map-adapter', 'copy the mapped adapter, build ELFs, review cosim.json, commit',
                       map_adapter):
        return finish(walk, started, rvw_home)
    walk.record('bring-up', 'smoke', subst=values, expect='exit 0; smoke run passes',
                check=lambda r: r.returncode == 0 or f'exit {r.returncode}')
    walk.record('bring-up', 'regress-list', expect='exit 0; smoke listed',
                check=lambda r: (r.returncode == 0 and 'smoke' in r.stdout) or f'exit {r.returncode}')
    quick = walk.record('bring-up', 'quick', subst=values, expect='exit 0; all pass')
    trace = _find(out / 'runs/quick', 'rvfi.jsonl')
    values['RUN'] = trace.parent if trace else out / 'runs/quick'
    walk.record('bring-up', 'cosim', subst=values, expect='exit 0; match',
                check=lambda r: (r.returncode == 0 and (_json(r) or {}).get('status') == 'match') or f'exit {r.returncode}')
    gate = walk.record('bring-up', 'gate', subst=values, expect='exit 0; accept on the committed revision',
                       check=lambda r: (r.returncode == 0 and 'accept' in r.stdout.lower()) or f'exit {r.returncode}')
    walk.record('bring-up', 'design-db', expect='exit 0; database written',
                check=lambda r: (r.returncode == 0 and (walk.core / 'rvw/out/design.db').is_file()) or f'exit {r.returncode}')

    if 'test-fails' in workflows:
        arith = walk.core / 'rvw/out/programs/arith'
        failing = out / 'runs/arith'
        walk.record('test-fails', 'failing-run', argv=[str(walk.core / 'rvw/run.sh'), 'run', '--elf', str(arith),
                                                       '--out', str(failing), '--seed', '1', '--rvfi-trace', '--json'],
                    expect='exit 1; status fail (the seeded sub bug)',
                    check=lambda r: (_json(r) or {}).get('status') == 'fail' or f'exit {r.returncode}')
        fail_values = {**values, 'RUN': failing, 'ELF': arith}
        walk.record('test-fails', 'bundle', subst=fail_values, expect='exit 0; bundle written')
        walk.record('test-fails', 'cosim', subst=fail_values, expect='exit 1; mismatch at the sub retirement',
                    check=lambda r: (_json(r) or {}).get('status') == 'mismatch' or f'exit {r.returncode}')
        walk.record('test-fails', 'drivers', subst={**fail_values, 'SIGNAL': 'regs_13'},
                    cli_extra=['--db', str(walk.core / 'rvw/out/design.db')], expect='exit 0; drivers of x13 (a3)')

        def fix():
            path = walk.core / 'src/main/scala/tiny/TinyCore.scala'
            text = path.read_text()
            if BUG not in text:
                raise RuntimeError('seeded statement not found')
            path.write_text(text.replace(BUG, FIX))
            toml = walk.core / 'rvw.toml'
            toml.write_text(toml.read_text().replace("include = ['^smoke$']", "include = ['^(smoke|arith)$']"))
            walk.git('add', '-A')
            walk.git('commit', '-qm', 'fix sub and add arith to the smoke suite')
            return 'sub computes a - b; arith joins the smoke suite'
        base = values['REV']
        walk.action('test-fails', 'fix', 'apply the one-line fix and commit', fix)
        walk.record('test-fails', 'gate', subst={**values, 'REV': base}, expect='exit 0; accept with arith passing',
                    check=lambda r: (r.returncode == 0 and 'accept' in r.stdout.lower()) or f'exit {r.returncode}')
    return finish(walk, started, rvw_home)


def _find(root, name):
    hits = sorted(Path(root).rglob(name)) if Path(root).exists() else []
    return hits[0] if hits else None


def finish(walk, started, rvw_home):
    works = sum(s['status'] == 'works' for s in walk.steps)
    report = {'schema': SCHEMA, 'workstation': str(rvw_home), 'core': str(walk.core),
              'seconds': round(time.monotonic() - started, 1), 'steps': walk.steps,
              'summary': {'steps': len(walk.steps), 'works': works, 'rough_edges': len(walk.steps) - works},
              'status': 'works' if works == len(walk.steps) else 'rough_edges'}
    (walk.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    return report
