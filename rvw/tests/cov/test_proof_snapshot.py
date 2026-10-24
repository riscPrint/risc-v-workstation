"""Round 18: an edit followed by a revert must not change a solver's RTL inputs."""
import hashlib
import json
from pathlib import Path

import pytest

from rvw.cov import proof
from .test_proof import (INCLUDE_HARNESS, INCLUDE_POINT, TINY, _include_dut,
                         _setup, needs_sby)


@pytest.mark.parametrize('ending', [b'\r\n', b'\r'])
def test_snapshot_preserves_source_line_endings(tmp_path, ending):
    from rvw.cov import source_snapshot
    source, harness = tmp_path / 'dut.v', tmp_path / 'harness.sv'
    source.write_bytes(b'module dut;\nendmodule\n'.replace(b'\n', ending))
    harness.write_bytes(b'module h;\n// RVW_POINT\nendmodule\n'.replace(b'\n', ending))
    reference, manifest = source_snapshot.create(tmp_path, [source], harness, proof.check_script_paths)
    for entry in manifest['entries']:
        assert Path(entry['path']).read_bytes() == Path(entry['opened']).read_bytes()
    records = {str(p): proof.file_record(p) for p in [source, harness]}
    assert source_snapshot.verify(reference, [source], harness, records, tmp_path, proof.stale_record) == manifest


@needs_sby
@pytest.mark.parametrize('kind', ['source', 'nested-header'])
@pytest.mark.parametrize('stage', ['guard.log', '0-cover.log'])
def test_edit_and_revert_cannot_exclude_reachable_point(tmp_path, monkeypatch, kind, stage):
    dut = ('module dut(input clk,input a,input b,output reg q=0,output reg r=0);\n'
           'always @(posedge clk) begin q<=a; r<=b; end\nendmodule\n')
    harness = ('module h(input clk,input a,input b);\nwire q,r; dut d(clk,a,b,q,r);\n'
               'always @(posedge clk) begin\n// RVW_POINT\nend\nendmodule\n')
    if kind == 'source':
        cfg, db = _setup(tmp_path, harness, 'q != r', dut=dut, extra={'reset': None})
        target, changed = tmp_path / 'dut.v', dut.replace('r<=b', 'r<=a')
    else:
        target = tmp_path / 'defs.svh'
        target.write_text('`define ENABLE 1\n')
        outer = tmp_path / 'outer.svh'
        outer.write_text(f'`include "{target}"\n')
        cfg, db = _setup(tmp_path, INCLUDE_HARNESS, INCLUDE_POINT, dut=_include_dut(outer))
        changed = '`define ENABLE 0\n'
    original = target.read_text()
    real_run = proof.run_job
    events = []

    def edit_and_revert(argv, cwd, log, timeout):
        if Path(log).name == stage:
            target.write_text(changed)
            events.append('edit')
        rc = real_run(argv, cwd, log, timeout)
        if Path(log).name == '0-prove.log':
            target.write_text(original)
            events.append('revert')
        return rc

    monkeypatch.setattr(proof, 'run_job', edit_and_revert)
    result = proof.prove(cfg, db, tmp_path / 'proof', timeout=30)
    assert events == ['edit', 'revert'] and target.read_text() == original
    row = result['points'][0]
    assert not row['unreachable'], row
    assert row['jobs']['cover']['status'] == 'PASS'
    assert row['jobs']['prove']['status'] == 'FAIL'
    applied = proof.apply_exclusions(json.loads(db.read_text()), tmp_path / 'proof/exclusions.json')
    assert 'exclusion' not in applied['points'][0]
    assert result['source_snapshot']['sha256']
    for job in [result['sanity'], *row['jobs'].values()]:
        assert job['snapshot_sha256'] == result['source_snapshot']['sha256']
        assert job['input_hashes']
    # Import checks every job even when no point was excluded.
    copied = Path(row['jobs']['prove']['directory']) / 'src/dut.v'
    copied.write_text('// changed solver input\n')
    with pytest.raises(ValueError, match='snapshot|proof evidence'):
        proof.apply_exclusions(json.loads(db.read_text()), tmp_path / 'proof/exclusions.json')


