"""Launcher cancellation and native build identity."""
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from rvw.common.proc import kill_group, run_group
from race_injection import race_injector

SCRIPT = Path(__file__).resolve().parents[2] / "RiscvSim" / "scripts" / "native-identity.py"


# ------------------------------------------------------------------ review 14: publication race

RUN_SH = SCRIPT.parents[1] / "boom" / "run.sh"
FAKE_JAVA = r'''#!/usr/bin/env python3
import json, os, sys, time
from pathlib import Path
if "--version" in sys.argv:
    print("fixture java 21")
    sys.exit(0)
go = os.environ.get("FAKE_JAVA_GO")
if go:
    Path(os.environ["FAKE_JAVA_STARTED"]).write_text(str(os.getpid()))
    while not Path(go).exists():
        time.sleep(0.02)
record = json.loads(next(a.split("=", 1)[1] for a in sys.argv if a.startswith("-Driscvsim.native.identity=")))
print("native-build " + json.dumps(record, sort_keys=True))
'''
FAKE_SBT = r'''#!/usr/bin/env bash
set -euo pipefail
# Export-only discovery does not compile.
case " $* " in *" boom/compile "*) ;; *)
  if [ -n "${CUSTOM_BASE:-}" ]; then echo "$CUSTOM_BASE"; fi
  exit 0 ;;
esac
original_classes="$FAKE_CLASSES"
FAKE_CLASSES="$PWD/target/classes"
mkdir -p "$FAKE_CLASSES"
cp -R "$original_classes/." "$FAKE_CLASSES/"
FAKE_SCALA_JAR="${FAKE_SCALA_JAR//$LIVE_SIM/$PWD}"
if [ -n "${FAKE_SBT_LOG:-}" ]; then echo compile >> "$FAKE_SBT_LOG"; fi
if [ -f "$SPINAL_BOOM/src/A.scala" ]; then cp "$SPINAL_BOOM/src/A.scala" "$FAKE_CLASSES/A.class"; fi
if [ -n "${FAKE_SBT_STARTED:-}" ]; then
  touch "$FAKE_SBT_STARTED"
  while [ ! -f "$FAKE_SBT_GO" ]; do sleep 0.05; done
fi
echo "[info] compiling"
echo "$FAKE_SCALA_JAR:$FAKE_CLASSES"
'''


