"""C8 mutation regressions at baseline and control boundaries."""
from pathlib import Path
import hashlib
import json
import shutil
import sqlite3

import pytest
from race_injection import race_injector
from rvw.cov import mutation
from rvw.common.capture import Capture


@pytest.fixture
def mcy_project(tmp_path, monkeypatch):
    project = tmp_path / 'project'
    project.mkdir()
    (project / 'config.mcy').write_text('[files]\ndesign.sv\n')
    (project / 'baseline.sh').write_text('exit 0\n')
    (project / 'design.sv').write_text('module dut; endmodule\n')
    (project / 'nested').mkdir()
    (project / 'nested/test-options.svh').write_text('original\n')
    tools = tmp_path / 'bin'
    tools.mkdir()
    for name in ('bash', 'mcy', 'yosys'):
        path = tools / name
        path.write_text('#!/bin/sh\necho fixture-version\n')
        path.chmod(0o755)
    monkeypatch.setenv('PATH', str(tools))
    observed = []
    def run_job(argv, cwd, log, timeout):
        observed.append((Path(argv[0]).name, (cwd / 'nested/test-options.svh').read_text()))
        if argv[1:] == ['init']:
            (cwd / 'database').mkdir()
            with sqlite3.connect(cwd / 'database/db.sqlite3') as db:
                db.executescript('CREATE TABLE mutations(mutation_id INTEGER, mutation TEXT);'
                                 'CREATE TABLE tags(mutation_id INTEGER, tag TEXT);'
                                 'CREATE TABLE results(mutation_id INTEGER, test TEXT, result TEXT);'
                                 'CREATE TABLE queue(mutation_id INTEGER, test TEXT, running INTEGER);'
                                 'CREATE TABLE files(filename TEXT, data BLOB);')
                db.execute('INSERT INTO files VALUES(?,?)', ('design.sv', (cwd / 'design.sv').read_bytes()))
                db.execute('INSERT INTO mutations VALUES(0, "mutate -mode none")')
                db.execute('INSERT INTO results VALUES(0, "sim", "PASS")')
                db.execute('INSERT INTO mutations VALUES(1, "mutate -mode inv")')
                db.execute('INSERT INTO results VALUES(1, "sim", "FAIL")')
        return 0
    monkeypatch.setattr(mutation, 'run_job', run_job)
    return project, observed


@pytest.mark.parametrize('script', [
    'tmp=$(mktemp -d {out}.XXXXXX)\ntest -d "$tmp"\nrm -r "$tmp"\n',
    'tmp="$(mktemp -d "{out}.XXXXXX")"\ntest -d "$tmp"\nrm -r "$tmp"\n',
    'printf generated > {out}\ntest "$(cat {out})" = generated\n',
    'printf generated >"{out}"\ntest "$(cat "{out}")" = generated\n',
    'printf generated 2> {out}\ntest -f {out}\n',
])
def test_shell_outputs_use_private_scratch(mcy_project, monkeypatch, script):
    import os
    from rvw.common.proc import run_group
    project, _ = mcy_project
    out = project.parent / 'outputs/result'
    (project / 'baseline.sh').write_text('set -eu\n' + script.format(out=out))
    (project / 'rvw-external-inputs').write_text('[]')
    execute = mutation.run_job
    seen = []

    def run(argv, cwd, log, timeout):
        if log.name == 'baseline.log':
            content = (cwd / 'baseline.sh').read_text()
            scratch = log.parent / 'scratch' / out.relative_to('/')
            assert str(scratch) in content
            result = run_group(['/bin/bash', str(cwd / 'baseline.sh')], cwd=cwd,
                               env={'PATH': os.defpath}, capture=True, timeout=timeout)
            assert result.returncode == 0, result
            seen.append(content)
        return execute(argv, cwd, log, timeout)

    monkeypatch.setattr(mutation, 'run_job', run)
    result = mutation.mutate(project, run=True, baseline=project / 'baseline.sh')
    assert seen and result['status'] == 'complete'
    assert not out.parent.exists()


@pytest.mark.parametrize('option', ['-o ', '-o', '--output ', '--output='])
def test_compiler_output_options_are_relocated(mcy_project, monkeypatch, option):
    project, _ = mcy_project
    out = project.parent / 'outputs/sim'
    (project / 'baseline.sh').write_text(f'iverilog {option}{out} design.sv\nvvp {out}\n')
    (project / 'rvw-external-inputs').write_text('[]')
    execute = mutation.run_job

    def run(argv, cwd, log, timeout):
        if log.name == 'baseline.log':
            scratch = log.parent / 'scratch' / out.relative_to('/')
            script = (cwd / 'baseline.sh').read_text()
            assert f'iverilog {option}{scratch} design.sv' in script
            assert f'vvp {scratch}' in script
        return execute(argv, cwd, log, timeout)

    monkeypatch.setattr(mutation, 'run_job', run)
    assert mutation.mutate(project, run=True, baseline=project / 'baseline.sh')['status'] == 'complete'


