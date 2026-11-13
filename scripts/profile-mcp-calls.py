#!/usr/bin/env python3
"""Measure warm MCP envelopes, job wrappers and cold provider resolution.

rvw/.venv/bin/python scripts/profile-mcp-calls.py > "$RUN_ROOT/calls.jsonl"
Add --control for the original empty-argument and signature work. Worker cases
always compare catalog discovery with a known provider on the same revision.
No native tools run. The VCD is a small hand-written parser fixture.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def record(start, **fields):
    print(json.dumps(dict(cpu_s=time.process_time() - start, load=os.getloadavg(), **fields)),
          flush=True)


def worker(case, wave):
    start = time.process_time()
    from rvw.mcp.execution import run_discovered
    result = run_discovered('wave_info', {'wave': wave, 'indexed': False},
                            provider=None if case == 'worker-before' else 'rvw.wave.mcp_tools')
    assert result['signals'] == 1
    record(start, case=case, imports=len(sys.modules))


def calls(control, repeats):
    from rvw.mcp.registry import Registry
    from rvw.mcp.spec import ToolSpec, schema
    if control:
        import inspect
        import rvw.mcp.registry as registry
        registry._check_json = lambda args: json.dumps(args, allow_nan=False)
        ToolSpec.wants_job = property(lambda self: 'job' in inspect.signature(self.handler).parameters)
    for case, count in (('envelope', 10000), ('job', 3000)):
        for repeat in range(repeats):
            handler = (lambda job: {'value': 1}) if case == 'job' else (lambda: {'value': 1})
            registry = Registry([ToolSpec('tiny', 'tiny', schema({}), handler, long=case == 'job')])
            def call():
                if case == 'job':
                    result = registry.call('tiny', {})
                    registry.jobs.get(result['job_id']).done.wait()
                else:
                    registry.call_json('tiny', {})
            try:
                call()  # Load the schema, dependencies and worker thread before timing.
                start = time.process_time()
                for _ in range(count):
                    call()
                record(start, case=case, calls=count, control=control)
            finally:
                registry.jobs.shutdown()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--control', action='store_true')
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--child', choices=('worker-before', 'worker-after'))
    parser.add_argument('--wave')
    args = parser.parse_args()
    if args.child:
        worker(args.child, args.wave)
        return
    calls(args.control, args.repeats)
    with tempfile.TemporaryDirectory(prefix='toolperf-calls-') as directory:
        wave = Path(directory) / 'tiny.vcd'
        wave.write_text('$timescale 1ns $end\n$scope module top $end\n'
                        '$var wire 1 ! clock $end\n$upscope $end\n$enddefinitions $end\n'
                        '#0\n0!\n#5\n1!\n')
        for repeat in range(args.repeats):
            for case in ('worker-before', 'worker-after'):
                subprocess.run([sys.executable, __file__, '--child', case, '--wave', str(wave)],
                               check=True)


if __name__ == '__main__':
    main()
