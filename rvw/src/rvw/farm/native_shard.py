"""Queue-owned persistent adapter shard. Each attempt has fresh C1 directories."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import signal
from pathlib import Path
import time

from rvw.common.proc import run_group
from rvw.results import load_run, SuiteResults, TestEntry, write_json
from rvw.results.signature import run_signature


def execute(manifest, adapter, out, suite='isa', timeout=600):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(line) for line in Path(manifest).read_text().splitlines() if line.strip()]
    if not rows:
        raise ValueError('empty shard')
    captured = []
    for index, row in enumerate(rows):
        elf = Path(row['elf']).resolve(strict=True)
        captured.append(dict({k: v for k, v in row.items() if k != 'id'},
                             elf=str(elf), out=str(out / 'cells' / str(index))))
    local = out / 'manifest.jsonl'
    local.write_text(''.join(json.dumps(r) + '\n' for r in captured))
    start = time.monotonic()
    with (out / 'adapter.log').open('w') as log:
        process = run_group([*adapter, 'run-many', '--persistent', '--jobs', '1', '--manifest', str(local), '--json'],
                            timeout=timeout, stdout=log, stderr=log, grace=20)
    tests, errors, source, core, config = [], [], None, None, None
    for original, row in zip(rows, captured):
        try:
            run = load_run(row['out'])
            expected = dict(elf_sha256=hashlib.sha256(Path(row['elf']).read_bytes()).hexdigest(),
                            **{k: row[k] for k in ('config', 'seed', 'max_cycles', 'mem_latency') if k in row})
            if any(run.get(k) != v for k, v in expected.items()):
                raise ValueError('C1 input identity differs')
            if run.extra.get('execution_mode') != 'server':
                raise ValueError('adapter did not use persistent server')
            if source is not None and (run.source != source or run.core != core or run.config != config):
                raise ValueError('mixed source, core or configuration in shard')
            source, core, config = run.source, run.core, run.config
            extra = dict(run.extra)
            extra.update(elf_sha256=run.elf_sha256, tools=run.tools,
                         options={**run.extra.get('options', {}),
                                  **{k: v for k, v in row.items() if k not in ('id', 'elf', 'out')},
                                  'max_cycles': run.max_cycles, 'mem_latency': run.mem_latency},
                         kind='elf')
            if run.message:
                extra.update(message=run.message, message_complete=True)
            if run.fail_code is not None:
                extra['fail_code'] = run.fail_code
            if run.why_inconclusive:
                extra['inconclusive'] = run.why_inconclusive
            tests.append(TestEntry(id=original.get('id', Path(original['elf']).name), status=run.status,
                seed=run.seed, cycles=run.cycles, instret=run.instret, wall_s=run.wall_s,
                run=str(Path(row['out']).relative_to(out)), signature=run_signature(run), extra=extra))
        except (OSError, ValueError) as error:
            errors.append(dict(test=original.get('id', Path(original['elf']).name), error=str(error)))
    if tests:
        results = SuiteResults(out.name, suite, core, config, datetime.now(timezone.utc).isoformat(),
                               source=source, tests=tests)
        write_json(out / 'results.json', results.to_dict())
    wall = time.monotonic() - start
    expected_exit = process.returncode == 0 or (process.returncode == 1 and any(t.failed for t in tests))
    complete = not errors and not process.timed_out and expected_exit and all(t.conclusive for t in tests)
    report = dict(schema='rvw.native-shard/1', status='complete' if complete else 'inconclusive',
                  expected=len(rows), collected=len(tests), errors=errors, wall_seconds=wall,
                  tests_per_second=len(tests)/wall, adapter_returncode=process.returncode)
    write_json(out / 'collection.json', report)
    return report


def main():
    def stop(signum, frame):
        raise SystemExit(128 + signum)
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, stop)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--adapter', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--suite', default='isa')
    parser.add_argument('--timeout', type=float, default=600)
    args = parser.parse_args()
    report = execute(args.manifest, json.loads(args.adapter), args.out, args.suite, args.timeout)
    print(json.dumps(report))
    return 0 if report['status'] == 'complete' else 3


if __name__ == '__main__':
    raise SystemExit(main())
