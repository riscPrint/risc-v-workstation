"""Each advertised adapter config must emit its own complete, bound C2 stream."""
import json
from types import SimpleNamespace

import pytest

from rvw.doctor import c1suite
from rvw.doctor.check import diagnose
from test_doctor_conformance import trace_file

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('fault', ['', 'missing', 'config', 'end'])
def test_c2_per_config(tmp_path, monkeypatch, fault):
    calls = []
    def run(args, **kwargs):
        from pathlib import Path
        config = args[args.index('--config') + 1]
        out = Path(args[args.index('--out') + 1]); out.mkdir(parents=True)
        calls.append(config)
        result = dict(schema='rvw.run/1', core='test', config=config, status='pass', seed=7,
                      max_cycles=100000, cycles=2, instret=1, elf_sha256='a'*64, rtl_sha256='b'*64,
                      artifacts={'rvfi_trace': 'rvfi.jsonl'})
        (out/'result.json').write_text(json.dumps(result))
        if fault != 'missing':
            trace_file(out, config='wrong' if fault == 'config' else config,
                       end=None if fault == 'end' else 'pass')
        return SimpleNamespace(returncode=0, stderr='')
    monkeypatch.setattr(c1suite, 'run_group', run)
    cfg = SimpleNamespace(adapter=['adapter'], path=tmp_path/'rvw.toml', name='test', configs=['a','b'])
    info = dict(configs=['a','b'], xlen=32, isa={'a':'rv32im','b':'rv32im'})
    result = c1suite.c2_conformance(cfg, info, tmp_path/'smoke')
    assert calls == ['a','b']
    if fault:
        assert any(c['status'] == 'error' for c in result)
    else:
        assert sum(c['name'].endswith('.c2') and c['status'] == 'ready' for c in result) == 2
        assert all(c['status'] == 'inconclusive' for c in result if c['name'].endswith('c2_mapping'))
