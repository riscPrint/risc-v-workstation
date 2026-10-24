"""Output ownership must outlive a killed regression runner."""
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent


# ------------------------------------------------------------------------------ output ownership

def _wait_file(path, proc, timeout=15):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if path.exists() and path.read_text().strip():
            return path.read_text().strip()
        assert proc.poll() is None, "runner exited before adapter started"
        time.sleep(0.05)
    pytest.fail(f"adapter did not create {path}")


@pytest.mark.parametrize("close_fds,spawn_window", [(False, False), (True, False), (True, True)])
def test_killed_runner_keeps_output_owned(fake, tmp_path, rvw, close_fds, spawn_window):
    """A stale adapter must not publish over the next run, even when it closes inherited fds or
    the runner dies between Popen and process-group registration. Exercise --fresh too."""
    adapter = tmp_path / "writer.py"
    pidfile, release = tmp_path / "writer.pid", tmp_path / "release"
    adapter.write_text(f"""import json, os, pathlib, sys, time
if {close_fds!r}:
    os.closerange(3, 4096)
pid = pathlib.Path({str(pidfile)!r})
pid.write_text(str(os.getpid()))
end = time.monotonic() + 30
while not pathlib.Path({str(release)!r}).exists():
    if time.monotonic() > end: sys.exit(1)
    time.sleep(.05)
manifest = pathlib.Path(sys.argv[sys.argv.index('--manifest') + 1])
for line in manifest.read_text().splitlines():
    job = json.loads(line)
    out = pathlib.Path(job['out'])
    out.mkdir(parents=True, exist_ok=True)
    (out / 'result.json').write_text(json.dumps({{'schema':'rvw.run/1', 'status':'pass', 'seed':job['seed']}}))
""")
    fake.config.write_text(fake.config.read_text().replace(str(HERE / "fake_adapter.py"), str(adapter))
                           .replace('lock = "fake-test"', 'build_first = false'))
    out = tmp_path / "shared-out"
    cmd = [sys.executable, "-m", "rvw", "regress", "run", "--core", str(fake.config),
           "--suite", "isa", "--out", str(out), "--no-cache", "--no-index", "--json"]
    if spawn_window:
        # Stop in Popen's return window. No registration after Popen can have run yet.
        launch = tmp_path / "launch.py"
        launch.write_text("""import subprocess, sys, time
from rvw.cli import main
real = subprocess.Popen
def boundary(*args, **kwargs):
    p = real(*args, **kwargs)
    if any(str(x).endswith('writer.py') for x in args[0]):
        time.sleep(30)
    return p
subprocess.Popen = boundary
raise SystemExit(main(sys.argv[1:]))
""")
        cmd = [sys.executable, str(launch), *cmd[3:]]
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    apid = None
    try:
        apid = int(_wait_file(pidfile, p))
        # Let registration finish in the normal case; the explicit window stays blocked.
        if not spawn_window:
            time.sleep(.2)
        p.kill()
        p.wait(timeout=5)
        for fresh in ([], ["--fresh"]):
            code, text, _ = rvw("regress", "run", "--core", fake.config, "--suite", "isa",
                               "--out", out, "--no-cache", "--no-index", *fresh, "--json")
            assert code == 2 and "in use" in text + rvw.stderr
        release.touch()
    finally:
        if p.poll() is None:
            p.kill()
        p.wait(timeout=5)
        if apid:
            try:
                os.killpg(apid, signal.SIGKILL)
            except ProcessLookupError:
                pass


