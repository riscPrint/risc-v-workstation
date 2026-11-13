"""Bounded external clients over an allowlisted MCP transport.

The evaluator stays in this process. The child receives only a URL and a token.
Clients must disable other tools. This runner is not an OS security sandbox.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import secrets
import socket
import sys
import threading
import time
from pathlib import Path

from rvw.common.proc import run_group
from rvw.mcp.remote import Remote
from rvw.mcp.spec import ToolError
from .engine import Session, load_pack, report


def run_trial(pack, task, command, out, *, budget_s=60, max_calls=32, model=None, repeats=1):
    if budget_s <= 0 or max_calls < 1 or repeats < 1:
        raise ValueError('budget, max calls and repeats must be positive')
    tasks, digest = load_pack(Path(pack))
    selected = next((t for t in tasks if t['id'] == task), None)
    if selected is None:
        raise ValueError('unknown task ID')
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    scores, attempts = [], []
    for repetition in range(repeats):
        run_dir = out / f'trial-{repetition + 1}'
        run_dir.mkdir()
        session = Session(selected, max_calls=max_calls)
        registry = session.registry()
        original_call = registry.call
        request_log = []
        rejected_calls = []
        serial = threading.Lock()
        def bounded_call(name, arguments):
            with serial:
                if len(request_log) >= max_calls:
                    rejected_calls.append(name)
                    raise ToolError('tool budget exhausted')
                request_log.append({'tool': name, 'arguments': arguments})
                return original_call(name, arguments)
        registry.call = bounded_call
        token = secrets.token_hex(32)
        ready = threading.Event()
        import uvicorn

        class Server(uvicorn.Server):
            async def startup(self, sockets=None):
                await super().startup(sockets=sockets)
                ready.set()

        app = Remote({token: {'tools': list(registry.tools)}}, registry_factory=lambda policy: registry)
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen()
        port = listener.getsockname()[1]
        server = Server(uvicorn.Config(app, log_level='error', lifespan='on'))
        thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
        thread.start()
        try:
            if not ready.wait(10) or not server.started:
                raise RuntimeError('benchmark MCP server did not start')
            env = {k: v for k, v in os.environ.items() if not k.startswith('RVW_BENCH_')}
            env.update(RVW_BENCH_MCP_URL=f'http://127.0.0.1:{port}/sse', RVW_BENCH_MCP_TOKEN=token)
            started = time.monotonic()
            try:
                result = run_group(command, cwd=run_dir, env=env, timeout=budget_s, capture=True)
                exit_code, timeout = result.returncode, result.timed_out
                output, errors = result.stdout or '', result.stderr or ''
            except OSError as exc:
                exit_code, timeout, output, errors = None, False, '', str(exc)
            wall = time.monotonic() - started
        finally:
            server.should_exit = True
            thread.join(10)
            if thread.is_alive():
                server.force_exit = True
                thread.join(2)
            listener.close()
            registry.jobs.shutdown()
        (run_dir / 'client.log').write_text(output + '\n--- stderr ---\n' + errors)
        score = session.score()
        scores.append(score)
        attempts.append({'repeat': repetition + 1, 'exit_code': exit_code, 'timed_out': timeout,
                         'wall_s': wall, 'calls': len(request_log), 'budget_rejections': len(rejected_calls),
                         'requests': request_log, 'complete': score['complete']})
        body = report(scores, digest, model or 'external')
        body.update(schema='rvw.agent-external-trial/1',
                    task_sha256=hashlib.sha256(json.dumps(selected, sort_keys=True).encode()).hexdigest(), client={'command': command, 'model': model},
                    machine={'system': platform.system(), 'machine': platform.machine(), 'cpus': os.cpu_count(),
                             'python': platform.python_version()}, budget_s=budget_s, max_calls=max_calls,
                    repeats_requested=repeats, attempts=attempts,
                    tool_surface='fixture MCP only; external client must disable other tools')
        (out / 'results.json').write_text(json.dumps(body, indent=2) + '\n')
    return body