@needs_sby
def test_apply_checks_snapshot_and_every_solver_copy(tmp_path):
    dut, harness = TINY.split('module h')
    cfg, db = _setup(tmp_path, 'module h' + harness, "s == 2'd3", dut=dut, extra={'reset': None})
    out = tmp_path / 'proof'
    result = proof.prove(cfg, db, out, timeout=30)
    data = json.loads(db.read_text())
    path = out / 'exclusions.json'
    assert proof.apply_exclusions(data, path)['points'][0]['exclusion']
    assert result['schema'] == 'rvw.coverage-exclusions/7'
    jobs = [result['sanity'], *result['points'][0]['jobs'].values(), result['points'][0]['cone']]
    for job in jobs:
        copied = Path(job['directory']) / 'src/dut.v'
        original = copied.read_bytes()
        copied.write_bytes(original + b'// changed\n')
        with pytest.raises(ValueError, match='snapshot|proof evidence'):
            proof.apply_exclusions(data, path)
        # Updating a self-reported job hash cannot change the snapshot it must match.
        edited = json.loads(path.read_text())
        def change_hash(obj):
            if isinstance(obj, dict):
                if obj.get('directory') == job['directory']:
                    obj['input_hashes'][str(copied)] = hashlib.sha256(copied.read_bytes()).hexdigest()
                for value in obj.values():
                    change_hash(value)
            elif isinstance(obj, list):
                for value in obj:
                    change_hash(value)
        change_hash(edited)
        bad = out / 'edited.json'
        bad.write_text(json.dumps(edited))
        with pytest.raises(ValueError, match='snapshot|proof evidence'):
            proof.apply_exclusions(data, bad)
        copied.write_bytes(original)
    for field in ['snapshot_sha256', 'input_hashes']:
        edited = json.loads(path.read_text())
        del edited['points'][0]['jobs']['prove'][field]
        bad = out / 'edited.json'
        bad.write_text(json.dumps(edited))
        with pytest.raises(ValueError, match='snapshot|proof evidence'):
            proof.apply_exclusions(data, bad)
    guard_copy = out / 'guard/dut.v'
    original = guard_copy.read_bytes()
    guard_copy.write_bytes(original + b'// changed guard input\n')
    with pytest.raises(ValueError, match='snapshot|proof evidence'):
        proof.apply_exclusions(data, path)
    guard_copy.write_bytes(original)
    manifest = json.loads(Path(result['source_snapshot']['path']).read_text())
    frozen = Path(manifest['entries'][0]['path'])
    frozen.chmod(0o644)
    frozen.write_text('// changed snapshot\n')
    with pytest.raises(ValueError, match='snapshot|proof evidence'):
        proof.apply_exclusions(data, path)


@pytest.mark.parametrize('directive', ['`include `HEADER', '`include "missing.svh"',
                                     '`define JOIN(a,b) a``b', '`define X ' + chr(92) + '\n1', '`__FILE__',
                                     '$readmemh("live.hex", memory);'])
def test_unsupported_snapshot_forms_refuse_before_tools(tmp_path, monkeypatch, directive):
    dut, harness = TINY.split('module h')
    cfg, db = _setup(tmp_path, 'module h' + harness, "s == 2'd3", dut=directive + '\n' + dut,
                     extra={'reset': None})
    monkeypatch.setattr(proof, 'run_job', lambda *a, **k: pytest.fail('tool read unsupported live input'))
    with pytest.raises(ValueError, match='snapshot'):
        proof.prove(cfg, db, tmp_path / 'proof')


def test_generated_property_cannot_add_a_live_include(tmp_path, monkeypatch):
    cfg, db = _setup(tmp_path, INCLUDE_HARNESS, '`include "/tmp/live.svh"')
    monkeypatch.setattr(proof, 'run_job', lambda *a, **k: pytest.fail('tool read unsupported live input'))
    with pytest.raises(ValueError, match='snapshot'):
        proof.prove(cfg, db, tmp_path / 'proof')


@needs_sby
def test_nested_header_snapshot_is_verified_on_apply(tmp_path):
    header = tmp_path / 'defs.svh'
    header.write_text('`define ENABLE 0\n')
    outer = tmp_path / 'outer.svh'
    outer.write_text(f'`include "{header}"\n')
    cfg, db = _setup(tmp_path, INCLUDE_HARNESS, INCLUDE_POINT, dut=_include_dut(outer))
    out = tmp_path / 'proof'
    result = proof.prove(cfg, db, out, timeout=30)
    path = out / 'exclusions.json'
    data = json.loads(db.read_text())
    assert proof.apply_exclusions(data, path)['points'][0]['exclusion']
    manifest = json.loads(Path(result['source_snapshot']['path']).read_text())
    entry = next(e for e in manifest['entries'] if e['opened'] == str(header))
    assert set(result['dependencies']) == {str(header), str(outer)}
    for field in ['raw', 'path']:
        target = Path(entry[field])
        original = target.read_bytes()
        target.chmod(0o644)
        target.write_bytes(b'`define ENABLE 1\n')
        with pytest.raises(ValueError, match='snapshot|proof evidence'):
            proof.apply_exclusions(data, path)
        target.write_bytes(original)
        target.chmod(0o444)
