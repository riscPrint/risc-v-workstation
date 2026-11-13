"""The native campaign must forward the selected assertion engine."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('engine', ['abc bmc3', 'smtbmc bitwuzla'])
def test_engine_reaches_project_binding(tmp_path, monkeypatch, engine):
    path = Path(__file__).resolve().parents[2]/'examples/vexriscv/formal/run_sail_m.py'
    spec = importlib.util.spec_from_file_location('sail_m_example', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    widths = module.monitor(32)[2]
    ports = ['input wire clk', 'input wire reset']
    ports += [f'output wire [{w-1}:0] rvfi_{name}' for name,w in widths.items()]
    rtl = tmp_path/'core.v'
    rtl.write_text('module VexRiscv ('+','.join(ports)+'); endmodule\n')
    files = {}
    for name in module.NAMES:
        raw = ('model '+name).encode()
        (tmp_path/f'insn_{name}.v').write_bytes(raw)
        files[name] = {'model_sha256': hashlib.sha256(raw).hexdigest()}
    (tmp_path/'manifest.json').write_text(json.dumps({'schema':'rvw.sail-m/1','files':files}))
    class Captured(Exception):
        pass
    def capture(manifest, out):
        plan = json.loads(Path(manifest).read_text())
        assert plan['check_options']['insn_mul_ch0'] == {'cycles':[20], 'engine':engine}
        assert plan['check_options']['cover']['engine'] == 'smtbmc bitwuzla'
        raise Captured
    monkeypatch.setattr(module, 'generate', capture)
    monkeypatch.setattr(sys, 'argv', ['run_sail_m', '--rtl',str(rtl), '--riscv-formal',str(tmp_path),
        '--models',str(tmp_path), '--out',str(tmp_path/'out'), '--checks','mul', '--engine',engine])
    with pytest.raises(Captured):
        module.main()
