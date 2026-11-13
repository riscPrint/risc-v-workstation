#!/usr/bin/env python3
"""Repeat cold-process CPU/import measurements. Redirect JSONL outside the checkout.

Run with rvw/.venv/bin/python scripts/profile-startup.py. Import profiles:
python -X importtime -m rvw mcp --list. CPU profile:
python scripts/profile-startup.py --cpu-profile "$RUN_ROOT/startup.prof" mcp --list.
"""
import contextlib
import io
import json
import os
import subprocess
import sys
import time


def metric(start, **fields):
    return dict(cpu_s=time.process_time() - start, imports=len(sys.modules),
                load=os.getloadavg(), **fields)


def child(args):
    start = time.process_time()
    from rvw.cli import main
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            code = main(args)
        except SystemExit as exc:
            code = exc.code
    print(json.dumps(metric(start, args=args, exit_code=code)))


def server_child(profile):
    start = time.process_time()
    from contextlib import asynccontextmanager
    import anyio
    import mcp.server.stdio as stdio
    original = stdio.stdio_server

    class Metered:
        def __init__(self):
            self.stream = anyio.wrap_file(sys.stdout)
            self.list_sent = False

        async def write(self, data):
            await self.stream.write(data)
            self.list_sent = json.loads(data).get('id') == 2

        async def flush(self):
            await self.stream.flush()
            if self.list_sent:
                print('METRIC ' + json.dumps(metric(start)), file=sys.stderr, flush=True)
                self.list_sent = False

    @asynccontextmanager
    async def measured_stdio(*args, **kwargs):
        async with original(*args, stdout=Metered(), **kwargs) as streams:
            yield streams

    stdio.stdio_server = measured_stdio
    from rvw.cli import main
    main(['mcp', '--profile', profile])


def server_measure(profile):
    process = subprocess.Popen([sys.executable, __file__, '--server-child', profile],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True)
    def send(message):
        process.stdin.write(json.dumps({'jsonrpc': '2.0', **message}) + '\n')
        process.stdin.flush()

    def receive(identifier):
        while line := process.stdout.readline():
            value = json.loads(line)
            if value.get('id') == identifier:
                if 'error' in value:
                    raise RuntimeError(value['error'])
                return value
        raise RuntimeError('MCP server closed before response')

    captured = []
    try:
        send(dict(id=1, method='initialize', params=dict(protocolVersion='2025-03-26',
                  capabilities={}, clientInfo=dict(name='profile-startup', version='1'))))
        receive(1)
        send(dict(method='notifications/initialized'))
        send(dict(id=2, method='tools/list', params={}))
        result = receive(2)
        # The response can reach the parent before the child resumes after flush.
        while line := process.stderr.readline():
            captured.append(line)
            if line.startswith('METRIC '):
                break
    finally:
        process.terminate()
        _, stderr = process.communicate(timeout=20)
    stderr = ''.join(captured) + stderr
    metrics = [json.loads(line.removeprefix('METRIC ')) for line in stderr.splitlines()
               if line.startswith('METRIC ')]
    if not metrics:
        raise RuntimeError(stderr)
    return dict(metrics[0], profile=profile, tools=len(result['result']['tools']))


if __name__ == '__main__':
    if sys.argv[1:2] == ['--child']:
        child(sys.argv[2:])
    elif sys.argv[1:2] == ['--server-child']:
        server_child(sys.argv[2])
    elif sys.argv[1:2] == ['--cpu-profile']:
        import cProfile
        profiler = cProfile.Profile(timer=time.process_time)
        try:
            profiler.runcall(child, sys.argv[3:] or ['mcp', '--list'])
        finally:
            profiler.dump_stats(sys.argv[2])
    else:
        for repeat in range(3):
            for args in (['--help'], ['query', '--help'], ['probes', '--help'],
                         ['mcp', '--list'], ['mcp', '--list', '--profile', 'core']):
                print(subprocess.check_output([sys.executable, __file__, '--child', *args],
                                              text=True).strip(), flush=True)
            for profile in ('core', 'all'):
                print(json.dumps(server_measure(profile)), flush=True)
