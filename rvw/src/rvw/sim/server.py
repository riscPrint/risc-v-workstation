"""Local socket access to one serial native JSONL simulation process."""
import json
import os
from pathlib import Path
import selectors
import socket
import subprocess
import time

from rvw.common.proc import kill_group


def request(endpoint, job, timeout=600):
    """Submit one job. The service owns native process teardown on timeout."""
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(timeout)
        client.connect(str(endpoint))
        client.sendall(json.dumps(job).encode() + b'\n')
        with client.makefile('rb') as stream:
            line = stream.readline()
    if not line:
        raise ValueError('simulation service closed without a reply')
    reply = json.loads(line)
    if 'error' in reply:
        raise ValueError(reply['error'])
    return reply


def serve(endpoint, command, timeout=600, *, ready=None):
    """Own one adapter `serve` process. Jobs run serially in the same JVM."""
    path = Path(endpoint)
    if path.exists():
        raise ValueError('simulation socket already exists')
    if not isinstance(command, list) or not command or not all(isinstance(v, str) for v in command):
        raise ValueError('server command must be a nonempty argument array')
    path.parent.mkdir(parents=True, exist_ok=True)
    with socket.socket(socket.AF_UNIX) as listener, path.with_suffix('.log').open('x') as log:
        listener.bind(str(path))
        listener.listen(4)
        process = None
        try:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=log, start_new_session=True, bufsize=0)
            if ready is not None:
                ready.set()
            while True:
                with listener.accept()[0] as client:
                    with client.makefile('rwb', buffering=0) as stream:
                        line = stream.readline()
                        job = json.loads(line)
                        process.stdin.write(json.dumps(job).encode() + b'\n')
                        process.stdin.flush()
                        with selectors.DefaultSelector() as selector:
                            selector.register(process.stdout, selectors.EVENT_READ)
                            if not selector.select(timeout):
                                stream.write(b'{"error":"native simulation request timed out; server stopped"}\n')
                                return 2
                        reply = process.stdout.readline()
                        if not reply:
                            stream.write(b'{"error":"native simulation process exited; server stopped"}\n')
                            return 2
                        stream.write(reply)
                        if job.get('op') == 'shutdown':
                            return 0
        finally:
            if process is not None:
                kill_group(process)
            path.unlink(missing_ok=True)


def identity_error(original, rerun):
    """Live reproduction needs the same native session and generated RTL."""
    expected = (original.get('details') or {}).get('simulation_session', {}).get('id')
    actual = (rerun.get('details') or {}).get('simulation_session', {}).get('id')
    if not expected or actual != expected:
        return 'wave request did not use the original live simulation session'
    if not original.get('rtl_sha256') or rerun.get('rtl_sha256') != original.get('rtl_sha256'):
        return 'live wave request used a different RTL identity'
    return None


def execute(endpoint, cmd, out, timeout=None):
    """Use the same fresh-directory and C1 checks as a process invocation."""
    from rvw.runs import adapter
    directory = adapter.fresh_dir(out)
    command = cmd.set(out=str(directory))
    started = time.time()
    before = time.monotonic()
    log = directory / 'rerun.log'
    try:
        if command.env.get("RVW_ADAPTER_RESOLUTION_ERROR"):
            raise ValueError("unsupported revision: " + command.env["RVW_ADAPTER_RESOLUTION_ERROR"])
        reply = request(endpoint, adapter._manifest_entry(command), timeout=timeout or 600)
        log.write_text(json.dumps(reply) + '\n')
        if command.inputs is not None:
            command.inputs.verify()
        run, error = adapter._collect(directory, started, command)
        return adapter.Attempt(run, directory, time.monotonic()-before,
                               0 if run else 2, log=log, error=error)
    except (OSError, ValueError) as error:
        log.write_text(str(error) + '\n')
        return adapter.Attempt(None, directory, time.monotonic()-before, 2, log=log, error=str(error))