def test_output_relocation_preserves_existing_live_file(mcy_project, monkeypatch):
    import os
    from rvw.common.proc import run_group
    project, _ = mcy_project
    out = project.parent / 'result.txt'
    out.write_text('live contents\n')
    (project / 'baseline.sh').write_text(f'printf private > "{out}"\n')
    (project / 'rvw-external-inputs').write_text('[]')
    execute = mutation.run_job

    def run(argv, cwd, log, timeout):
        if log.name == 'baseline.log':
            rc = run_group(['/bin/bash', str(cwd / 'baseline.sh')], cwd=cwd,
                           env={'PATH': os.defpath}, capture=True, timeout=timeout)
            assert rc.returncode == 0
            assert (log.parent / 'scratch' / out.relative_to('/')).read_text() == 'private'
        return execute(argv, cwd, log, timeout)

    monkeypatch.setattr(mutation, 'run_job', run)
    assert mutation.mutate(project, run=True, baseline=project / 'baseline.sh')['status'] == 'complete'
    assert out.read_text() == 'live contents\n'


@pytest.mark.parametrize('script', [
    'cat {path} > /tmp/generated.log',
    'cat {path}\nprintf output > {path}',
    'cat >> {path}',  # Append needs the initial contents.
    'cat <> {path}',  # Read/write redirection needs the initial contents.
    'unknown-tool -o {path}',
    'mktemp -d /tmp/result.XXXXXX\ncat {path}',
    'echo "literal > {path}"\ncat {path}',
    "echo '(iverilog -o {path})'\ncat {path}",
    '# iverilog -o {path}\ncat {path}',
    'echo \\> {path}\ncat {path}',
])
def test_output_syntax_keeps_real_input_checks(mcy_project, script):
    project, observed = mcy_project
    (project / 'rvw-external-inputs').write_text('[]')
    (project / 'baseline.sh').write_text(script.format(path='/undeclared/input'))
    with pytest.raises(ValueError, match='undeclared.*[/]undeclared/input'):
        mutation.mutate(project, run=True, baseline=project / 'baseline.sh')
    assert observed == []


def test_real_mcy_output_template_options_and_redirection(tmp_path):
    example = Path(__file__).resolve().parents[2] / 'examples/coverage'
    project = tmp_path / 'project'
    project.mkdir()
    for name in ('tiny.sv', 'tb.sv', 'config.mcy', 'test_sim.sh', 'baseline.sh'):
        shutil.copyfile(example / name, project / name)
    out = tmp_path / 'live-output'
    script = project / 'baseline.sh'
    script.write_text(script.read_text()
                      .replace('mktemp -d', 'mktemp -d /tmp/rvw-mutation.XXXXXX')
                      .replace('"$tmp/sim"', f'"{out}/sim"')
                      .replace('vvp ' + f'"{out}/sim"' + ' | tee "$tmp/result"',
                               f'vvp "{out}/sim" > "{out}/result"')
                      .replace('"$tmp/result"', f'"{out}/result"'))
    (project / 'rvw-external-inputs').write_text('[]')
    result = mutation.mutate(project, run=True, baseline=script)
    assert result['status'] == 'complete', result
    assert result['counts']['killed'] == 10 and result['counts']['survived'] == 13
    assert result['counts']['control'] == 1 and not out.exists()
    assert mutation.mutate(project)['counts'] == result['counts']


@pytest.mark.parametrize('revert', [False, True])
def test_mutation_transitive_project_inputs_are_frozen(mcy_project, race_injector, revert):
    project, observed = mcy_project
    header = project / 'nested/test-options.svh'
    edit = race_injector.file(mutation, 'run_job', header, b'changed\n', replace=True, revert=revert)
    result = mutation.mutate(project, run=True, baseline=project / 'baseline.sh')
    assert edit.fired
    assert observed == [('bash', 'original\n'), ('mcy', 'original\n'), ('mcy', 'original\n')]
    assert result['status'] == 'inconclusive'
    assert result['cause'] == 'input_not_captured:mcy_dependencies'
    assert result['counts']['killed'] == 0 and result['observed_counts']['killed'] == 1
    assert result['cache_key'] is None and result['generation']




def test_generation_inspection_keeps_refusal_and_applies_test_selection(mcy_project):
    project, _ = mcy_project
    result = mutation.mutate(project, run=True, baseline=project / 'baseline.sh')
    inspected = mutation.mutate(project, detection_tests=['other'])
    assert inspected['generation'] == result['generation']
    assert inspected['status'] == 'inconclusive' and inspected['counts']['killed'] == 0
    assert inspected['observed_counts']['pending'] == 2
    assert inspected['detection_tests'] == ['other']


def _legacy_copy(project, result, target):
    workspace = project / 'rvw-results/generations' / result['generation'] / 'workspace'
    work = next(workspace.rglob('config.mcy')).parent
    target.mkdir()
    shutil.copytree(work / 'database', target / 'database')
    shutil.copyfile(work / 'config.mcy', target / 'config.mcy')
    assert (work / 'database/db.sqlite3').read_bytes() == (target / 'database/db.sqlite3').read_bytes()
    return target


