"""Round-20 capture regressions, with real formal tools and named race boundaries."""
import hashlib
import json
import os
import re
import shlex
import shutil
import sys

import pytest

from race_injection import race_injector
from rvw.cli import main
from rvw.formal import common

PASS = 'module t(input clk, input reset); always @(posedge clk) assert(1); endmodule\n'
FAIL = PASS.replace('assert(1)', 'assert(0)')
needs_tools = pytest.mark.skipif(
    not all(shutil.which(t) for t in ('yosys', 'sby', 'yices-smt2')),
    reason='needs yosys, sby and yices-smt2',
)


def bmc(source, out):
    return main(['formal', 'bmc', '--verilog', str(source), '--top', 't', '--depth', '3',
                 '--timeout', '30', '--out', str(out), '--json'])


@needs_tools
@pytest.mark.parametrize('replace', [False, True])
def test_symlink_parent_captures_the_selected_input(tmp_path, race_injector, replace):
    parent = tmp_path / 'real'
    (parent / 'child').mkdir(parents=True)
    link = tmp_path / 'link'
    link.symlink_to(parent / 'child', target_is_directory=True)
    selected_file = parent / 'design.v'
    selected_file.write_text(FAIL)
    (tmp_path / 'design.v').write_text(PASS)
    selected = link / '../design.v'
    assert selected.read_text() == FAIL
    # Both permanent replacement and edit-and-revert after capture must use the first bytes.
    hook = race_injector.file(common, 'module_ports', selected_file, PASS.encode(),
                              replace=replace, revert=not replace)
    out = tmp_path / 'out'
    assert bmc(selected, out) == 1
    assert hook.fired
    result = json.loads((out / 'result.json').read_text())
    assert result['status'] == 'fail'
    item = result['input_snapshot']['files'][0]
    assert item['original'] == str(selected)
    assert item['resolved'] == str(selected_file)
    assert item['sha256'] == hashlib.sha256(FAIL.encode()).hexdigest()
    assert item['symlinks'] == [{'path': str(link), 'target': str(parent / 'child')}]
    captured = next(f for f in result['input_capture']['files'] if f['source'] == str(selected))
    assert captured['sha256'] == item['sha256']
    assert captured['symlinks'] == item['symlinks']


@needs_tools
@pytest.mark.parametrize('replace,revert', [(True, False), (False, True)])
@pytest.mark.parametrize('selected', ['yosys', 'sby', 'yices-smt2', 'yosys-witness'])
def test_changed_tool_cannot_publish_a_pass(tmp_path, monkeypatch, race_injector, replace, revert, selected):
    import os
    import shlex
    real = shutil.which(selected)
    bindir = tmp_path / 'bin'
    bindir.mkdir()
    wrapper = bindir / selected
    original = '#!/bin/sh\nexec ' + shlex.quote(real) + ' "$@"\n'
    wrapper.write_text(original)
    wrapper.chmod(0o755)
    monkeypatch.setenv('PATH', str(bindir) + os.pathsep + os.environ['PATH'])
    changed = '#!/bin/sh\n# changed after proof\nexec ' + shlex.quote(real) + ' "$@"\n'
    hook = race_injector.file(common, 'tool_versions', wrapper, changed.encode(),
                              replace=replace, revert=revert)
    source = tmp_path / 'design.v'
    source.write_text(PASS)
    out = tmp_path / 'out'
    assert bmc(source, out) == 1
    assert hook.fired
    result = json.loads((out / 'result.json').read_text())
    assert result['status'] == 'unknown'
    assert result['cause'].startswith('input_not_captured:tool:')
    binding = result['tool_bindings'][selected]
    assert binding['input']['sha256'] == hashlib.sha256(original.encode()).hexdigest()
    assert result['tools'][selected] == binding['command']['version'].strip().splitlines()[0]


