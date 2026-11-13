"""Real core runs. No Spike-generated trace is a DUT fixture."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import pytest
from rvw.common.proc import run_group
from rvw.cosim.elf import Elf
from window_check import check_interrupts
from native_sdks import require_core

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize('core', ['boom', 'vexriscv'])
def test_core_interrupts(tmp_path, core):
    require_core(core)
    subprocess.run(['bash', str(ROOT / 'RiscvSim/tests/programs/build.sh')], check=True)
    programs = ROOT / 'RiscvSim/tests/programs/build'
    adapter = ROOT / 'RiscvSim/boom/run.sh'
    platform_args = ['--core', 'boom']
    xlen = 64
    sources = [('external', 11), ('timer', 7), ('software', 3)]
    if core == 'boom':
        sources.append(('delegated', 9))
    if core == 'vexriscv':
        if not os.environ.get('VEXRISCV'):
            pytest.skip('set VEXRISCV to run the VexRiscv adapter')
        xlen = 32
        adapter = ROOT / 'examples/vexriscv/rvw/run.sh'
        platform_args = ['--core', 'boom', '--platform', str(ROOT / 'examples/vexriscv/rvw/platform.json')]
        programs = tmp_path / 'programs'
        programs.mkdir()
        for name, _ in sources:
            source = ROOT / f'RiscvSim/tests/programs/interrupt-{name}.S'
            subprocess.run([os.environ.get('RISCV_GCC', 'riscv64-unknown-elf-gcc'), '-march=rv32im_zicsr',
                '-mabi=ilp32', '-DNO_PMP', '-nostdlib', '-nostartfiles', '-static',
                '-T', str(source.parent / 'link.ld'), '-o', str(programs / source.stem), str(source)], check=True)
    if core == 'vexriscv':
        unsupported = run_group([str(adapter), 'run', '--elf', str(programs / 'interrupt-external'),
            '--out', str(tmp_path / 'unsupported'), '--irq-schedule', '1:0x200'], capture=True, timeout=30)
        assert unsupported.returncode == 2
        assert 'adapter does not support these IRQ inputs' in unsupported.stdout + unsupported.stderr
    jobs = []
    for name, bit in sources:
        for masked in [False, True]:
            level = 1 << bit
            schedule = f'1:0x0,100:0x{level:x},200:0x0' + ('' if masked else f',1000:0x{level:x}')
            jobs.append(dict(elf=str(programs / f'interrupt-{name}'),
                             out=str(tmp_path / f'{name}-{masked}'), irq_schedule=schedule,
                             max_cycles=20000 if not masked else 3000, seed=1, mem_latency=0, rvfi_trace=True))
    manifest = tmp_path / 'jobs.jsonl'
    manifest.write_text(''.join(json.dumps(j)+'\n' for j in jobs))
    run = run_group([str(adapter), 'run-many', '--manifest', str(manifest), '--jobs', '1'], timeout=1200)
    assert run.returncode in (0, 1)
    for j in jobs:
        out = Path(j['out'])
        masked = out.name.endswith('True')
        c1 = json.loads((out / 'result.json').read_text())
        assert c1['status'] == ('timeout' if masked else 'pass'), c1
        assert c1['irq_schedule'] == j['irq_schedule']
        assert j['irq_schedule'] in c1['replay']
        assert c1['core'] == core and c1['rtl_sha256']
        assert c1['source']['core_rev_full']
        assert c1['elf_sha256'] == hashlib.sha256(Path(j['elf']).read_bytes()).hexdigest()

        trace = out / 'rvfi.jsonl'
        elf = Elf(j['elf'])
        bit = {'external': 11, 'timer': 7, 'software': 3, 'delegated': 9}[out.name.split('-')[0]]
        schedule = [(int(c), int(v, 16)) for c, v in (s.split(':') for s in j['irq_schedule'].split(','))]
        kwargs = {} if masked else dict(cause=(1 << (xlen-1)) | bit, window=(1001, 19999),
            handler_pc=elf.symbols['irq_handler'], mode=1 if bit == 9 else 3,
            epc_range=(elf.symbols['irq_wait'], elf.symbols['irq_wait_end']))
        bounds = check_interrupts(trace, schedule, **kwargs)
        (out / 'interrupt-check.json').write_text(json.dumps(bounds))
        assert bounds['status'] == 'consistent', bounds
        if not masked:
            rows = [json.loads(line) for line in trace.read_text().splitlines()]
            assert any('order' in r and r['cycle'] >= 1000 and
                       int(r['pc'], 16) < elf.symbols['irq_wait'] - 4 for r in rows)

        result = subprocess.run([str(ROOT / 'rvw/.venv/bin/rvw'), 'cosim', 'check', *platform_args,
            '--elf', j['elf'], '--trace', str(trace), '--json'], capture_output=True, text=True)
        (out / 'cosim.json').write_text(result.stdout)
        assert result.returncode == 0, json.loads(result.stdout).get('mismatch', result.stdout[:500])
        if not masked:
            assert check_interrupts(trace, schedule, **(kwargs | {'window': (1, 999)}))['status'] == 'mismatch'
            assert check_interrupts(trace, schedule, **(kwargs | {'cause': (1 << (xlen-1)) | (3 if bit != 3 else 7)}))['status'] == 'mismatch'

            # Mutate the recorded event, then require Spike comparison to reject it.
            rows = [json.loads(line) for line in trace.read_text().splitlines()]
            event = next(r for r in rows if r.get('event') == 'trap')
            event['cause'] = hex((1 << (xlen-1)) | (3 if bit != 3 else 7))
            bad = out / 'wrong-event.jsonl'
            bad.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            negative = subprocess.run([str(ROOT / 'rvw/.venv/bin/rvw'), 'cosim', 'check', *platform_args,
                '--elf', j['elf'], '--trace', str(bad), '--json'], capture_output=True, text=True)
            (out / 'wrong-event-cosim.json').write_text(negative.stdout)
            assert negative.returncode == 1, negative.stdout[:1000] + negative.stderr