@pytest.mark.parametrize('add_declaration', [False, True])
@pytest.mark.parametrize('control', ['PASS', 'FAIL', 'missing'])
def test_legacy_mutation_database_keeps_only_observations(mcy_project, rvw, add_declaration, control):
    project, _ = mcy_project
    fresh = mutation.mutate(project, run=True, baseline=project / 'baseline.sh')
    legacy = _legacy_copy(project, fresh, project.parent / 'legacy')
    if add_declaration:
        # A declaration added after execution cannot establish the run's dependencies.
        (legacy / 'rvw-external-inputs').write_text('[]')
    if control != 'PASS':
        # This is a separate legacy fixture. copytree preserved the sealed source modes.
        (legacy / 'database').chmod(0o700)
        (legacy / 'database/db.sqlite3').chmod(0o600)
        with sqlite3.connect(legacy / 'database/db.sqlite3') as db:
            if control == 'missing':
                db.execute('DELETE FROM mutations WHERE mutation_id=0')
            else:
                db.execute('UPDATE results SET result=? WHERE mutation_id=0', (control,))
    rc, _, result = rvw('cov', 'mutate', legacy, '--json')
    assert rc == 3
    assert result['status'] == 'inconclusive'
    assert result['cause'] == 'input_not_captured:mcy_dependencies'
    assert result['dependency_complete'] is False and result['cache_key'] is None
    assert all(result['counts'][state] == 0 for state in ('killed', 'survived', 'equivalent', 'control'))
    assert result['observed_counts']['killed'] == 1
    if control == 'PASS':
        assert result['observed_counts'] == fresh['observed_counts']
        assert result['counts'] == fresh['counts']
        assert [r['observed_state'] for r in result['mutants']] == ['control', 'killed']
        assert all(r['state'] == 'inconclusive' for r in result['mutants'])


@pytest.mark.parametrize('missing', ['none', 'capture', 'trees', 'tools', 'problems', 'dependency_declaration',
                                   'manifest', 'external', 'tool'])
def test_all_v1_generations_keep_only_observations(mcy_project, missing):
    from rvw.results.generation import publish
    project, _ = mcy_project
    (project / 'rvw-external-inputs').write_text('[]')
    result = mutation.mutate(project, run=True, baseline=project / 'baseline.sh')
    assert result['schema'] == 'rvw.mutation/2' and result['counts']['killed'] == 1
    # /1 once allowed dependency_complete without complete capture evidence.
    # Even fully populated /1 evidence must remain historical observations.
    result['schema'] = 'rvw.mutation/1'
    if missing == 'none':
        pass
    elif missing in ('capture', 'dependency_declaration'):
        result.pop(missing)
    elif missing == 'problems':
        result['capture']['problems'] = ['input_not_captured:external']
    elif missing == 'manifest':
        result['dependency_declaration'].pop('manifest')
    elif missing == 'external':
        result['dependency_declaration']['paths'].append('../uncaptured')
    elif missing == 'tool':
        result['capture']['tools'].pop()
    else:
        result['capture'][missing] = []
    publish(project / 'rvw-results', lambda directory:
            (directory / 'result.json').write_text(json.dumps(result)))
    inspected = mutation.mutate(project)
    assert inspected['status'] == 'inconclusive'
    assert inspected['cause'] == 'input_not_captured:mcy_dependencies'
    assert inspected['dependency_complete'] is False
    assert inspected['counts']['killed'] == inspected['counts']['equivalent'] == 0
    assert inspected['observed_counts']['killed'] == 1


def test_real_mcy_legacy_unknown_dependencies(tmp_path, rvw):
    # Reproduce review22-cosim/probe_legacy_unknown.py with a byte-identical legacy DB.
    example = Path(__file__).resolve().parents[2] / 'examples/coverage'
    project = tmp_path / 'project'
    project.mkdir()
    for name in ('tiny.sv', 'tb.sv', 'config.mcy', 'test_sim.sh', 'baseline.sh'):
        shutil.copyfile(example / name, project / name)
    fresh = mutation.mutate(project, run=True, baseline=project / 'baseline.sh')
    legacy = _legacy_copy(project, fresh, tmp_path / 'legacy')
    result = mutation.mutate(legacy)
    assert result['status'] == 'inconclusive'
    assert result['cause'] == 'input_not_captured:mcy_dependencies'
    assert result['counts'] == fresh['counts']
    assert result['observed_counts'] == fresh['observed_counts']
    assert result['observed_counts']['killed'] == 10
    assert result['observed_counts']['survived'] == 13
    assert result['observed_counts']['control'] == 1
    rc, _, cli = rvw('cov', 'mutate', legacy, '--json')
    assert rc == 3 and cli['counts'] == result['counts']
    from rvw.cov.mcp_tools import mcp_tools
    from rvw.mcp.registry import Registry
    registry = Registry(mcp_tools())
    try:
        _, job, error = registry.call_json('cov_mutate', {'project': str(legacy), 'lock': ''})
        assert not error, job
        _, status, error = registry.call_json('job_status', {'job_id': job['job_id'], 'wait_s': 60})
        assert not error and status['status'] == 'done', status
        for key in ('status', 'cause', 'dependency_complete', 'counts', 'observed_counts'):
            assert status['result'][key] == cli[key] == result[key]
    finally:
        registry.jobs.shutdown()


