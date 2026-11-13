"""Checked campaigns retain failures and reject stale resumes."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from rvw.workloads import rtl

pytestmark = pytest.mark.fast


def test_campaign_resume_and_failure(tmp_path, monkeypatch):
    project = tmp_path / 'rvw.toml'
    project.write_text('project')
    source = tmp_path / 'source'
    source.mkdir()
    settings = tmp_path / 'bench.json'
    settings.write_text(json.dumps({'schema': 'rvw.rtl-bench-settings/1',
        'programs': ['vvadd', 'median'], 'source': str(source),
        'target': {'march': 'rv32im', 'abi': 'ilp32', 'ram_base': '0x80000000', 'ram_size': '0x1000000'}}))
    monkeypatch.setattr(rtl, 'load_config', lambda **kw: SimpleNamespace(
        default_config='default', configs=['default'], adapter=['adapter'], source_repo=None, input_env=[]))
    monkeypatch.setattr(rtl.subprocess, 'check_output', lambda *a, **kw: b'fixed')
    def build(manifest, source, out, cc, bench, target, keep_going):
        out.mkdir()
        rows = []
        for name in ('vvadd', 'median'):
            elf = out / name
            elf.write_bytes(name.encode())
            rows.append({'id': name, 'elf': str(elf), 'elf_sha256': rtl.core.digest(elf)})
        rtl.save(out / 'build.json', {'workloads': rows})
    monkeypatch.setattr(rtl.core, 'build', build)
    calls = []
    def execute(cmd, out, **kw):
        calls.append(cmd)
        out.mkdir()
        (out / 'rvfi.jsonl').write_text('trace')
        good = 'vvadd' in cmd.get('elf')
        data = {'status': 'pass' if good else 'fail', 'instret': 10, 'cycles': 20}
        return SimpleNamespace(run=SimpleNamespace(get=data.get, inconclusive=None),
                               returncode=0 if good else 1, dir=out, error=None, wall=0.1)
    monkeypatch.setattr(rtl, 'execute', execute)
    kw = dict(out=tmp_path / 'out', project=project, settings=settings, repeats=2)
    result = rtl.run(**kw)
    assert len(calls) == 4
    assert result['status'] == 'fail'
    assert result['workloads'][0]['ipc'] == .5
    assert result['workloads'][0]['deterministic'] is True
    assert result['workloads'][1]['ipc'] is None
    assert 'triage' in result['workloads'][1]
    assert not list((tmp_path / 'out').rglob('rvfi.jsonl'))
    assert rtl.run(**kw, resume=True) == result
    assert len(calls) == 4
    with pytest.raises(ValueError, match='inputs differ'):
        rtl.run(**{**kw, 'repeats': 1}, resume=True)
    (tmp_path / 'out/build/vvadd').write_bytes(b'changed')
    with pytest.raises(ValueError, match='ELF changed'):
        rtl.run(**kw, resume=True)


def test_rv32_build_target(tmp_path):
    from rvw.workloads import core
    source = tmp_path / 'input'
    source.mkdir()
    (source / 'code').write_text('pinned')
    compiler = tmp_path / 'compiler'
    compiler.write_text('#!/usr/bin/env python3\nimport sys\nfrom pathlib import Path\n'
        'if "--version" in sys.argv: print("test compiler 1"); sys.exit(0)\n'
        'header=bytearray(64); header[:6]=b"\\x7fELF\\x01\\x01"; header[18:20]=b"\\xf3\\x00"\n'
        'Path(sys.argv[1]).write_bytes(header)\n')
    compiler.chmod(0o755)
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'schema': 'rvw.workloads/1', 'compiler_version': 'test compiler 1',
        'source_sha256': core.tree_hash(source), 'workloads': [{'id': 'small', 'mode': 'bare',
        'stdout_sha256': core.EMPTY, 'build': ['{cc}', '{out}/workload.elf']}]}))
    result = core.build(manifest, source, tmp_path / 'build32', str(compiler), target={'march': 'rv32im'})
    assert result['target'] == {'march': 'rv32im'}
    with pytest.raises(ValueError, match='RV64 ELF'):
        core.build(manifest, source, tmp_path / 'build64', str(compiler))
