"""Inputs of a regress run, recorded once at start. Declarations are a user completeness claim.

The adapter runs in place: on the selected core tree, the declared tools and the real PATH.
C8 puts edits during a run out of scope, so nothing is copied for execution. The capture
records the identity of `cache_paths`, the adapter, the tools and the declared environment
for the job keys; the adapter's `identity` adds the design (RTL) identity.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
from pathlib import Path
import shlex
import shutil
import sys
import tempfile
import weakref

from rvw.common.interpreter import bind_interpreter, script_interpreter
from rvw.common.capture import Capture, CaptureError
from rvw.common.proc import run_group, _defer_cancellation
from .routing import OptionInputs, is_git


def private_directory(core, source=None, *, prefix='.rvw-inputs-'):
    """Store captures outside every declared input tree, regardless of --out."""
    paths = [core.source_repo, *core.cache_paths, *(s.dir for s in core.suites.values())]
    paths += [Path(arg) for arg in core.adapter if Path(arg).is_dir()]
    if source is not None:
        paths.append(source.path)
    roots = [Path(path).resolve() for path in paths if path is not None]
    for base in (Path(tempfile.gettempdir()), Path.home() / '.cache/rvw/inputs', Path('/var/tmp')):
        base = base.resolve()
        if any(base.is_relative_to(root) for root in roots):
            continue
        try:
            base.mkdir(parents=True, exist_ok=True)
            directory = Path(tempfile.mkdtemp(prefix=prefix, dir=base))
        except OSError:
            continue
        try:
            (directory / '.rvw-private-inputs').write_text('rvw.regress-inputs/1\n')
            return directory
        except BaseException:
            remove_private(directory)
            raise
    raise CaptureError('input_not_captured:storage', 'no private storage outside the input trees')


def remove_private(directory):
    """Remove an owned capture, including sealed read-only directories."""
    with _defer_cancellation():
        if directory.exists():
            for root, directories, _ in os.walk(directory):
                Path(root).chmod(0o700)
            shutil.rmtree(directory)


@contextlib.contextmanager
def private_storage(core, source=None, *, prefix='.rvw-inputs-'):
    directory = None
    try:
        with _defer_cancellation():
            directory = private_directory(core, source, prefix=prefix)
        yield directory
    finally:
        if directory is not None:
            remove_private(directory)


def adapter_roots(core):
    return [Path(arg) for arg in core.adapter[1:] if Path(arg).exists()]


class Inputs:
    def __init__(self, core, source, *, capture=None):
        self.directory = None
        self._cleanup = None
        self.closed = False
        try:
            with _defer_cancellation():
                self.directory = private_directory(core, source)
                self._cleanup = weakref.finalize(self, remove_private, self.directory)
            self._initialize(core, source, capture)
        except BaseException:
            self.close()
            raise

    def close(self):
        if self._cleanup is not None:
            self._cleanup()
        self.closed = True

    def _initialize(self, core, source, capture):
        self.cwd = Path.cwd()
        self.capture = capture if capture is not None else Capture(self.directory / 'capture')
        self.elfs = {}
        toolchain_env = ['CXX', 'CC', 'VERILATOR_ROOT'] if core.input_verilator_toolchain else []
        self.env = self.capture.env(*core.input_env, *toolchain_env, 'PATH')
        # Only declared environment reaches the adapter. Output/lock routing is added by the runner.
        self.child_env = {k: v for k, v in self.env.items() if v is not None}
        self.source = source
        self.adapter = []
        self.python_environments = {}
        self.problem = None
        self.options = OptionInputs(self.capture, [source.path, *core.cache_paths, *adapter_roots(core)],
                                    self.cwd)
        try:
            launcher = self.interpreter(sys.executable)
            self.child_env['RVW_PYTHON'] = str(launcher)
            self.child_env['RVW_LOCK_PYTHON'] = str(launcher)
            for name in core.input_tools:
                self.capture.tool(name)
            if core.input_verilator_toolchain:
                self.verilator_toolchain()
            for name in core.input_commands:
                # Record the executable the adapter will find on its PATH.
                selected = shutil.which(name, path=self.child_env.get('PATH', os.defpath))
                if selected is None or not self.capture.file(Path(selected)).executable:
                    raise CaptureError('input_not_captured:command', name)
            if source.path is None:
                raise CaptureError('input_not_captured:core', 'select a core source tree with source_env')
            if not source.reusable:
                raise CaptureError('input_not_captured:core', 'the core source identity is not covered')
            self.child_env[core.source_env] = str(source.path)
            self.child_env['RVW_CAPTURE_SOURCE_ENV'] = core.source_env
            # The adapter reports this descriptor as its C1 source.
            self.child_env['RVW_CAPTURE_SOURCE'] = json.dumps(source.to_dict(), sort_keys=True)
            for path in core.cache_paths:
                self.add(path)
            executable = shutil.which(core.adapter[0])
            if executable is None:
                raise CaptureError('input_not_captured:adapter', 'executable not found')
            first = Path(executable).absolute()
            header = self.capture.file(first).copy.read_bytes()[:4096]
            if header.startswith(b'#!'):
                words = script_interpreter(header)
                interpreter = self.interpreter(words[0])
                self.adapter = [str(interpreter), *words[1:], str(first)]
            elif first.name.startswith('python'):
                self.adapter = [str(self.interpreter(first))]
            else:
                # C1 adapters need no --version interface. Keep their byte identity.
                self.adapter = [str(self.capture.tool(first, identity_only=True).path)]
            for arg in core.adapter[1:]:
                path = Path(arg)
                if path.exists():
                    self.add(path)
                    self.adapter.append(str(path.absolute()))
                else:
                    self.adapter.append(arg)
            if not core.input_complete:
                raise CaptureError('input_not_captured:adapter_dependencies',
                                   'set input_complete=true and declare cache_paths, input_env and input_tools')
        except CaptureError as exc:
            self.problem = str(exc)

    def verilator_toolchain(self):
        """Record the compiler and linker that Verilator's makefile selects (and CXX/CC).

        Refuse a command that needs shell or make evaluation to name its executable.
        """
        verilator = self.capture.tool('verilator')
        probe = run_group([str(verilator.path), '-V'], env=self.child_env,
                          capture=True, timeout=10, grace=0.5)
        roots = re.findall(r'^\s*VERILATOR_ROOT\s*=\s*(.*?)\s*$', probe.stdout or '', re.M)
        if probe.timed_out or probe.returncode or not roots:
            raise CaptureError('input_not_captured:verilator_toolchain',
                               'cannot read VERILATOR_ROOT from verilator -V')
        makefile = self.capture.file(Path(roots[-1]) / 'include/verilated.mk')
        try:
            text = makefile.copy.read_text()
        except UnicodeError as exc:
            raise CaptureError('input_not_captured:verilator_toolchain',
                               'cannot decode verilated.mk') from exc
        commands = []
        for variable in ('CXX', 'LINK'):
            values = re.findall(rf'^{variable}\s*=\s*(.*?)\s*$', text, re.M)
            if len(values) != 1:
                raise CaptureError('input_not_captured:verilator_toolchain',
                                   f'cannot select verilated.mk {variable}')
            commands.append((variable, values[0]))
        commands += [(variable, self.env[variable]) for variable in ('CXX', 'CC')
                     if self.env.get(variable)]
        for variable, command in commands:
            try:
                args = shlex.split(command)
            except ValueError:
                args = []
            if len(args) != 1 or re.search(r'[$`;|&<>\n]', command):
                raise CaptureError('input_not_captured:verilator_toolchain',
                                   f'cannot enumerate {variable} command: {command}')
            self.capture.tool(args[0])

    def interpreter(self, name):
        return bind_interpreter(self.capture, name, environments=self.python_environments,
                                env=self.child_env, guard=lambda item: None, run=run_group)

    def add(self, path):
        path = Path(path).absolute()
        if path.is_dir():
            return self.capture.tree(path, git=is_git(path, self.capture))
        return self.capture.file(path)

    def elf(self, path):
        path = Path(path).absolute()
        if path not in self.elfs:
            self.elfs[path] = self.capture.file(path)
        return self.elfs[path]

    def record(self):
        record = self.capture.record()
        if self.problem and self.problem not in record['problems']:
            record['problems'].append(self.problem)
        return record