@pytest.mark.parametrize('revert', [False, True])
def test_declared_empty_inputs_earn_outcomes_and_survive_inspection(mcy_project, race_injector, revert):
    project, _ = mcy_project
    declaration = project / 'rvw-external-inputs'
    declaration.write_text('[]\n')
    edit = race_injector.file(mutation, 'run_job', declaration, b'["missing"]\n',
                              replace=True, revert=revert)
    result = mutation.mutate(project, run=True, baseline=project / 'baseline.sh')
    assert edit.fired
    assert result['counts']['killed'] == 1
    assert result['dependency_complete'] is True
    assert result['dependency_declaration']['claim'] == 'declared complete by the user'
    assert result['dependency_declaration']['paths'] == []
    assert result['cache_key'] is None
    assert mutation.mutate(project)['counts'] == result['counts']


@pytest.mark.parametrize('expression', ['a/2', 'a /2', '(a)/2', 'a / 2', 'a /* divide */ /2'])
def test_declared_hdl_arithmetic_is_not_an_absolute_path(mcy_project, expression):
    project, _ = mcy_project
    (project / 'rvw-external-inputs').write_text('[]')
    source = f'module dut(input [7:0] a, output [7:0] y); assign y = {expression}; endmodule\n'
    (project / 'design.sv').write_text(source)
    result = mutation.mutate(project, run=True, baseline=project / 'baseline.sh')
    assert result['status'] == 'complete' and result['counts']['killed'] == 1
    generation = project / 'rvw-results/generations' / result['generation']
    executed = generation / 'workspace' / project.relative_to('/') / 'design.sv'
    assert executed.read_text() == source


@pytest.mark.parametrize('statement', ['`include "/unlisted/options.svh"',
                                     'initial $readmemh("/unlisted/rom.hex", mem);',
                                     'initial $readmemb("/unlisted/rom.bin", mem);'])
def test_declared_hdl_undeclared_path_still_refuses(mcy_project, statement):
    project, observed = mcy_project
    (project / 'rvw-external-inputs').write_text('[]')
    (project / 'design.sv').write_text(f'module dut; {statement}\nendmodule\n')
    with pytest.raises(ValueError, match='undeclared absolute path /unlisted/'):
        mutation.mutate(project, run=True, baseline=project / 'baseline.sh')
    assert observed == []


@pytest.mark.parametrize('command', [
    "sed -n '/PASS/p' result.txt",
    "test -n \"$(sed -n '/PASS/p' \"$tmp/result\")\"",
    "sed -n -e '/PASS/p' result.txt",
    "sed --expression='/PASS/p' result.txt",
    "sed -e 's|/prefix/|/replacement/|' result.txt",
    "grep -q '/PASS/' result.txt",
    "grep -e '/PASS/' result.txt",
])
def test_shell_regex_arguments_are_data(mcy_project, command):
    project, _ = mcy_project
    (project / 'rvw-external-inputs').write_text('[]')
    script = command + '\n'
    (project / 'baseline.sh').write_text(script)
    result = mutation.mutate(project, run=True, baseline=project / 'baseline.sh')
    assert result['status'] == 'complete' and result['counts']['killed'] == 1
    work = project / 'rvw-results/generations' / result['generation'] / 'workspace' / project.relative_to('/')
    assert (work / 'baseline.sh').read_text() == script


@pytest.mark.parametrize('command', [
    "sed -n '/PASS/p' /unlisted/input",
    "sed -n -f /unlisted/program result.txt",
    "sed --file=/unlisted/program result.txt",
    "sed -n '/PASS/r /unlisted/input' result.txt",
    "sed -n '/PASS/r/unlisted/input' result.txt",
    "sed 'r/unlisted/input' result.txt",
    "sed 's|/prefix/||w /unlisted/output' result.txt",
    "sed 's|/prefix/||w/unlisted/output' result.txt",
    "grep -e '/PASS/' /unlisted/input",
    "grep '/PASS/' result.txt </unlisted/input",
    'cc -I/unlisted/include design.c',
    'cat grep /unlisted/input',
    'grep "$(cat /unlisted/pattern)" result.txt',
    'sed -n "/$(cat /unlisted/pattern)/p" result.txt',
])
def test_shell_file_arguments_still_refuse(mcy_project, command):
    project, observed = mcy_project
    (project / 'rvw-external-inputs').write_text('[]')
    (project / 'baseline.sh').write_text(command + '\n')
    with pytest.raises(ValueError, match='undeclared absolute path /unlisted/'):
        mutation.mutate(project, run=True, baseline=project / 'baseline.sh')
    assert observed == []


@pytest.mark.parametrize('prefix', ["sed -n '/PASS/r", "sed 'r"])
def test_sed_attached_declared_input_uses_copy(mcy_project, monkeypatch, prefix):
    import re
    project, _ = mcy_project
    external = project.parent / 'patterns.txt'
    external.write_text('captured input\n')
    (project / 'rvw-external-inputs').write_text(json.dumps([str(external)]))
    (project / 'baseline.sh').write_text(f"{prefix}{external}' result.txt\n")
    execute = mutation.run_job

    def run(argv, cwd, log, timeout):
        if log.name == 'baseline.log':
            path = Path(re.search(r"r(/[^']+)'", (cwd / 'baseline.sh').read_text())[1])
            assert path != external
            assert path.read_text() == 'captured input\n'
            assert path.is_relative_to(log.parent / 'workspace')
        return execute(argv, cwd, log, timeout)

    monkeypatch.setattr(mutation, 'run_job', run)
    result = mutation.mutate(project, run=True, baseline=project / 'baseline.sh')
    assert result['status'] == 'complete'