@needs_tools
@pytest.mark.parametrize('flow', ['bmc', 'xprop', 'from-sim'])
def test_tools_keep_their_first_paths_and_solver_binding(tmp_path, monkeypatch, race_injector, flow):
    import os
    import shlex
    bindir = tmp_path / 'bin'
    bindir.mkdir()
    solver_log = tmp_path / 'solver.log'
    solver = bindir / 'yices-smt2'
    solver.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> ' + shlex.quote(str(solver_log))
                      + '\nexec ' + shlex.quote(shutil.which('yices-smt2')) + ' "$@"\n')
    solver.chmod(0o755)
    original_path = str(bindir) + os.pathsep + os.environ['PATH']
    monkeypatch.setenv('PATH', original_path)
    trapdir = tmp_path / 'traps'
    trapdir.mkdir()
    trap_log = tmp_path / 'trap.log'
    for name in ('yosys', 'sby', 'yices-smt2', 'vcd2fst', 'fst2vcd'):
        trap = trapdir / name
        trap.write_text('#!/bin/sh\necho unexpected >> ' + shlex.quote(str(trap_log)) + '\nexit 99\n')
        trap.chmod(0o755)
    hook = race_injector.at(common, 'module_ports',
                            lambda: monkeypatch.setenv('PATH', str(trapdir) + os.pathsep + original_path))
    source = tmp_path / 'design.v'
    source.write_text(PASS.replace('input reset', 'input reset, output y').replace('always @', 'assign y=0; always @'))
    out = tmp_path / 'out'
    extra = ['--outputs'] if flow == 'xprop' else []
    if flow == 'from-sim':
        trace = tmp_path / 'trace.vcd'
        trace.write_text('$timescale 1ns $end\n$scope module t $end\n'
                         '$var wire 1 ! clk $end\n$var wire 1 r reset $end\n'
                         '$var wire 1 y y $end\n$upscope $end\n$enddefinitions $end\n'
                         '#0\n0!\n0r\n0y\n#5\n1!\n#10\n0!\n')
        extra = ['--trace', str(trace), '--scope', 't', '--time', '5']
    assert main(['formal', flow, '--verilog', str(source), '--top', 't', '--depth', '6',
                 '--timeout', '30', '--out', str(out), *extra]) == 0
    assert hook.fired
    assert not trap_log.exists()
    # Ignore the start-of-command version query. Both the proof and cover must
    # execute the selected wrapper, even through the release Python launcher.
    calls = solver_log.read_text().splitlines()
    assert sum('--incremental' in line for line in calls) >= 2
    result = json.loads((out / 'result.json').read_text())
    assert result['input_capture']['problems'] == []
    assert result['input_capture']['env']['PATH'] == original_path
    assert result['tools']['yices-smt2'].startswith('Yices')
    sby_log = (out / 'sby.log').read_text()
    assert str(out / 'inputs' / 'tools' / 'yosys') in sby_log
    assert str(out / 'inputs' / 'tools' / 'yosys-smtbmc') in sby_log


@needs_tools
@pytest.mark.parametrize('selected', ['yosys', 'yices-smt2'])
@pytest.mark.parametrize('settings', ['unset', 'set'])
def test_python_forwarding_tool_uses_caller_python_environment(tmp_path, monkeypatch,
                                                              selected, settings):
    real_tool = shutil.which(selected)
    bindir = tmp_path / 'bin'
    bindir.mkdir()
    forward = tmp_path / 'forward.py'
    forward.write_text('import os, sys\n'
                       + f'os.execv({real_tool!r}, [{real_tool!r}, *sys.argv[1:]])\n')
    log = tmp_path / 'python-env.log'
    wrapper = bindir / selected
    caller = {'PYTHONHOME': None, 'PYTHONEXECUTABLE': None,
              'PYTHONPATH': str(tmp_path), 'PYTHONUSERBASE': str(tmp_path / 'user'),
              'PYTHONNOUSERSITE': None}
    if settings == 'set':
        caller.update(PYTHONHOME=sys.base_prefix, PYTHONEXECUTABLE=sys.executable,
                      PYTHONNOUSERSITE='1')
    for name, value in caller.items():
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    wrapper.write_text('#!/bin/sh\n'
                       + 'printf "%s|%s|%s|%s|%s\\n" '
                       + ' '.join('"${' + name + '-unset}"' for name in caller)
                       + ' >> ' + shlex.quote(str(log)) + '\n'
                       + 'exec ' + shlex.quote(sys.executable) + ' '
                       + shlex.quote(str(forward)) + ' "$@"\n')
    wrapper.chmod(0o755)
    monkeypatch.setenv('PATH', str(bindir) + os.pathsep + os.environ['PATH'])
    source = tmp_path / 'top.sv'
    source.write_text(PASS)
    out = tmp_path / 'out'
    assert bmc(source, out) == 0
    assert set(log.read_text().splitlines()) == {
        '|'.join('unset' if value is None else value for value in caller.values())}
    captured = json.loads((out / 'result.json').read_text())['input_capture']['env']
    assert {name: captured[name] for name in caller} == caller


@needs_tools
@pytest.mark.parametrize('engine', ['smtbmc:abc', 'smtbmc:yices, smtbmc:abc',
                                    'smtbmc:abc:--unroll'])
def test_smtbmc_abc_is_refused_before_proof(tmp_path, capsys, engine):
    source = tmp_path / 'top.sv'
    source.write_text(PASS)
    out = tmp_path / 'out'
    with pytest.raises(SystemExit) as exc:
        main(['formal', 'bmc', '--verilog', str(source), '--top', 't',
              '--depth', '4', '--engine', engine, '--out', str(out)])
    assert exc.value.code == 2
    error = capsys.readouterr().err
    assert 'smtbmc:abc' in error
    assert 'Yosys ' in error
    assert re.search(r'yosys-abc sha256=[0-9a-f]{64}', error)
    assert not (out / 'result.json').exists()
    assert not (out / 'bmc.sby').exists()
    assert not (out / 'sby.log').exists()
