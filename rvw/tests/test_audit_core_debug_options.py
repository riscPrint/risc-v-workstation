"""A debug adapter must report the run options that the trial requested."""
import sys

import pytest

from rvw.runs.adapter import Command, execute, execute_many


@pytest.mark.parametrize('name,wanted,actual', [
    ('seed', 2, 1), ('config', 'large', 'small'),
    ('max_cycles', 200, 100), ('mem_latency', 20, 1),
])
@pytest.mark.parametrize('batched', [False, True])
def test_debug_attempt_refuses_result_for_other_options(tmp_path, monkeypatch, batched, name, wanted, actual):
    monkeypatch.setenv('RVW_NO_LOCK', '1')
    monkeypatch.delenv('RVW_NO_RUN_MANY', raising=False)
    script = tmp_path / 'wrong_seed.py'
    script.write_text('''import json, sys
from pathlib import Path
args = sys.argv
if args[1] == 'run-many':
    jobs = [json.loads(line) for line in Path(args[args.index('--manifest') + 1]).read_text().splitlines()]
else:
    jobs = [{'out': args[args.index('--out') + 1]}]
for job in jobs:
    Path(job['out'], 'result.json').write_text(json.dumps({
        'schema': 'rvw.run/1', 'status': 'assert', 'seed': 1,
        'message': 'Core.scala:42 assertion', 'cycles': 10}))
'''.replace("'seed': 1", repr(name) + ': ' + repr(actual)))
    cmd = Command(exe=[sys.executable, str(script)], opts={'--' + name.replace('_', '-'): str(wanted)})
    attempts = execute_many([cmd, cmd], [tmp_path / 'a', tmp_path / 'b']) if batched else [execute(cmd, tmp_path / 'a')]
    for attempt in attempts:
        assert attempt.run is not None
        assert attempt.run.inconclusive
        assert name in attempt.run.inconclusive
        from rvw.reduce.core import Reducer
        reducer = object.__new__(Reducer)
        reducer.sig = 'assert:Core.scala:42'
        assert reducer.matches(attempt.run)[0] is None


@pytest.mark.parametrize('batched', [False, True])
@pytest.mark.parametrize('identity', ['other', 'missing', 'match', 'uppercase'])
def test_debug_attempt_checks_requested_elf(tmp_path, monkeypatch, batched, identity):
    monkeypatch.setenv('RVW_NO_LOCK', '1')
    monkeypatch.delenv('RVW_NO_RUN_MANY', raising=False)
    elf = tmp_path / 'wanted.elf'
    elf.write_bytes(b'wanted program')
    script = tmp_path / 'other_elf.py'
    script.write_text('''import json, sys, hashlib
from pathlib import Path
args = sys.argv
jobs = ([json.loads(line) for line in Path(args[args.index('--manifest') + 1]).read_text().splitlines()]
        if args[1] == 'run-many' else [{'out': args[args.index('--out') + 1]}])
for job in jobs:
    Path(job['out'], 'result.json').write_text(json.dumps({
        'schema': 'rvw.run/1', 'status': 'assert', 'cycles': 10,
        'elf_sha256': hashlib.sha256(b'other program').hexdigest(),
        'message': 'Core.scala:42 assertion'}))
''')
    import hashlib
    reported = hashlib.sha256(b'other program' if identity == 'other' else elf.read_bytes()).hexdigest()
    reported = None if identity == 'missing' else reported.upper() if identity == 'uppercase' else reported
    script.write_text(script.read_text().replace("hashlib.sha256(b'other program').hexdigest()", repr(reported)))
    cmd = Command(exe=[sys.executable, str(script)], opts={'--elf': str(elf)})
    attempts = execute_many([cmd, cmd], [tmp_path / 'a', tmp_path / 'b']) if batched else [execute(cmd, tmp_path / 'a')]
    for attempt in attempts:
        assert attempt.run is not None
        if identity in ('match', 'uppercase'):
            assert not attempt.run.inconclusive
        else:
            assert attempt.run.inconclusive
            assert 'ELF' in attempt.run.inconclusive
