#!/usr/bin/env python3
"""Identify native tools once, then launch the JVM with pinned command paths.

Only closed build options earn native reuse. Opaque hooks disable conclusive results.
Tools and their installed data stay stable during a launch under C8.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "rvw/src"))
from rvw.common.proc import run_group, _defer_cancellation


NAMESPACE = "native-inputs-v28"
# The bundled build tools do not read shell bookkeeping or the inherited lock descriptor.
# Custom wrappers and shell expansions are excluded from native reuse below.
BOOKKEEPING = {"_", "PWD", "OLDPWD", "SHLVL", "RVW_LOCKS_HELD", "RVW_PYTHON",
               "RISCVSIM_WORK", "RISCVSIM_CP_CACHE", "RISCVSIM_XMX", "RISCVSIM_CACHE_ENTRIES"}
# Agent frontends assign a new call ID to each shell invocation. Standard native
# tools do not read these UI identifiers. Keep unknown settings in the digest.
FRONTEND_BOOKKEEPING = {"CODEX_TOOL_CALL_ID", "CODEX_THREAD_ID", "CODEX_SESSION_ID",
                        "T3CODE_THREAD_ID", "XPC_SERVICE_NAME", "RVW_COSIM_PORT", "RVW_RVFI_FLUSH"}
BOOKKEEPING |= FRONTEND_BOOKKEEPING
VARIABLES = """SPINAL_BOOM SPINAL_VERILATOR_FLAGS SPINAL_MAKE_CMD RISCVSIM_MAKE RISCVSIM_MAKE_JOBS
RISCVSIM_COVERAGE CXX CC CPP LINK AR CFLAGS CXXFLAGS CPPFLAGS LDFLAGS LDLIBS
USER_CPPFLAGS USER_LDFLAGS USER_LDLIBS OPT OPT_FAST OPT_SLOW OPT_GLOBAL OBJCACHE
MAKE MAKEFLAGS MFLAGS MAKEOVERRIDES MAKEFILES GNUMAKEFLAGS VERILATOR_ROOT VERILATOR_BIN
VERILATOR_GDB VERILATOR_GDBBT VERILATOR_FLAGS VERILATOR_NO_OPT VFLAGS
CPATH C_INCLUDE_PATH CPLUS_INCLUDE_PATH OBJC_INCLUDE_PATH LIBRARY_PATH COMPILER_PATH
GCC_EXEC_PREFIX CCC_OVERRIDE_OPTIONS SDKROOT DEVELOPER_DIR MACOSX_DEPLOYMENT_TARGET
CCACHE_PREFIX CCACHE_PATH CCACHE_CONFIGPATH LD_PRELOAD LD_LIBRARY_PATH DYLD_LIBRARY_PATH
DYLD_INSERT_LIBRARIES BASH_ENV ENV PERL5OPT PERL5LIB PYTHONPATH PYTHONHOME
JAVA_HOME PATH""".split()
FLAG_VARIABLES = """CFLAGS CXXFLAGS CPPFLAGS LDFLAGS LDLIBS USER_CPPFLAGS USER_LDFLAGS
USER_LDLIBS OPT OPT_FAST OPT_SLOW OPT_GLOBAL""".split()
# These can inject files, commands or compiler options which this collector cannot resolve.
OPAQUE_VARIABLES = """MAKEFLAGS MFLAGS MAKEOVERRIDES MAKEFILES GNUMAKEFLAGS OBJCACHE
VERILATOR_BIN VERILATOR_GDB VERILATOR_GDBBT VERILATOR_FLAGS VERILATOR_NO_OPT VFLAGS
CPATH C_INCLUDE_PATH CPLUS_INCLUDE_PATH OBJC_INCLUDE_PATH LIBRARY_PATH COMPILER_PATH
GCC_EXEC_PREFIX CCC_OVERRIDE_OPTIONS CCACHE_PREFIX CCACHE_PATH CCACHE_CONFIGPATH
LD_PRELOAD LD_LIBRARY_PATH DYLD_LIBRARY_PATH DYLD_INSERT_LIBRARIES BASH_ENV ENV
PERL5OPT PERL5LIB PYTHONPATH PYTHONHOME""".split()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def collect(*, include_java=True):
    reasons = []
    inherited = dict(os.environ)
    # The runner declares the core checkout selector. Emitted RTL identifies its content;
    # selecting another checkout does not change the native compiler inputs.
    source_env = inherited.get('RVW_CAPTURE_SOURCE_ENV')
    source_selectors = {source_env} if source_env else set()
    names = set(VARIABLES) | {k for k in inherited if k.startswith(
        ("VERILATOR_", "SPINAL_", "CCACHE_", "GCC_", "CLANG_", "DYLD_", "LD_"))}
    environment = {name: inherited.get(name) for name in sorted(names - source_selectors)}
    ignored = BOOKKEEPING | source_selectors | {k for k in inherited if k.startswith(("RVW_CAPTURE_", "RVW_LOCK_"))}
    result = {"namespace": NAMESPACE, "environment": environment,
              "environment_sha256": digest({k: v for k, v in inherited.items() if k not in ignored}),
              "environment_ignored": sorted(BOOKKEEPING | source_selectors), "tools": {}}
    files, versions = {}, {}

    def file(path):
        path = path.resolve(strict=True)
        key = str(path)
        if key not in files:
            with path.open("rb") as stream:
                data = stream.read()
                info = os.fstat(stream.fileno())
            files[key] = ({"path": key, "sha256": hashlib.sha256(data).hexdigest(),
                           "size": str(info.st_size), "modified_ns": str(info.st_mtime_ns)}, data)
        return files[key]

    def tool(name, command):
        # Never evaluate shell syntax, make variables or compiler wrappers to identify a tool.
        try:
            args = shlex.split(command)
        except ValueError:
            args = []
        if len(args) != 1 or re.search(r"[$`;|&<>\n]", command):
            reasons.append(f"cannot enumerate {name} command")
            return None
        path = shutil.which(args[0])
        if path is None:
            reasons.append(f"cannot resolve {name}")
            return None
        try:
            descriptor, data = file(Path(path))
            path = Path(descriptor["path"])
            if name == "ar":
                version = "archiver"
            else:
                if str(path) not in versions:
                    probe = run_group([str(path), "--version"], capture=True, timeout=10, grace=0.5)
                    versions[str(path)] = (((probe.stdout or "") + (probe.stderr or "")).strip()
                                           if probe.returncode == 0 and not probe.timed_out else "")
                version = versions[str(path)]
        except (OSError, ValueError) as exc:
            reasons.append(f"cannot identify {name}: {exc}")
            return None
        record = {"command": command, "invocation_name": Path(args[0]).name,
                  "path": str(path), "sha256": descriptor["sha256"], "version": version}
        result["tools"][name] = record
        if not record["version"]:
            reasons.append(f"cannot read {name} --version")
        if name in ("ar", "make", "sh", "bash", "perl") and data.startswith(b"#!"):
            reasons.append(f"cannot enumerate {name} wrapper inputs")
        if name in ("compiler", "linker", "env_cxx", "env_cc"):
            compiler_name = r"(?:[A-Za-z0-9_.]+-)*(?:g\+\+|c\+\+|clang\+\+|gcc|clang|cc)(?:-[0-9.]+)?"
            wrapper_version = re.search(r"\b(?:ccache|sccache|distcc|icecc)\b", record["version"], re.I)
            if data.startswith(b"#!") or not re.fullmatch(compiler_name, path.name) or wrapper_version:
                reasons.append(f"cannot enumerate {name} wrapper inputs")
        return path

    tool("python", shlex.quote(sys.executable))
    verilator = tool("verilator", "verilator")
    # The standard Perl launcher runs a native binary beside its resolved script.
    # Its bytes belong to the tool identity even when its version string is unchanged.
    if verilator and (verilator.parent / "verilator_bin").is_file():
        tool("verilator_bin", shlex.quote(str(verilator.parent / "verilator_bin")))
    root = None
    if verilator:
        probe = run_group([str(verilator), "-V"], capture=True, timeout=10, grace=0.5)
        # -V lists compiled defaults first and the effective environment last.
        roots = re.findall(r"^\s*VERILATOR_ROOT\s*=\s*(.*?)\s*$", probe.stdout or "", re.M)
        if probe.returncode == 0 and roots:
            root = Path(roots[-1])
    if root and (root / "include/verilated.mk").is_file():
        mk = root / "include/verilated.mk"
        makefile, data = file(mk)
        result["verilator_root"] = str(Path(makefile["path"]).parent.parent)
        result["verilated_mk_path"] = makefile["path"]
        result["verilated_mk_sha256"] = makefile["sha256"]
        text = data.decode()
        # Standard Verilator includes only compiler-generated .d files in the private build
        # workspace. An installation that includes other makefiles needs a fresh native build.
        private_deps = "DEPS := $(wildcard *.d)\nifneq ($(DEPS),)\n  include $(DEPS)\nendif"
        checked_text = re.sub(r"^" + re.escape(private_deps) + r"(?=\n|$)", "", text, flags=re.M)
        if re.search(r"^\s*(?:-?include|sinclude)\s+", checked_text, re.M):
            reasons.append("cannot enumerate Verilator make includes")
        for variable, name in (("CXX", "compiler"), ("LINK", "linker")):
            values = re.findall(rf"^{variable}\s*=\s*(.*?)\s*$", text, re.M)
            if len(values) == 1:
                tool(name, values[0])
            else:
                reasons.append(f"cannot enumerate verilated.mk {variable}")
    else:
        reasons.append("cannot enumerate Verilator make configuration")
    for variable, name in (("CXX", "env_cxx"), ("CC", "env_cc")):
        if os.environ.get(variable):
            tool(name, os.environ[variable])
    tool("make", os.environ.get("RISCVSIM_MAKE") or "make")
    tool("ar", "ar")
    for interpreter in ["sh", "bash", "perl"]:
        tool(interpreter, interpreter)

    # Spinal supplies these flags itself. Environment additions must not introduce another
    # source, include, response file, linker script or a shell expansion behind our key.
    simple = r"(?:-D[A-Za-z_][A-Za-z_0-9]*(?:=[A-Za-z_0-9.+-]+)?|-U[A-Za-z_][A-Za-z_0-9]*|-O[0-3sg]|-g[0-3]?|-std=[A-Za-z_0-9+]+|-fPIC|-pthread)"
    for variable in ["SPINAL_VERILATOR_FLAGS", *FLAG_VARIABLES]:
        value = os.environ.get(variable, "")
        try:
            tokens = shlex.split(value)
        except ValueError:
            tokens = ["<invalid>"]
        if variable == "SPINAL_VERILATOR_FLAGS":
            tokens = [t for t in tokens if t not in ("-CFLAGS", "-LDFLAGS")]
            # These options only change native code generation. They cannot name
            # external files. Keep their exact spelling and values in the identity.
            numeric = {"--threads", "--output-split", "--output-split-cfuncs"}
            remaining = []
            i = 0
            while i < len(tokens):
                if (tokens[i] in numeric and i + 1 < len(tokens)
                        and re.fullmatch(r"[0-9]{1,9}", tokens[i + 1])
                        and (tokens[i] != "--threads" or int(tokens[i + 1]) > 0)):
                    i += 2
                else:
                    remaining.append(tokens[i])
                    i += 1
            tokens = remaining
        if any(not re.fullmatch(simple, t) for t in tokens):
            reasons.append(f"cannot enumerate {variable} external inputs")
    for variable in OPAQUE_VARIABLES:
        if os.environ.get(variable):
            reasons.append(f"cannot enumerate {variable} inputs")
    known = set(VARIABLES)
    for variable in sorted(names - known):
        if os.environ.get(variable):
            reasons.append(f"cannot enumerate {variable} inputs")
    wrapper = Path(__file__).with_name("make-jobs.sh").absolute()
    make_wrapper, _ = file(wrapper)
    result["make_wrapper_path"] = make_wrapper["path"]
    result["make_wrapper_sha256"] = make_wrapper["sha256"]
    if include_java:
        tool("java", str(Path(os.environ["JAVA_HOME"]) / "bin/java") if os.environ.get("JAVA_HOME") else "java")
    make_command = os.environ.get("SPINAL_MAKE_CMD", "make")
    if make_command != "make" and Path(make_command).resolve() != Path(make_wrapper["path"]):
        reasons.append("cannot enumerate SPINAL_MAKE_CMD inputs")
    if os.environ.get("RISCVSIM_MAKE") not in (None, "", "make"):
        reasons.append("cannot enumerate RISCVSIM_MAKE inputs")
    result["cache_disabled_reasons"] = reasons
    result["cache_enabled"] = not reasons
    result["sha256"] = digest(result)
    # Publication uses only cheap stats. These metadata values do not enter the identity.
    result["provenance"] = dict(result)
    result["files"] = [item for _, (item, _) in sorted(files.items())]
    return result


def launch(record, directory, command):
    """Use private lookup names and preserve C++ driver names such as clang++."""
    pinned = None
    try:
        with _defer_cancellation():
            pinned = Path(tempfile.mkdtemp(prefix='native-bin.', dir=Path(directory).resolve()))
        for name in ['verilator', 'make', 'ar', 'sh', 'bash', 'perl']:
            if name in record['tools']:
                (pinned / name).symlink_to(record['tools'][name]['path'])
        environment = dict(os.environ)
        environment['PATH'] = str(pinned) + os.pathsep + record['environment']['PATH']
        for key, tool in [('RISCVSIM_PINNED_MAKE', 'make'), ('RISCVSIM_PINNED_CXX', 'compiler'),
                          ('RISCVSIM_PINNED_LINK', 'linker'), ('RISCVSIM_PINNED_AR', 'ar')]:
            if tool in record['tools']:
                selected = record['tools'][tool]
                if tool in ('compiler', 'linker'):
                    # C++ drivers can select their mode from argv[0] (clang++ vs clang).
                    # Keep separate directories in case CXX and LINK use the same name.
                    target = pinned / tool / selected['invocation_name']
                    target.parent.mkdir()
                    target.symlink_to(selected['path'])
                    environment[key] = str(target)
                else:
                    environment[key] = selected['path']
        environment['RISCVSIM_PINNED_BIN'] = str(pinned)
        environment['SPINAL_MAKE_CMD'] = record['make_wrapper_path']
        # `java` itself is pinned too. A caller may supply extra JVM properties and arguments.
        executable = record['tools']['java']['path']
        result = run_group([executable, '-Driscvsim.native.identity=' + canonical(record),
                            '-Driscvsim.native.bin=' + str(pinned), *command], env=environment)
        return result.returncode
    finally:
        if pinned is not None:
            shutil.rmtree(pinned)


if __name__ == "__main__":
    # Convert process-group cancellation into an exception, so run_group cleans its tool tree.
    def cancelled(signum, frame):
        raise SystemExit(128 + signum)
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, cancelled)
    if len(sys.argv) > 1 and sys.argv[1] == 'launch':
        inputs = None
        args = sys.argv[2:]
        if args[0] == '--inputs':
            inputs, args = Path(args[1]), args[2:]
        try:
            sys.exit(launch(json.loads(args[0]), args[1], args[2:]))
        finally:
            if inputs is not None:
                shutil.rmtree(inputs)

    else:
        print(canonical(collect()))
