"""Real native reverse replay through the shared snapshot-port API."""
import importlib.util
import json
import os
from pathlib import Path
import shutil

from rvw.common.proc import run_group
from rvw.sim.live import capture
from rvw.sim.reverse import reverse_step
from rvw.sim import checkpoint

EXAMPLE = Path(__file__).resolve().parents[1]


def test_reverse_replay_real_core(tmp_path):
    elf = tmp_path / 'smoke'
    gcc = os.environ.get('RISCV_PREFIX', 'riscv64-unknown-elf-') + 'gcc'
    built = run_group([gcc, '-march=rv32im_zicsr_zifencei', '-mabi=ilp32', '-nostdlib',
        '-nostartfiles', '-T', str(EXAMPLE / 'programs/link.ld'), str(EXAMPLE / 'programs/smoke.S'),
        '-o', str(elf)], timeout=30, capture=True, text=True)
    assert built.returncode == 0, built.stderr
    manifest = tmp_path / 'port.json'
    manifest.write_text(json.dumps(dict(schema='rvw.snapshot-adapter/1',
        module=str(EXAMPLE / 'checkpoint_port.py'), options=dict(elf=str(elf), launcher=str(EXAMPLE / 'checkpoint-probe.sh')),
        identity_files=dict(rtl=[str(EXAMPLE / 'src/main/scala/rvwvex/VexTop.scala')],
            native_build=[shutil.which('verilator'), shutil.which('c++'), shutil.which('java')],
            harness=[str(EXAMPLE / 'src/main/scala/rvwvex/CheckpointProbe.scala')], stimulus=[str(elf)]))))
    early = tmp_path / 'early.json'
    capture(manifest, early, instruction=8)
    result = reverse_step(manifest, [early], tmp_path / 'reversed.json', current=15,
                          target=10, max_seconds=600)
    assert result['target'] == 10 and result['restored_instruction'] == 8
    envelope = json.loads((tmp_path / 'reversed.json').read_text())['payload']
    assert envelope['state']['counters']['instructions'] == 10
    import base64
    saved = json.loads(base64.b64decode(envelope['native']))['state']
    assert saved['retired'] == '10'
    # Compare replayed prefix with an independent from-reset checkpoint at N.
    reference = tmp_path / 'reference.json'
    capture(manifest, reference, instruction=10)
    ref_payload = json.loads(reference.read_text())['payload']
    assert saved == json.loads(base64.b64decode(ref_payload['native']))['state']
