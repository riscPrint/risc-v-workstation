"""Project-owned process port for the fixed-latency VexRiscv bridge probe."""
import json
from pathlib import Path
import tempfile

from rvw.common.proc import run_group
from rvw.sim.checkpoint import STATE


class Port:
    def __init__(self, options):
        self.elf = Path(options['elf']).resolve(strict=True)
        self.launcher = Path(options['launcher']).resolve(strict=True)
        self.temporary = tempfile.TemporaryDirectory(prefix='rvw-vex-replay-')
        self.root = Path(self.temporary.name)
        self.raw = None
        self.count = 0
        self.calls = 0
        self.timeout = options.get('timeout', 600)

    def _run(self, mode, target, timeout):
        self.calls += 1
        snapshot = self.root / f'state-{self.calls}.json'
        if mode != 'save':
            snapshot.write_bytes(self.raw)
        result = run_group([str(self.launcher), str(self.elf), str(self.root / f'run-{self.calls}'),
            str(snapshot), mode, str(target)], timeout=timeout, capture=True, text=True)
        if result.timed_out:
            raise ValueError('VexRiscv replay exceeded the process wall budget')
        if result.returncode:
            raise ValueError('VexRiscv replay failed: ' + result.stdout[-3000:] + result.stderr[-1000:])
        self.raw = snapshot.read_bytes()
        self.count = int(json.loads(self.raw)['state']['retired'])

    def advance(self, unit, target):
        if unit != 'instructions':
            raise ValueError('VexRiscv probe supports instruction boundaries only')
        self._run('save', target, self.timeout)

    def position(self, unit):
        if unit != 'instructions':
            raise ValueError('VexRiscv probe supports instruction boundaries only')
        return self.count

    def quiescent(self): return self.raw is not None
    def external_effects(self): return []

    def save(self):
        saved = json.loads(self.raw)['state']
        state = {key: {} for key in STATE}
        state.update(scheduler={'cycle': int(saved['cycle'])}, clock={'phase': 'settled-low'},
            memory={'encoding': 'inside-native-payload'}, pending={'encoding': 'inside-native-payload'},
            rng={'kind': 'none'}, devices={'kind': 'none'}, interrupts={'levels': 0},
            monitors={'handler': saved['handler']}, rvfi={'encoding': 'inside-native-payload'},
            stimulus={'identity': saved['identity']}, counters={'instructions': self.count})
        return self.raw, state

    def validate_restore(self, native, state):
        saved = json.loads(native)['state']
        if saved['schema'] != 'rvw.vex-bridge-probe/1' or int(saved['retired']) != state['counters']['instructions']:
            raise ValueError('VexRiscv checkpoint counters or schema differ')
        if saved['identity'] != state['stimulus']['identity']:
            raise ValueError('VexRiscv checkpoint input identity differs')

    def restore(self, native, state):
        self.validate_restore(native, state)
        # The next process installs the saved RTL and harness state before any
        # instruction executes. The immutable payload is the stopped port state.
        self.raw = native
        self.count = state['counters']['instructions']

    def replay_to_instruction(self, target, *, max_seconds):
        if target < self.count:
            raise ValueError('replay target precedes restored boundary')
        if target != self.count:
            self._run('replay', target, max_seconds)

    def close(self): self.temporary.cleanup()


def create(options): return Port(options)