def test_real_mcy_baseline_sed_expression(tmp_path):
    example = Path(__file__).resolve().parents[2] / 'examples/coverage'
    project = tmp_path / 'project'
    project.mkdir()
    for name in ('tiny.sv', 'tb.sv', 'config.mcy', 'test_sim.sh', 'baseline.sh'):
        shutil.copyfile(example / name, project / name)
    baseline = project / 'baseline.sh'
    original = baseline.read_text()
    rewritten = original.replace("grep -q '^PASS$' \"$tmp/result\"",
                                 "test -n \"$(sed -n '/PASS/p' \"$tmp/result\")\"")
    assert rewritten != original
    baseline.write_text(rewritten)
    (project / 'rvw-external-inputs').write_text('[]')
    result = mutation.mutate(project, run=True, baseline=baseline)
    assert result['status'] == 'complete'
    assert (result['counts']['killed'], result['counts']['survived'], result['counts']['control']) == (10, 13, 1)
    assert mutation.mutate(project)['counts'] == result['counts']


@pytest.mark.parametrize('stage', ['baseline', 'init'])
def test_failed_mutation_stage_keeps_bounded_log_evidence(mcy_project, monkeypatch, stage):
    project, _ = mcy_project
    execute = mutation.run_job
    def fail(argv, cwd, log, timeout):
        if log.name == stage + '.log':
            log.write_text('prefix' * 2000 + '\nuseful failure detail\n')
            return 7
        return execute(argv, cwd, log, timeout)
    monkeypatch.setattr(mutation, 'run_job', fail)
    with pytest.raises(ValueError) as error:
        mutation.mutate(project, run=True, baseline=project / 'baseline.sh')
    message = str(error.value)
    assert 'useful failure detail' in message
    assert len(message) < 5000
    assert '.building-' not in message
    assert not (project / 'rvw-results/current').exists()


def test_mutation_mcp_help_describes_declaration():
    from rvw.cov.mcp_tools import mcp_tools
    spec = next(spec for spec in mcp_tools() if spec.name == 'cov_mutate')
    assert 'rvw-external-inputs' in spec.description
    assert 'Fresh runs return inconclusive because' not in spec.description


@pytest.mark.parametrize('absolute', [False, True])
@pytest.mark.parametrize('revert', [False, True])
def test_declared_external_inputs_run_only_from_copies(mcy_project, monkeypatch, race_injector,
                                                      absolute, revert):
    project, _ = mcy_project
    external = project.parent / 'dependencies'
    external.mkdir()
    header = external / 'options.svh'
    header.write_text('original external\n')
    lookup = str(header) if absolute else '../dependencies/options.svh'
    (project / 'baseline.sh').write_text(f'cat {lookup}\n')
    (project / 'rvw-external-inputs').write_text(json.dumps([str(external) if absolute else '../dependencies']))
    execute = mutation.run_job
    consumed = []

    def read_dependency(argv, cwd, log, timeout):
        if Path(argv[0]).name == 'bash':
            path = (cwd / 'baseline.sh').read_text().split()[1]
            consumed.append((cwd / path).read_text())
        return execute(argv, cwd, log, timeout)

    monkeypatch.setattr(mutation, 'run_job', read_dependency)
    edit = race_injector.file(mutation, 'run_job', header, b'changed external\n',
                              replace=True, revert=revert)
    result = mutation.mutate(project, run=True, baseline=project / 'baseline.sh')
    assert edit.fired and consumed == ['original external\n']
    assert result['counts']['killed'] == 1 and result['dependency_complete']
    record = next(r for r in result['capture']['files'] if r['source'] == str(header))
    assert record['sha256'] == hashlib.sha256(b'original external\n').hexdigest()


@pytest.mark.parametrize('declared', [False, True])
def test_missing_declaration_explains_how_to_declare(mcy_project, capsys, declared):
    project, _ = mcy_project
    if declared:
        (project / 'rvw-external-inputs').write_text('[]')
    result = mutation.mutate(project, run=True, baseline=project / 'baseline.sh')
    stderr = capsys.readouterr().err
    if declared:
        assert result['counts']['killed'] == 1
    else:
        assert result['status'] == 'inconclusive'
        assert 'rvw-external-inputs' in stderr and '[]' in stderr and 'JSON' in stderr


@pytest.mark.parametrize('contents', ['{}', 'null', '[1]', '["missing"]'])
def test_bad_declaration_refuses_before_execution(mcy_project, contents):
    project, observed = mcy_project
    (project / 'rvw-external-inputs').write_text(contents)
    with pytest.raises(ValueError, match='input_not_captured:'):
        mutation.mutate(project, run=True, baseline=project / 'baseline.sh')
    assert observed == []


