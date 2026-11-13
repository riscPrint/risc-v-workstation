"""Measure serial boot slices after exact final checkpoint state equality."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import zipfile
from rvw.common.proc import run_group
from rvw.common.lock import held


def digest(checkpoint):
    h = hashlib.sha256()
    with zipfile.ZipFile(checkpoint) as archive:
        for name in ('state.json', 'ram.bin'):
            with archive.open(name) as stream:
                while chunk := stream.read(1024 * 1024):
                    h.update(chunk)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('--inputs', type=Path, required=True)
    p.add_argument('--checkpoint', type=Path, required=True)
    p.add_argument('--classpath', type=Path, required=True, help='frozen runtime classpath.txt')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--cycles', type=int, default=65536)
    p.add_argument('--pairs', type=int, default=5)
    a = p.parse_args()
    if a.cycles < 1024 or a.pairs < 5:
        p.error('use at least 1024 cycles and five pairs')
    with zipfile.ZipFile(a.checkpoint) as archive:
        state = json.loads(archive.read('state.json'))['state']
    stop = int(state['cycle']) + a.cycles
    # Keep lock waiting outside each trial's execution timeout.
    with held('vex-linux'):
        a.out.mkdir(parents=True, exist_ok=False)
        variants = [('O0-t1', 0, 1), ('O3-t1', 3, 1), ('O3-t2', 3, 2)]
        samples = {name: [] for name, _, _ in variants}
        expected = None
        here = Path(__file__).resolve().parent.parent
        for pair in range(-1, a.pairs):
            order = variants if pair % 2 == 0 else list(reversed(variants))
            for name, opt, threads in order:
                label = f'{"warm" if pair < 0 else f"pair-{pair}"}-{name}'
                checkpoint = a.out / f'{label}.zip'
                shutil.copyfile(a.checkpoint, checkpoint)
                out = a.out / label
                env = dict(os.environ, RVW_BOOT_CLASSPATH=str(a.classpath.resolve()),
                           RVW_BOOT_OPT=str(opt), RVW_BOOT_THREADS=str(threads),
                           RVW_BOOT_WORK=str((a.out / f'native-{name}').resolve()))
                env.pop('RVW_BOOT_SECONDS', None)
                env.pop('RVW_BOOT_FREEZE_RUNTIME', None)
                env.pop('SPINAL_VERILATOR_FLAGS', None)
                command = [str(here / 'boot-slices.sh'), str(a.inputs / 'reset.elf'),
                           str(a.inputs / 'payloads.json'), str(a.inputs / 'devices.json'),
                           str(out), str(checkpoint), 'restore', str(stop)]
                run = run_group(command, env=env, capture=True, timeout=600)
                (a.out / f'{label}.log').write_text(run.stdout + run.stderr)
                if run.returncode:
                    raise RuntimeError(f'{label} failed; see its log')
                result = json.loads((out / 'result.json').read_text())
                if int(result['slice_cycles']) != a.cycles:
                    raise ValueError(f'{label} did not execute the complete slice')
                actual = digest(checkpoint)
                if expected is None:
                    expected = actual
                if actual != expected:
                    raise ValueError(f'{label}: complete checkpoint state differs')
                checkpoint.unlink()
                if pair >= 0:
                    samples[name].append(result)
                print(f'{label}: {result["instructions_per_second"]:.2f} instructions/s; state equal', flush=True)
        print('\n| Profile | Median cycles/s | Median instructions/s | Paired wall speedup |')
        print('|---|---:|---:|---:|')
        base = samples['O0-t1']
        for name, _, _ in variants:
            rows = samples[name]
            ratio = math.exp(statistics.mean(math.log(b['wall_seconds']/r['wall_seconds']) for b, r in zip(base, rows)))
            print(f'| {name} | {statistics.median(r["cycles_per_second"] for r in rows):.2f} | '
                  f'{statistics.median(r["instructions_per_second"] for r in rows):.2f} | {ratio:.4f}x |')
        print(f'\nPairs: {a.pairs}. Complete final checkpoint SHA-256: {expected}.')
        print('Rates include RTL restore and checkpoint writes. C2 was not captured. These are bounded-slice measurements.')
        for name, _, _ in variants:
            shutil.rmtree(a.out / f'native-{name}', ignore_errors=True)


if __name__ == '__main__':
    main()
