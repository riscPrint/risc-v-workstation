"""Coverage proofs must bind the solver through the release launchers."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil

import pytest

from race_injection import race_injector
from rvw.common.capture import CaptureError
from rvw.common.proc import run_group
from rvw.cov import proof
from .test_proof import TINY, _setup, needs_sby


def _counter(tmp_path):
    dut, harness = TINY.split('module h')
    return _setup(tmp_path, 'module h' + harness, "s == 2'd3", dut=dut, extra={'reset': None})


def _script(path, body):
    path.write_text('#!/bin/sh\n' + body)
    path.chmod(0o755)
    return path


@needs_sby
def test_release_launcher_uses_selected_z3_version(tmp_path, monkeypatch, race_injector):
    smtbmc = Path(shutil.which('yosys-smtbmc')).resolve()
    if 'release_bindir' not in smtbmc.read_text():
        pytest.skip('needs the OSS CAD Suite smtbmc launcher')
    suite_z3 = smtbmc.with_name('z3')
    suite_version = run_group([str(suite_z3), '--version'], capture=True, timeout=10).stdout.strip()
    candidates = [Path(p) / 'z3' for p in os.environ['PATH'].split(os.pathsep)]
    other = next((p.resolve() for p in candidates if p.is_file()
                  and run_group([str(p), '--version'], capture=True, timeout=10).stdout.strip() != suite_version), None)
    if other is None:
        pytest.skip('needs a second installed Z3 version')
    selected_version = run_group([str(other), '--version'], capture=True, timeout=10).stdout.strip()
    bindir = tmp_path / 'bin'
    bindir.mkdir()
    solver_log = tmp_path / 'solver.log'
    solver = _script(bindir / 'z3', 'printf "%s\\n" "$*" >> ' + shlex.quote(str(solver_log))
                     + '\nexec ' + shlex.quote(str(other)) + ' "$@"\n')
    selected_hash = hashlib.sha256(solver.read_bytes()).hexdigest()
    selected_path = str(bindir) + os.pathsep + os.environ['PATH']
    monkeypatch.setenv('PATH', selected_path)
    traps = tmp_path / 'traps'
    traps.mkdir()
    trap_log = tmp_path / 'trap.log'
    for name in ('z3', 'yosys', 'sby', 'yosys-smtbmc', 'yosys-witness'):
        _script(traps / name, 'echo unexpected >> ' + shlex.quote(str(trap_log)) + '\nexit 99\n')
    hook = race_injector.at(proof, 'elaborate', lambda: monkeypatch.setenv(
        'PATH', str(traps) + os.pathsep + selected_path), when='before')
    cfg, db = _counter(tmp_path)
    out = tmp_path / 'proof'
    result = proof.prove(cfg, db, out, timeout=20)
    assert hook.fired
    assert result['points'][0]['unreachable']
    assert proof.apply_exclusions(json.loads(db.read_text()), out / 'exclusions.json')['points'][0]['exclusion']
    # Version queries do not prove that smtio used this solver. Check its SMT calls.
    assert sum('-smt2 -in' in line for line in solver_log.read_text().splitlines()) >= 4
    assert not trap_log.exists()
    assert result['tools']['z3']['version'].strip() == selected_version
    assert result['tools']['z3']['sha256'] == selected_hash
    assert result['capture']['env']['PATH'] == selected_path
    binding = result['tool_bindings']['z3']
    assert binding['input']['resolved'] == str(solver)
    assert binding['input']['sha256'] == selected_hash
    for name in ('sby', 'yosys', 'yosys-smtbmc', 'yosys-witness', 'z3'):
        assert name in result['tool_bindings']
    log = (out / '0-prove.log').read_text()
    assert str(out / 'tool-bindings' / 'yosys') in log
    assert str(out / 'tool-bindings' / 'yosys-smtbmc') in log


@needs_sby
@pytest.mark.parametrize('replace,revert', [(True, False), (False, True)])
def test_changed_z3_cannot_publish_exclusions(tmp_path, monkeypatch, race_injector, replace, revert):
    real = shutil.which('z3')
    bindir = tmp_path / 'bin'
    bindir.mkdir()
    solver = _script(bindir / 'z3', 'exec ' + shlex.quote(real) + ' "$@"\n')
    monkeypatch.setenv('PATH', str(bindir) + os.pathsep + os.environ['PATH'])
    hook = race_injector.file(proof, 'elaborate', solver, solver.read_bytes() + b'# changed\n',
                              replace=replace, revert=revert)
    cfg, db = _counter(tmp_path)
    with pytest.raises(CaptureError, match='input_not_captured:tool:'):
        proof.prove(cfg, db, tmp_path / 'proof', timeout=20)
    assert hook.fired
    assert not (tmp_path / 'proof/exclusions.json').exists()


@needs_sby
def test_unbound_smtbmc_launcher_is_inconclusive(tmp_path, monkeypatch, race_injector, rvw):
    real = shutil.which('yosys-smtbmc')
    bindir = tmp_path / 'bin'
    bindir.mkdir()
    # An arbitrary launcher can change PATH again. Its solver lookup is unknown.
    launcher = _script(bindir / 'yosys-smtbmc', 'exec ' + shlex.quote(real) + ' "$@"\n')
    monkeypatch.setenv('PATH', str(bindir) + os.pathsep + os.environ['PATH'])
    hook = race_injector.file(proof.source_snapshot, 'create', launcher,
                              launcher.read_bytes() + b'# replaced launcher\n', replace=True)
    cfg, db = _counter(tmp_path)
    out = tmp_path / 'proof'
    code, _, result = rvw('cov', 'prove', db, '--config', cfg, '--work-dir', out, '--timeout', '20', '--json')
    assert hook.fired
    assert code == 3
    assert result['status'] == 'inconclusive'
    assert result['cause'] == 'input_not_captured:tool:z3'
    assert not (out / 'exclusions.json').exists()