@pytest.mark.parametrize('revert', [False, True])
def test_undeclared_absolute_input_is_refused_from_captured_script(mcy_project, race_injector, revert):
    project, observed = mcy_project
    script = project / 'baseline.sh'
    script.write_text('cat /unlisted/options.svh\n')
    (project / 'rvw-external-inputs').write_text('[]')
    edit = race_injector.file(Capture, 'tree', script, b'exit 0\n',
                              when='after', replace=True, revert=revert)
    with pytest.raises(ValueError, match='undeclared.*[/]unlisted'):
        mutation.mutate(project, run=True, baseline=script)
    assert edit.fired and observed == []


def test_declared_run_keeps_equivalence_separate_from_detection(mcy_project, monkeypatch, race_injector):
    project, _ = mcy_project
    (project / 'rvw-external-inputs').write_text('[]')

    execute = mutation.run_job

    def run(argv, cwd, log, timeout):
        rc = execute(argv, cwd, log, timeout)
        if argv[1:] == ['run', '-j', '1']:
            with sqlite3.connect(cwd / 'database/db.sqlite3') as db:
                db.execute('UPDATE results SET result="PASS"')
                db.execute('INSERT INTO results VALUES(0, "eq", "PASS")')
                db.execute('INSERT INTO results VALUES(1, "eq", "PASS")')
        return rc

    monkeypatch.setattr(mutation, 'run_job', run)
    edit = race_injector.file(mutation, 'run_job', project / 'design.sv', b'changed live\n', revert=True)
    result = mutation.mutate(project, run=True, baseline=project / 'baseline.sh',
                             detection_tests=['sim'], equivalence_tests=['eq'])
    assert edit.fired
    assert result['counts']['equivalent'] == 1 and result['counts']['killed'] == 0
    assert mutation.mutate(project, detection_tests=['sim'], equivalence_tests=['eq'])['counts'] == result['counts']


@pytest.fixture
def campaign_with_roles(mcy_project, monkeypatch):
    project, _ = mcy_project
    (project / 'rvw-external-inputs').write_text('[]')
    execute = mutation.run_job

    def run(argv, cwd, log, timeout):
        rc = execute(argv, cwd, log, timeout)
        if argv[1:] == ['run', '-j', '1']:
            with sqlite3.connect(cwd / 'database/db.sqlite3') as db:
                db.execute('INSERT INTO mutations VALUES(2, "mutate -mode inv")')
                db.execute('INSERT INTO results VALUES(2, "sim", "PASS")')
                db.executemany('INSERT INTO results VALUES(?, "eq", ?)',
                               [(0, 'PASS'), (1, 'FAIL'), (2, 'FAIL')])
        return rc

    monkeypatch.setattr(mutation, 'run_job', run)
    result = mutation.mutate(project, run=True, baseline=project / 'baseline.sh',
                             detection_tests=['sim'], equivalence_tests=['eq'])
    assert result['status'] == 'complete'
    assert result['counts']['killed'] == result['counts']['survived'] == 1
    return project, result


def test_inspection_defaults_preserve_saved_roles(campaign_with_roles, rvw):
    from rvw.cov.cli import execute_json
    project, original = campaign_with_roles
    rc, _, cli = rvw('cov', 'mutate', project, '--json')
    assert rc == 0
    for result in (mutation.mutate(project), mutation.mutation_report(project), cli,
                   execute_json('mutate', project=str(project))):
        for key in ('counts', 'mutants', 'detection_tests', 'equivalence_tests', 'generation'):
            assert result[key] == original[key], key


def test_inspection_overrides_only_explicit_roles(campaign_with_roles, rvw):
    from rvw.cov.cli import execute_json
    project, _ = campaign_with_roles
    rc, _, cli = rvw('cov', 'mutate', project, '--test', 'other', '--json')
    assert rc == 3  # The requested test has no unmutated control.
    assert cli['equivalence_tests'] == ['eq']
    assert cli['detection_tests'] == ['other'] and cli['counts']['pending'] == 3
    for result in (mutation.mutate(project, equivalence_tests=[]),
                   execute_json('mutate', project=str(project), equivalence_test=[])):
        assert result['equivalence_tests'] == []
        assert result['detection_tests'] == ['sim']
    assert mutation.mutate(project, detection_tests=None)['detection_tests'] is None
    # Inspection is read-only, including when the roles are changed.
    assert mutation.mutate(project)['equivalence_tests'] == ['eq']


def test_mcp_inspection_preserves_saved_roles(campaign_with_roles):
    from rvw.cov.mcp_tools import mcp_tools
    from rvw.mcp.registry import Registry
    project, original = campaign_with_roles
    registry = Registry(mcp_tools())
    try:
        _, job, error = registry.call_json('cov_mutate', {'project': str(project), 'lock': ''})
        assert not error, job
        _, status, error = registry.call_json('job_status', {'job_id': job['job_id'], 'wait_s': 60})
        assert not error and status['status'] == 'done', status
        for key in ('counts', 'mutants', 'detection_tests', 'equivalence_tests', 'generation'):
            assert status['result'][key] == original[key], key
    finally:
        registry.jobs.shutdown()


