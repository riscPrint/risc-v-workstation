"""Expose a stopped boot slice to C1 debug tools without claiming C1 replay support."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
from rvw.results import RunResult, save_run


def convert(report: Path, checkpoint: Path, elf: Path, out: Path, *, wave=None, trace=None):
    sample = json.loads(report.read_text())
    if sample.get('schema') != 'rvw.vexii-boot-slice-result/1':
        raise ValueError('expected a boot-slice result')
    with zipfile.ZipFile(checkpoint) as archive:
        state = json.loads(archive.read('state.json'))['state']
    if state['schema'] != 'rvw.vexii-boot-slice/1':
        raise ValueError('expected a boot-slice checkpoint')
    for name in ('cycle', 'retired', 'pc', 'trap', 'mode', 'retired_by_mode', 'irq_levels'):
        if name in sample and sample[name] != state[name]:
            raise ValueError(f'result and checkpoint differ: {name}')
    elf = elf.resolve()
    digest = hashlib.sha256(elf.read_bytes()).hexdigest()
    if digest != state['identity']['inputs'][0]:
        raise ValueError('ELF differs from the captured boot input')
    out.mkdir(parents=True, exist_ok=False)
    (out / 'console.log').write_text(''.join(sample['console'].values()))
    artifacts = {'log': 'console.log', 'native_slice': str(report.resolve()),
                 'checkpoint': str(checkpoint.resolve())}
    if wave:
        artifacts['wave'] = str(Path(wave).resolve(strict=True))
    if trace:
        artifacts['rvfi_trace'] = str(Path(trace).resolve(strict=True))
    marker = 'RVW_LINUX_USERSPACE\n'
    userspace = any(marker in text.replace('\r\n', '\n') for text in sample['console'].values())
    complete = sample['status'] == 'shutdown' and userspace
    result = RunResult(status='pass' if complete else 'timeout', core='vexiiriscv',
        config='rv64imacsu_linux', elf=str(elf), elf_sha256=digest, seed=1, mem_latency=1,
        cycles=int(sample['cycle']), instret=int(sample['retired']), wall_s=sample['wall_seconds'],
        message='userspace marker and power-off observed' if complete else 'stopped boot slice; OS completion not established',
        artifacts=artifacts, extra={'rtl_sha256': state['identity']['rtl'],
            'inconclusive': 'diagnostic view of a project boot slice; C1 replay is not bound',
            'details': {'completion': sample['status'], 'userspace_marker': userspace,
                        'last_retired_pc': sample['pc'], 'last_trap': sample['trap'],
                        'device_output': sample['console'], 'checkpoint_identity': state['identity'],
                        'last_retired_mode': sample.get('mode'), 'retired_by_mode': sample.get('retired_by_mode'),
                        'irq_levels': sample.get('irq_levels')}})
    save_run(result, out / 'result.json')
    return result.to_dict()


if __name__ == '__main__':
    p = argparse.ArgumentParser(__doc__)
    for field in ('report', 'checkpoint', 'elf', 'out'):
        p.add_argument('--' + field, type=Path, required=True)
    p.add_argument('--wave', type=Path)
    p.add_argument('--trace', type=Path)
    args = p.parse_args()
    print(json.dumps(convert(args.report, args.checkpoint, args.elf, args.out,
                             wave=args.wave, trace=args.trace)))