@pytest.fixture
def launcher(tmp_path):
    """Real launcher with fake sbt/JVM and the installed native tools."""
    sim = tmp_path / "RiscvSim"
    for rel in ("boom/run.sh", "scripts/make-jobs.sh", "scripts/native-identity.py", "scripts/source-identity.py", "scripts/supervise.py"):
        (sim / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SCRIPT.parents[1] / rel, sim / rel)
    # Exercise the real lock protocol in a private lock directory, without a BOOM build.
    repo = SCRIPT.parents[2]
    for rel in ("scripts/with-lock.sh", "rvw/src/rvw/common/lock.py", "rvw/src/rvw/common/proc.py", "rvw/src/rvw/common/budget.py", "rvw/src/rvw/common/capture.py", "rvw/src/rvw/regress/source.py"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo / rel, tmp_path / rel)
    bin_ = tmp_path / "bin"
    (tmp_path / "jdk" / "bin").mkdir(parents=True)
    bin_.mkdir()
    java = tmp_path / "jdk" / "bin" / "java"
    java.write_text(FAKE_JAVA.replace("#!/usr/bin/env python3", f"#!{sys.executable}", 1))
    (bin_ / "sbt").write_text(FAKE_SBT)
    for f in (java, bin_ / "sbt"):
        f.chmod(0o755)
    classes = tmp_path / "classes"
    classes.mkdir()
    (classes / "A.class").write_text("x")
    (tmp_path / "boom").mkdir()
    (sim / "lib").mkdir()
    scala_jar = sim / "lib/scala-library.jar"
    scala_jar.write_text("fixture scala library")
    cache = tmp_path / "cache"
    env = {**os.environ, "RVW_PYTHON": sys.executable, "RVW_LOCK_PYTHON": sys.executable,
           "PATH": f"{bin_}:{os.environ['PATH']}", "JAVA_HOME": str(tmp_path / "jdk"),
           "SPINAL_BOOM": str(tmp_path / "boom"), "RISCVSIM_CP_CACHE": str(cache), "RVW_NO_LOCK": "1",
           "LIVE_SIM": str(sim), "FAKE_CLASSES": str(classes), "FAKE_SCALA_JAR": str(scala_jar), "RVW_LOCK_DIR": str(tmp_path / "locks"), "RVW_LOCK_POLL_S": "0.05"}
    env.pop("FAKE_JAVA_GO", None)
    env.pop("RVW_LOCKS_HELD", None)

    def start(**extra):
        return subprocess.Popen(["bash", str(sim / "boom/run.sh"), "info"], env={**env, **extra}, cwd=tmp_path,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    start.cache = cache
    start.env, start.sim, start.bin = env, sim, bin_
    processes = []

    def tracked(**extra):
        p = start(**extra)
        processes.append(p)
        return p
    tracked.__dict__.update(start.__dict__)
    yield tracked
    for p in processes:
        kill_group(p, grace=0.2)


# ------------------------------------------------------------------ review 15: source identity

def wait_for_file(path, process):
    deadline = time.monotonic() + 15
    while not path.exists() or not path.read_text().strip():
        assert time.monotonic() < deadline and process.poll() is None, str(path)
        time.sleep(0.05)


def test_wait_for_pid_marker_waits_for_writer(tmp_path, monkeypatch):
    from types import SimpleNamespace
    marker = tmp_path / 'writer.pid'
    marker.touch()
    pauses = []
    def finish_write(seconds):
        pauses.append(seconds)
        marker.write_text('12345')
    monkeypatch.setattr(time, 'sleep', finish_write)
    wait_for_file(marker, SimpleNamespace(poll=lambda: None))
    assert pauses
    assert marker.read_text() == '12345'


def process_alive(pid):
    state = subprocess.run(['ps', '-o', 'stat=', '-p', str(pid)],
                           capture_output=True, text=True, check=False).stdout.strip()
    return bool(state) and not state.startswith('Z')


@pytest.mark.parametrize('sig', [signal.SIGTERM, signal.SIGINT, signal.SIGHUP])
@pytest.mark.parametrize('script', ['tests/programs/build.sh'])
def test_other_riscvsim_scripts_stop_children(launcher, tmp_path, sig, script):
    destination = launcher.sim / script
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SCRIPT.parents[1] / script, destination)
    if script.endswith('build.sh'):
        (destination.parent / 'fixture.S').write_text('')
    marker = tmp_path / 'child.pid'
    sleeper = launcher.bin / 'sbt'
    sleeper.write_text('#!/bin/bash\necho $$ > "$SLEEPER_PID"\nexec /bin/sleep 120\n')
    environment = {**launcher.env, 'RISCV_GCC': str(sleeper), 'SLEEPER_PID': str(marker),
                   'TMPDIR': str(tmp_path)}
    process = subprocess.Popen(['bash', str(destination)], env=environment,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, start_new_session=True)
    child = None
    try:
        wait_for_file(marker, process)
        child = int(marker.read_text())
        process.send_signal(sig)
        out, err = process.communicate(timeout=15)
        assert process.returncode == 128 + sig, (out, err)
        assert not process_alive(child), (out, err)
        assert not list(tmp_path.glob('riscvsim-launch.*'))
    finally:
        kill_group(process, grace=0.2)
        if child is not None and process_alive(child):
            os.kill(child, signal.SIGKILL)