@pytest.mark.parametrize('missing', ['detection_tests', 'equivalence_tests'])
def test_saved_generation_without_roles_is_inconclusive(campaign_with_roles, missing):
    from rvw.results.generation import publish
    project, result = campaign_with_roles
    result.pop(missing)
    publish(project / 'rvw-results', lambda directory:
            (directory / 'result.json').write_text(json.dumps(result)))
    inspected = mutation.mutate(project)
    assert inspected['status'] == 'inconclusive'
    assert inspected['cause'] == 'input_not_captured:mcy_test_roles'
    assert inspected['counts']['killed'] == inspected['counts']['equivalent'] == 0


def test_declared_run_failure_never_publishes_conclusive_kills(mcy_project, monkeypatch, race_injector):
    project, _ = mcy_project
    (project / 'rvw-external-inputs').write_text('[]')
    execute = mutation.run_job

    def fail(argv, cwd, log, timeout):
        rc = execute(argv, cwd, log, timeout)
        return 7 if argv[1:] == ['run', '-j', '1'] else rc

    monkeypatch.setattr(mutation, 'run_job', fail)
    edit = race_injector.file(mutation, 'run_job', project / 'design.sv', b'changed live\n', revert=True)
    result = mutation.mutate(project, run=True, baseline=project / 'baseline.sh')
    assert edit.fired and result['status'] == 'inconclusive'
    assert result['cause'] == 'mcy_run_failed' and result['counts']['killed'] == 0
    assert mutation.mutate(project)['counts']['killed'] == 0


@pytest.mark.parametrize('absolute', [None, False, True])
def test_real_mcy_declared_external_header(tmp_path, race_injector, absolute):
    # This test needs the normal suite environment with MCY, Yosys and Icarus installed.
    example = Path(__file__).resolve().parents[2] / 'examples/coverage'
    project = tmp_path / 'project'
    project.mkdir()
    for name in ('tiny.sv', 'tb.sv', 'config.mcy', 'test_sim.sh', 'baseline.sh'):
        shutil.copyfile(example / name, project / name)
    header = tmp_path / 'options.svh'
    header.write_text('`define RVW_CAPTURED_OPTIONS 1\n')
    lookup = str(header) if absolute else '../options.svh'
    source = project / 'tiny.sv'
    if absolute is not None:
        source.write_text(f'`include "{lookup}"\n' + source.read_text())
    (project / 'rvw-external-inputs').write_text(json.dumps([] if absolute is None else [lookup]))
    edit = race_injector.file(mutation, 'run_job', header, b'`include "missing.svh"\n',
                              replace=True, revert=True)
    result = mutation.mutate(project, run=True, baseline=project / 'baseline.sh')
    assert edit.fired and result['status'] == 'complete'
    counts = result['counts']
    assert counts['killed'] > 0 and counts['survived'] > 0
    assert counts['killed'] + counts['survived'] == 23
    assert counts['control'] == 1 and counts['pending'] == counts['error'] == 0
    if absolute is None:
        assert counts['killed'] == 10 and counts['survived'] == 13


def test_declared_empty_directory_is_materialized(mcy_project, monkeypatch, race_injector):
    project, _ = mcy_project
    external = project.parent / 'empty'
    external.mkdir()
    declaration = project / 'rvw-external-inputs'
    declaration.write_text('["../empty"]')
    execute = mutation.run_job

    def run(argv, cwd, log, timeout):
        assert (cwd.parent / 'empty').is_dir()
        return execute(argv, cwd, log, timeout)

    monkeypatch.setattr(mutation, 'run_job', run)
    edit = race_injector.file(mutation, 'run_job', declaration, b'[]', revert=True)
    result = mutation.mutate(project, run=True, baseline=project / 'baseline.sh')
    assert edit.fired and result['counts']['killed'] == 1


def test_relative_declaration_preserves_symlink_parent_semantics(mcy_project, monkeypatch, race_injector):
    project, _ = mcy_project
    actual = project.parent / 'actual'
    actual.mkdir()
    shutil.move(project, actual / 'project')
    project.symlink_to(actual / 'project', target_is_directory=True)
    external = actual / 'options.svh'
    external.write_text('correct\n')
    # Lexical removal of project/.. would capture this unrelated sibling instead.
    (project.parent / 'options.svh').write_text('wrong\n')
    (project / 'rvw-external-inputs').write_text('["../options.svh"]')
    execute = mutation.run_job

    def run(argv, cwd, log, timeout):
        assert (cwd.parent / 'options.svh').read_text() == 'correct\n'
        return execute(argv, cwd, log, timeout)

    monkeypatch.setattr(mutation, 'run_job', run)
    edit = race_injector.file(mutation, 'run_job', external, b'changed\n', replace=True, revert=True)
    result = mutation.mutate(project, run=True, baseline=project / 'baseline.sh')
    assert edit.fired and result['counts']['killed'] == 1


