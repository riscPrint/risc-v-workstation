#!/usr/bin/env python3
"""Replay misleading evidence cases from a real native C1/C2 capture."""
import argparse
import json
from pathlib import Path
import shutil
import time


def mcp_audit(run_dir, elf, expected_identity, **options):
    import anyio
    import os
    import sys
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    async def request():
        params = StdioServerParameters(command=sys.executable, args=["-m", "rvw", "mcp"], env=dict(os.environ))
        async with stdio_client(params) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                response = await session.call_tool("agent_bench_audit_run",
                    {"run_dir": str(run_dir), "elf": str(elf), "expected_identity": expected_identity, **options})
                if response.is_error:
                    raise RuntimeError(response.content[0].text)
                return json.loads(response.content[0].text)
    return anyio.run(request)
from rvw.agent_bench.audit import audit_run

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--run-dir', type=Path, required=True)
p.add_argument('--elf', type=Path, required=True)
p.add_argument('--wrong-elf', type=Path, required=True)
p.add_argument('--stale-rtl', required=True, help='Intended task RTL hash, different from this capture')
p.add_argument('--out', type=Path, required=True)
p.add_argument('--mcp', action='store_true', help='Use the normal audit MCP tool for every case')
a = p.parse_args()
a.out.mkdir(parents=True, exist_ok=False)
rows = []
for case in ('control', 'stale-rtl', 'wrong-elf', 'unsupported-fields', 'missing-coverage', 'missing-end'):
    out = a.out / case
    out.mkdir()
    for name in ('result.json', 'rvfi.jsonl'):
        shutil.copy2(a.run_dir / name, out / name)
    expected = {'rtl_sha256': json.loads((a.run_dir / 'result.json').read_text())['rtl_sha256']}
    options = {}
    if case == 'stale-rtl':
        if a.stale_rtl == expected['rtl_sha256']:
            raise ValueError('stale case needs a different intended RTL identity')
        expected['rtl_sha256'] = a.stale_rtl
    if case == 'unsupported-fields':
        lines = (out / 'rvfi.jsonl').read_text().splitlines()
        head = json.loads(lines[0])
        head['capabilities'] = [*head.get('capabilities', ['state']), 'unsupported']
        lines[0] = json.dumps(head)
        (out / 'rvfi.jsonl').write_text('\n'.join(lines) + '\n')
    if case == 'missing-end':
        lines = (out / 'rvfi.jsonl').read_text().splitlines()
        if json.loads(lines[-1]).get('event') != 'end':
            raise ValueError('input must have a complete native run end')
        (out / 'rvfi.jsonl').write_text('\n'.join(lines[:-1]) + '\n')
    if case == 'missing-coverage':
        options['required_artifacts'] = ['coverage.dat']
    started = time.monotonic()
    result = (mcp_audit if a.mcp else audit_run)(out, a.wrong_elf if case == 'wrong-elf' else a.elf,
                       expected_identity=expected, **options)
    rows.append({'case': case, 'wall_s': time.monotonic() - started, 'mcp_calls': 1 if a.mcp else 0, **result})
    print(case, result['status'])
(a.out / 'audit.json').write_text(json.dumps(rows, indent=2) + '\n')