@pytest.mark.parametrize('sig', [signal.SIGTERM, signal.SIGINT, signal.SIGHUP])
@pytest.mark.parametrize('stage', ['compile', 'native-probe', 'runtime'])
def test_launcher_cancel_stops_build_and_releases_ownership(launcher, tmp_path, sig, stage):
    from rvw.common.lock import status
    marker = tmp_path / 'sleeper.pid'
    extra = {'TMPDIR': str(tmp_path)}
    if stage in ('native-probe', 'classpath-probe'):
        tool = launcher.bin / 'verilator' if stage == 'native-probe' else tmp_path / 'jdk/bin/java'
        # Both processes need the group cleanup's KILL after its TERM grace period.
        tool.write_text(f'#!{sys.executable}\n' + '''import os, signal, subprocess, sys, time
from pathlib import Path
signal.signal(signal.SIGTERM, signal.SIG_IGN)
marker = Path(os.environ['SLEEPER_PID'])
subprocess.Popen([sys.executable, '-c',
    "import os,signal,time; from pathlib import Path; "
    "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
    "Path(os.environ['SLEEPER_PID'] + '.child').write_text(str(os.getpid())); time.sleep(120)"])
while not Path(str(marker) + '.child').exists():
    time.sleep(.01)
marker.write_text(str(os.getpid()))
time.sleep(120)
''')
    elif stage == 'runtime':
        tool = launcher.bin / 'sbt'
        extra.update(FAKE_JAVA_GO=str(tmp_path / 'java-go'), FAKE_JAVA_STARTED=str(marker))
    else:
        tool = launcher.bin / 'sbt'
        tool.write_text('''#!/bin/bash
case " $* " in *" boom/compile "*) compile=1 ;; *) compile=0 ;; esac
if [ "$SLEEP_STAGE" = compile ] && [ "$compile" = 0 ]; then exit 0; fi
echo $$ > "$SLEEPER_PID"
exec /bin/sleep 120
''')
    tool.chmod(0o755)
    process = launcher(RVW_NO_LOCK='', SLEEPER_PID=str(marker), SLEEP_STAGE=stage, **extra)
    child = None
    try:
        wait_for_file(marker, process)
        child = int(marker.read_text())
        if stage in ('compile', 'native-probe', 'runtime'):
            assert status('boom', tmp_path / 'locks')['held']
        process.send_signal(sig)
        out, err = process.communicate(timeout=15)
        assert not process_alive(child), (child, out, err)
        descendant = Path(str(marker) + '.child')
        if descendant.exists():
            assert not process_alive(int(descendant.read_text())), (out, err)
        assert process.returncode == 128 + sig, (out, err)
        assert not status('boom', tmp_path / 'locks')['held']
        assert not list(tmp_path.glob('riscvsim-launch.*'))
        result = run_group([str(tmp_path / 'scripts/with-lock.sh'), 'boom',
                            sys.executable, '-c', 'print("acquired")'],
                           env=launcher.env, capture=True, timeout=3)
        assert result.returncode == 0 and result.stdout.strip() == 'acquired', result
    finally:
        kill_group(process, grace=0.2)
        if child is not None:
            try:
                os.killpg(child, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                os.kill(child, signal.SIGKILL)
            except ProcessLookupError:
                pass
        descendant = Path(str(marker) + '.child')
        if descendant.exists() and process_alive(int(descendant.read_text())):
            os.kill(int(descendant.read_text()), signal.SIGKILL)


@pytest.mark.parametrize('sig', [signal.SIGTERM, signal.SIGINT, signal.SIGHUP])
def test_native_launch_cancel_stops_java_and_removes_private_inputs(tmp_path, sig):
    import json
    java = Path(os.environ['JAVA_HOME']) / 'bin/java'
    source = tmp_path / 'Sleeper.java'
    source.write_text('''import java.nio.file.*;
class Sleeper {
  public static void main(String[] args) throws Exception {
    Files.writeString(Path.of(args[0]), Long.toString(ProcessHandle.current().pid()));
    Thread.sleep(120000);
  }
}
''')
    inputs = tmp_path / 'inputs'
    inputs.mkdir()
    from rvw.common.capture import Capture, _stamp
    helper = SCRIPT.with_name('native-identity.py')
    cap = Capture(tmp_path / 'capture')
    item = cap.tool(java)
    tool = {'path': item.resolved, 'source': item.source, 'sha256': item.sha256,
            'stamp': list(map(str, cap._stamps[item.source])), 'symlinks': list(item.symlinks),
            'link_stamps': [{'path': link, 'stamp': list(map(str, _stamp(Path(link).lstat())))}
                            for link, _ in item.symlinks]}
    record = {'tools': {'java': tool}, 'file_stamps': [],
              'environment': {'PATH': os.environ['PATH']},
              'make_wrapper_path': str(SCRIPT.with_name('make-jobs.sh'))}
    marker = tmp_path / 'java.pid'
    process = subprocess.Popen([sys.executable, str(helper), 'launch', '--inputs', str(inputs),
                                json.dumps(record), str(tmp_path), str(source), str(marker)],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               start_new_session=True)
    child = None
    try:
        wait_for_file(marker, process)
        child = int(marker.read_text())
        assert list(tmp_path.glob('native-bin.*'))
        process.send_signal(sig)
        out, err = process.communicate(timeout=15)
        assert process.returncode == 128 + sig, (out, err)
        assert not process_alive(child), (out, err)
        assert not inputs.exists()
        assert not list(tmp_path.glob('native-bin.*'))
    finally:
        kill_group(process, grace=0.2)
        if child is not None:
            try:
                os.killpg(child, signal.SIGKILL)
            except ProcessLookupError:
                pass


# ------------------------------------------------------------------ review 17: dependency inputs


# ------------------------------------------------------------------ review 19: native build inputs

def test_native_flags_change_adapter_identity(launcher):
    def identity(flags):
        result = run_group([str(launcher.sim / "boom/run.sh"), "identity"],
                           env={**launcher.env, "SPINAL_VERILATOR_FLAGS": flags}, capture=True, timeout=30)
        assert result.returncode == 0, result.stderr
        return result.stdout
    assert identity("") != identity("-DFLAG_FAIL")


@pytest.mark.parametrize("variable,value", [
    ("SPINAL_VERILATOR_FLAGS", "-DFLAG_FAIL"), ("CXX", "g++"), ("CFLAGS", "-DFLAG_FAIL"),
    ("CXXFLAGS", "-O1"), ("CPPFLAGS", "-DFLAG_FAIL"), ("LDFLAGS", "-pthread"),
    ("VERILATOR_ROOT", "/missing/root"), ("USER_CPPFLAGS", "-DFLAG_FAIL"),
    ("RISCVSIM_MAKE_JOBS", "2"), ("UNLISTED_NATIVE_SETTING", "changed"),
])
def test_native_identity_covers_build_environment(launcher, variable, value):
    import json
    helper = launcher.sim / "scripts/native-identity.py"
    def capture(env):
        r = run_group(["python3", str(helper)], env=env, capture=True, timeout=30)
        assert r.returncode == 0, r.stderr
        return json.loads(r.stdout)
    before = capture(launcher.env)
    after = capture({**launcher.env, variable: value})
    assert before["sha256"] != after["sha256"]
    if variable != "UNLISTED_NATIVE_SETTING":
        assert after["environment"][variable] == value


@pytest.mark.parametrize("variable,value", [
    ("MAKEFLAGS", "-e CXX=other-compiler"), ("MAKEFILES", "/custom/policy.mk"),
    ("SPINAL_VERILATOR_FLAGS", "-f /custom/policy.f"), ("CXXFLAGS", "-include /custom/policy.h"),
    ("SPINAL_MAKE_CMD", "/custom/make-wrapper"), ("RISCVSIM_MAKE", "/custom/make"),
    ("CPATH", "/custom/includes"), ("SPINAL_UNKNOWN_NATIVE_FLAG", "anything"),
])
def test_opaque_native_inputs_disable_cache(launcher, variable, value):
    import json
    r = run_group(["python3", str(launcher.sim / "scripts/native-identity.py")],
                  env={**launcher.env, variable: value}, capture=True, timeout=30)
    assert r.returncode == 0, r.stderr
    identity = json.loads(r.stdout)
    assert identity["cache_enabled"] is False
    assert any(variable in reason for reason in identity["cache_disabled_reasons"])


def test_opaque_native_inputs_refuse_adapter_identity_for_result_reuse(launcher):
    r = run_group([str(launcher.sim / "boom/run.sh"), "identity"],
                  env={**launcher.env, "SPINAL_VERILATOR_FLAGS": "-f policy.f"}, capture=True, timeout=30)
    assert r.returncode != 0 and "refusing identity" in r.stderr


@pytest.mark.parametrize("tool", ["verilator", "compiler"])
def test_native_identity_binds_full_tool_versions(launcher, tmp_path, tool):
    import json
    version = tmp_path / "tool-version"
    version.write_text("native-tool 1.0")
    if tool == "verilator":
        probe = launcher.bin / "verilator"
        probe.write_text('#!/bin/bash\nif [ "$1" = --version ]; then cat "$NATIVE_VERSION"; '
                         'else exec "$REAL_VERILATOR" "$@"; fi\n')
        probe.chmod(0o755)
        env = {**launcher.env, "NATIVE_VERSION": str(version), "REAL_VERILATOR": shutil.which("verilator")}
        record_key = "verilator"
    else:
        probe = launcher.bin / "test-cxx"
        probe.write_text('#!/bin/bash\ncat "$NATIVE_VERSION"\n')
        probe.chmod(0o755)
        env = {**launcher.env, "NATIVE_VERSION": str(version), "CXX": str(probe)}
        record_key = "env_cxx"
    def capture():
        r = run_group(["python3", str(launcher.sim / "scripts/native-identity.py")],
                      env=env, capture=True, timeout=30)
        assert r.returncode == 0, r.stderr
        return json.loads(r.stdout)
    before = capture()
    version.write_text("native-tool 1.1")
    after = capture()
    assert before["tools"][record_key]["version"] == "native-tool 1.0"
    assert after["tools"][record_key]["version"] == "native-tool 1.1"
    assert before["sha256"] != after["sha256"]


def test_native_identity_cancellation_stops_probe_descendants(launcher, tmp_path):
    import signal
    pids = tmp_path / "probe-pids"
    probe = launcher.bin / "verilator"
    probe.write_text('''#!/usr/bin/env python3
import os, subprocess, sys, time
from pathlib import Path
child = subprocess.Popen([sys.executable, '-c',
    'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(120)'])
Path(os.environ['PROBE_PIDS']).write_text(f'{os.getpid()} {child.pid}')
time.sleep(120)
''')
    probe.chmod(0o755)
    try:
        r = run_group(["python3", str(launcher.sim / "scripts/native-identity.py")],
                      env={**launcher.env, "PROBE_PIDS": str(pids)}, capture=True, timeout=2, grace=2)
        assert r.timed_out and pids.is_file(), (r, pids.exists())
        for pid in pids.read_text().split():
            state = run_group(["ps", "-o", "stat=", "-p", pid], capture=True, timeout=5)
            assert not state.stdout.strip() or state.stdout.strip().startswith("Z"), (pid, state.stdout)
    finally:
        if pids.is_file():
            try:
                os.killpg(int(pids.read_text().split()[0]), signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_real_native_flags_invalidate_cache_and_enter_c1_and_replay(tmp_path):
    """A one-bit Verilator fixture, never BOOM. Reproduce the review's false pass in new JVMs."""
    import json
    import shlex
    import sys
    from rvw.runs.adapter import parse_replay

    repo = SCRIPT.parents[2]
    sim = repo / "RiscvSim"
    # Reuse the generic sbt project without loading the external BOOM build.
    project = tmp_path / "generic-project"
    (project / "project").mkdir(parents=True)
    (project / "src").symlink_to(sim / "src", target_is_directory=True)
    (tmp_path / "SpinalTrace").symlink_to(repo / "SpinalTrace", target_is_directory=True)
    (tmp_path / "SpinalWaves").symlink_to(repo / "SpinalWaves", target_is_directory=True)
    (project / "build.sbt").write_text((sim / "build.sbt").read_text())
    shutil.copy2(sim / "project/build.properties", project / "project/build.properties")
    env = {**os.environ, "RVW_LOCK_PYTHON": sys.executable, "RVW_PYTHON": sys.executable}
    env.pop("SPINAL_BOOM", None)
    # Use the checked-in make wrapper. This test must also prove stable native cache hits.
    env["SPINAL_MAKE_CMD"] = str(sim / "scripts/make-jobs.sh")
    # Load the library from an external build too. sbt resolves relative
    # ProjectRefs against the defining build, not the consumer's cwd.
    consumer = tmp_path / "consumer" / "deep"
    (consumer / "project").mkdir(parents=True)
    shutil.copy2(sim / "project/build.properties", consumer / "project/build.properties")
    (consumer / "build.sbt").write_text(
        'lazy val root = (project in file(".")).dependsOn('
        'ProjectRef(file("../../generic-project"), "riscvsim"))\n')
    ref = '{' + project.as_uri() + '/}riscvsim'
    build = run_group([str(repo / "scripts/with-lock.sh"), f"sbt-{repo.name}", "nice", "-n", "10", "sbt",
                       "-J-Xmx1g", "-Dsbt.offline=true", "-batch", f"{ref}/Test/compile", f"export {ref}/Test/fullClasspath"],
                      cwd=consumer, env=env, capture=True, timeout=240)
    assert build.returncode == 0, (build.stdout, build.stderr)
    cp = next(line for line in reversed(build.stdout.splitlines())
              if not line.startswith("[") and "scala-library" in line)
    (tmp_path / "FlagBox.v").write_text('''module FlagBox(output bad);
`ifdef FLAG_FAIL
assign bad = 1;
`else
assign bad = 0;
`endif
endmodule
''')
    java = str(Path(env["JAVA_HOME"]) / "bin/java")
    results = {}
    pinning_supported = 'def launch(' in (sim / 'scripts/native-identity.py').read_text()
    def native_command(identity, arguments):
        if pinning_supported:
            return ['python3', str(sim / 'scripts/native-identity.py'), 'launch', identity, str(tmp_path), *arguments]
        return [java, '-Driscvsim.native.identity=' + identity, *arguments]
    header = tmp_path / "policy.h"
    header.write_text("// An external compiler input disables native reuse.\n")
    opaque_flags = "-DFLAG_FAIL -CFLAGS " + shlex.quote("-include " + str(header))
    for label, flags, cache in [("base", "", "cache"), ("base-hit", "", "cache"),
                                ("changed", "-DFLAG_FAIL", "cache"),
                                ("changed-hit", "-DFLAG_FAIL", "cache"),
                                ("fresh", "-DFLAG_FAIL", "fresh-cache"),
                                ("opaque", opaque_flags, "cache")]:
        native_env = {**env, "SPINAL_VERILATOR_FLAGS": flags}
        identity = run_group(["python3", str(sim / 'scripts/native-identity.py')],
                             env=native_env, capture=True, timeout=30)
        assert identity.returncode == 0, identity.stderr
        run = run_group(native_command(identity.stdout, ["-Xmx1g", f"-Driscvsim.tools={repo}",
                         "-cp", cp, "riscvsim.NativeFlagsProbe", str(tmp_path), cache, label]),
                        cwd=sim, env=native_env, capture=True, timeout=120)
        assert run.returncode == 0, (run.stdout, run.stderr)
        result = json.loads((tmp_path / label / "result.json").read_text())
        assert result["status"] == ("fail" if flags else "pass"), (result, run.stdout, run.stderr)
        assert result['rtl_sha256'] and len(result['rtl_sha256']) == 64
        if label != 'opaque':
            assert not result.get('inconclusive'), result
        native = result["tools"]["native_build"]
        assert native["cache_enabled"] == (label != "opaque"), native
        assert native["environment"]["SPINAL_VERILATOR_FLAGS"] == flags
        assert native["tools"]["compiler"]["version"] and native["tools"]["verilator"]["version"]
        assert ("Found cached verilator binaries" in run.stdout) == label.endswith("-hit"), run.stdout
        tokens = shlex.split(result["replay"])
        assert f"SPINAL_VERILATOR_FLAGS={flags}" in tokens
        assert "-u" in tokens and "CXX" in tokens
        # Existing debug readers must preserve the env command when they decode replay.
        cmd = parse_replay(result["replay"], repo)
        assert cmd.env["SPINAL_VERILATOR_FLAGS"] == flags
        assert "CXX" in cmd.unset and "CXX" not in cmd.env
        cmd.environment = {**env, "SPINAL_VERILATOR_FLAGS": "wrong", "CXX": "wrong"}
        replay = run_group([*cmd.exe[:-1], sys.executable, "-c",
                            "import json,os; print(json.dumps([os.getenv('SPINAL_VERILATOR_FLAGS'), os.getenv('CXX')]))"],
                           env=cmd.child_environment(),
                           capture=True, timeout=10)
        assert replay.returncode == 0, replay.stderr
        assert json.loads(replay.stdout) == [flags, None]
        results[label] = native["sha256"]
    assert results["base"] == results["base-hit"]
    assert results["changed"] == results["changed-hit"] == results["fresh"]
    assert results["base"] != results["changed"]
    assert list((tmp_path / "cache" / native["namespace"]).iterdir())
@pytest.mark.parametrize("make_suffix", [
    "include external-policy.mk\n",
    "#DEPS := $(wildcard *.d)\nifneq ($(DEPS),)\n  include $(DEPS)\nendif\n",
])
def test_native_make_configuration_with_includes_refuses_reuse(launcher, tmp_path, make_suffix):
    import json
    root = tmp_path / 'custom-verilator'
    (root / 'include').mkdir(parents=True)
    (root / 'include/verilated.mk').write_text('CXX = g++\nLINK = g++\n' + make_suffix)
    probe = launcher.bin / 'verilator'
    probe.write_text('''#!/bin/bash
if [ "$1" = --version ]; then echo 'native-verilator 1.0';
else printf 'VERILATOR_ROOT = %s\\n' "$NATIVE_TEST_ROOT"; fi
''')
    probe.chmod(0o755)
    r = run_group(['python3', str(launcher.sim / 'scripts/native-identity.py')],
                  env={**launcher.env, 'NATIVE_TEST_ROOT': str(root)}, capture=True, timeout=30)
    assert r.returncode == 0, r.stderr
    identity = json.loads(r.stdout)
    assert identity['cache_enabled'] is False
    assert 'cannot enumerate Verilator make includes' in identity['cache_disabled_reasons']


@pytest.mark.parametrize("selection", ["configured", "environment"])
def test_native_compiled_compiler_wrapper_disables_reuse(launcher, tmp_path, selection):
    import json
    source = tmp_path / 'wrapper.c'
    source.write_text('#include <stdio.h>\nint main(void) { puts("ccache version 99"); return 0; }\n')
    wrapper = launcher.bin / 'ccache'
    build = run_group(['nice', '-n', '10', shutil.which('cc'), str(source), '-o', str(wrapper)],
                      capture=True, timeout=30)
    assert build.returncode == 0, build.stderr
    env = dict(launcher.env)
    if selection == 'configured':
        (launcher.bin / 'g++').symlink_to(wrapper)
        root = tmp_path / 'configured-verilator'
        (root / 'include').mkdir(parents=True)
        (root / 'include/verilated.mk').write_text('CXX = g++\nLINK = g++\n')
        probe = launcher.bin / 'verilator'
        probe.write_text('''#!/bin/bash
if [ "$1" = --version ]; then echo 'native-verilator 1.0';
else printf 'VERILATOR_ROOT = %s\\n' "$NATIVE_TEST_ROOT"; fi
''')
        probe.chmod(0o755)
        env['NATIVE_TEST_ROOT'] = str(root)
        record_key = 'compiler'
    else:
        env['CXX'] = str(wrapper)
        record_key = 'env_cxx'
    r = run_group(['python3', str(launcher.sim / 'scripts/native-identity.py')],
                  env=env, capture=True, timeout=30)
    assert r.returncode == 0, r.stderr
    identity = json.loads(r.stdout)
    assert identity['tools'][record_key]['version'] == 'ccache version 99'
    assert identity['cache_enabled'] is False
    assert any('wrapper inputs' in reason for reason in identity['cache_disabled_reasons'])


def test_native_launch_pins_the_collected_lookup_target(launcher, tmp_path, monkeypatch):
    from test_native_identity import helper
    from types import SimpleNamespace
    module = helper()
    real = shutil.which('verilator')
    alias = launcher.bin / 'verilator'
    alias.symlink_to(real)
    monkeypatch.setenv('PATH', launcher.env['PATH'])
    monkeypatch.setenv('JAVA_HOME', launcher.env['JAVA_HOME'])
    record = module.collect()
    alias.unlink()
    alias.symlink_to('/missing/alternate-verilator')
    launched = []

    def run(command, **kwargs):
        environment = kwargs['env']
        selected = Path(environment['PATH'].split(os.pathsep)[0]) / 'verilator'
        assert selected.resolve() == Path(record['tools']['verilator']['path'])
        launched.append(command)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(module, 'run_group', run)
    assert module.launch(record, tmp_path, ['--version']) == 0
    assert len(launched) == 1
    assert not list(tmp_path.glob('native-bin.*'))


def test_generic_build_does_not_load_core_projects():
    """The library must load in installations with no adjacent core checkout."""
    from pathlib import Path
    repo = Path(__file__).resolve().parents[2]
    build = (repo / "RiscvSim/build.sbt").read_text()
    # The generic trace library is required by --spinaltrace. Permit that exact
    # reference only; a core ProjectRef must still fail this check.
    trace_ref = 'ProjectRef(file("../SpinalTrace/spinaltrace"), "spinaltrace")'
    assert build.count(trace_ref) == 1
    assert "ProjectRef" not in build.replace(trace_ref, "")
    assert "SPINAL_BOOM" not in build
    adapter = (repo / "RiscvSim/boom/build.sbt").read_text()
    assert 'ProjectRef(file("..").getCanonicalFile, "riscvsim")' in adapter
    vex = (repo / "examples/vexriscv/rvw/build.sbt").read_text()
    assert 'ProjectRef(workstation / "RiscvSim", "riscvsim")' in vex
    assert 'workstation / "RiscvSim/src/main/scala"' not in vex