def test_declared_directory_symlink_uses_captured_target(mcy_project, monkeypatch, race_injector):
    project, _ = mcy_project
    actual = project.parent / 'actual-dependencies'
    actual.mkdir()
    header = actual / 'options.svh'
    header.write_text('correct\n')
    alias = project.parent / 'dependencies'
    alias.symlink_to(actual, target_is_directory=True)
    (project / 'rvw-external-inputs').write_text('["../dependencies"]')
    execute = mutation.run_job

    def run(argv, cwd, log, timeout):
        assert (cwd.parent / 'dependencies/options.svh').read_text() == 'correct\n'
        return execute(argv, cwd, log, timeout)

    monkeypatch.setattr(mutation, 'run_job', run)
    edit = race_injector.file(mutation, 'run_job', header, b'changed\n', replace=True, revert=True)
    result = mutation.mutate(project, run=True, baseline=project / 'baseline.sh')
    assert edit.fired and result['counts']['killed'] == 1


@pytest.mark.parametrize('control', ['FAIL', 'ERROR', 'pending', 'missing-result', 'missing-control'])
@pytest.mark.parametrize('revert', [False, True])
def test_failed_or_missing_control_invalidates_campaign(mcy_project, monkeypatch, race_injector,
                                                        control, revert):
    from rvw.cov.cli import execute_json
    project, _ = mcy_project
    (project / 'rvw-external-inputs').write_text('[]')
    execute = mutation.run_job

    def run(argv, cwd, log, timeout):
        rc = execute(argv, cwd, log, timeout)
        if argv[1:] == ['run', '-j', '1']:
            with sqlite3.connect(cwd / 'database/db.sqlite3') as db:
                if control == 'missing-control':
                    db.execute('DELETE FROM mutations WHERE mutation_id=0')
                elif control == 'missing-result':
                    db.execute('DELETE FROM results WHERE mutation_id=0')
                elif control == 'pending':
                    db.execute('INSERT INTO queue VALUES(0, "sim", 0)')
                else:
                    db.execute('UPDATE results SET result=? WHERE mutation_id=0', (control,))
        return rc

    monkeypatch.setattr(mutation, 'run_job', run)
    race = race_injector.file(mutation, 'run_job', project / 'design.sv', b'changed live',
                              replace=True, revert=revert)
    result = mutation.mutate(project, run=True, baseline=project / 'baseline.sh')
    assert race.fired
    assert result['status'] == 'inconclusive'
    assert result['cause'] in ('mcy_control_failed', 'mcy_control_missing')
    assert result['counts']['killed'] == result['counts']['equivalent'] == 0
    assert result['observed_counts']['killed'] == 1
    assert result['run_exit_code'] == result['baseline']['exit_code'] == 0
    assert result['control_failures']
    inspected = execute_json('mutate', project=str(project))
    assert inspected['status'] == 'inconclusive'
    assert inspected['counts'] == result['counts']


def test_control_failure_cli_and_mcp_agree(mcy_project, monkeypatch, rvw):
    from rvw.cov.cli import execute_json
    project, _ = mcy_project
    (project / 'rvw-external-inputs').write_text('[]')
    execute = mutation.run_job
    def run(argv, cwd, log, timeout):
        rc = execute(argv, cwd, log, timeout)
        if argv[1:] == ['run', '-j', '1']:
            with sqlite3.connect(cwd / 'database/db.sqlite3') as db:
                db.execute('UPDATE results SET result="FAIL" WHERE mutation_id=0')
        return rc
    monkeypatch.setattr(mutation, 'run_job', run)
    rc, _, result = rvw('cov', 'mutate', project, '--run', '--baseline', project / 'baseline.sh', '--json')
    assert rc == 3 and result['counts']['killed'] == 0
    mcp = execute_json('mutate', project=str(project))
    assert mcp['status'] == result['status'] == 'inconclusive'
    assert mcp['cause'] == result['cause'] == 'mcy_control_failed'
    assert mcp['observed_counts']['killed'] == 1


def test_fresh_campaign_refuses_missing_tool_capture_before_publishing_v2(mcy_project, monkeypatch):
    from rvw.results.generation import GenerationError
    project, _ = mcy_project
    (project / 'rvw-external-inputs').write_text('[]')
    original = Capture.record

    def record(capture):
        result = original(capture)
        result['tools'] = [tool for tool in result['tools'] if not tool['path'].endswith('/mcy')]
        return result

    monkeypatch.setattr(Capture, 'record', record)
    with pytest.raises(GenerationError, match='incomplete fresh-run tool evidence'):
        mutation.mutate(project, run=True, baseline=project / 'baseline.sh')
    assert not (project / 'rvw-results/current').exists()


def test_mcy_identity_uses_selected_executable_without_version_wrapper(mcy_project):
    import os
    project, _ = mcy_project
    (project / 'rvw-external-inputs').write_text('[]')
    mcy = Path(os.environ['PATH']) / 'mcy'
    mcy.write_text('#!/bin/sh\nexit 9\n')  # MCY has no successful --version interface.
    result = mutation.mutate(project, run=True, baseline=project / 'baseline.sh')
    identity = result['tools']['mcy']
    assert identity['executable'] == str(mcy.resolve())
    assert identity['sha256'] == hashlib.sha256(mcy.read_bytes()).hexdigest()
    assert any(tool['path'] == identity['executable'] and tool['sha256'] == identity['sha256']
               for tool in result['capture']['tools'])
    assert result['counts']['killed'] == 1
