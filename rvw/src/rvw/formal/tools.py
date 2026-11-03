"""Command-owned executable bindings for formal probes, proofs and replay."""
from __future__ import annotations

from contextvars import ContextVar
from pathlib import Path
import hashlib
import os
import shlex
import shutil

from rvw.common.capture import CaptureError

ACTIVE = ContextVar('formal_tools', default=None)

# These upstream commands have no successful --version interface. Their adapters
# report a captured content identity rather than inventing an upstream version.
_IDENTITY_ONLY = {'yosys-smtbmc', 'yosys-witness', 'yosys-abc', 'iverilog', 'vvp', 'pono', 'avy', 'btormc', 'btorsim'}
_SOLVERS = {'yices': 'yices-smt2', 'z3': 'z3', 'bitwuzla': 'bitwuzla',
            'boolector': 'boolector', 'cvc4': 'cvc4', 'cvc5': 'cvc5',
            'mathsat': 'mathsat', 'abc': 'yosys-abc'}
_OSS_PREFIX = '''#!/usr/bin/env bash
release_bindir="$(dirname "${BASH_SOURCE[0]}")"
release_bindir_abs="$("$release_bindir"/../libexec/realpath "$release_bindir/../bin")"
release_topdir_abs="$("$release_bindir"/../libexec/realpath "$release_bindir/..")"
export PATH="$release_bindir_abs:$PATH"
'''
_OSS_NATIVE_PREFIX = _OSS_PREFIX.replace('$release_bindir/../bin', '$release_bindir')
_ENV = ('PATH', 'HOME', 'TMPDIR', 'TMP', 'TEMP', 'LANG', 'LC_ALL', 'PYTHONPATH',
        'PYTHONHOME', 'YOSYS_DATDIR', 'LD_LIBRARY_PATH', 'DYLD_LIBRARY_PATH',
        'SYSTEMROOT')
_PYTHON_ENV = ('PYTHONHOME', 'PYTHONPATH', 'PYTHONEXECUTABLE', 'PYTHONUSERBASE',
               'PYTHONNOUSERSITE', 'PYTHONSAFEPATH', 'PYTHONPLATLIBDIR',
               'PYTHONPYCACHEPREFIX', 'PYTHONWARNINGS', 'PYTHONIOENCODING',
               'PYTHONUTF8', 'PYTHONMALLOC', 'PYTHONINSPECT', 'PYTHONSTARTUP',
               'PYTHONBREAKPOINT')


def _stamp(info):
    return tuple(getattr(info, k) for k in
                 ('st_dev', 'st_ino', 'st_mode', 'st_size', 'st_mtime_ns', 'st_ctime_ns'))


class Toolchain:
    def __init__(self, capture, args, directory):
        self.capture = capture
        self.directory = directory
        directory.mkdir()
        python_names = tuple(sorted(set(_PYTHON_ENV) |
                                    {k for k in os.environ if k.startswith('PYTHON')}))
        saved_env = capture.env(*dict.fromkeys((*_ENV, *python_names)))
        self.python_env = {k: saved_env[k] for k in python_names}
        self.env = {k: v for k, v in saved_env.items() if v is not None}
        self.raw = {}
        self.commands = {}
        self.identities = {}
        self.checks = []
        names = ['bash', 'yosys', 'sby', 'yosys-smtbmc', 'yosys-witness', 'yices-smt2']
        smtbmc_abc = False
        for engine in args.engine.split(','):
            parts = engine.strip().split(':')
            if parts[0] == 'smtbmc':
                solver = parts[1] if len(parts) > 1 else 'yices'
                if solver not in _SOLVERS:
                    raise CaptureError('input_not_captured:tool:solver', f'unsupported solver {solver}')
                names.append(_SOLVERS[solver])
                smtbmc_abc |= solver == 'abc'
            elif parts[0] == 'btor' and parts[1:] in (['pono'], ['btormc']):
                names.extend([parts[1], 'btorsim'])
            elif parts == ['aiger', 'avy']:
                names.extend(['avy', 'yosys-abc'])
            elif parts[0] == 'abc':
                names.append('yosys-abc')
            else:
                raise CaptureError('input_not_captured:tool:engine', f'unsupported engine {parts[0]}')
        if getattr(args, 'replay', None) == 'icarus':
            names += ['iverilog', 'vvp']
        trace = getattr(args, 'trace', None)
        if trace:
            names.append('vcd2fst')
            if str(trace).endswith('.fst'):
                names.append('fst2vcd')
        for name in dict.fromkeys(names):
            self._pin(name)
        if smtbmc_abc:
            raise CaptureError('unsupported_engine:smtbmc:abc',
                               f'smtbmc:abc is unsupported with {self.identities["yosys"]} '
                               f'(yosys-abc sha256={self.raw["yosys-abc"].sha256}); '
                               'the ABC SMT parser can crash. Use smtbmc:yices or abc:bmc3')
        self.env['PATH'] = str(directory) + os.pathsep + self.env.get('PATH', '')

    def _file(self, path):
        # Capture.file has no public executable-without-version API. Keep descriptor
        # identity around its one read, then check the pinned source at publication.
        before = path.stat()
        item = self.capture.file(path)
        if _stamp(before) != _stamp(Path(item.resolved).stat()):
            raise CaptureError(f'input_not_captured:tool:{path}', 'tool changed during capture')
        self.checks.append((item, _stamp(before)))
        return item

    def _pin(self, name, selected=None):
        path = selected or shutil.which(name, path=self.env.get('PATH', ''))
        if path is None:
            raise CaptureError(f'input_not_captured:tool:{name}', 'tool not installed')
        if name in _IDENTITY_ONLY:
            item = self._file(Path(path))
            if not item.executable:
                raise CaptureError(f'input_not_captured:tool:{name}', 'tool is not executable')
            version = f'{name} sha256={item.sha256}'
        else:
            tool = self.capture.tool(path)
            self.identities[name] = (tool.version.strip().splitlines() or [''])[0]
            version = tool.version
            # The copy is read only to recognize the installed oss-cad-suite launcher.
            item = self.capture.file(Path(path))
        self.raw[name] = item
        self.identities.setdefault(name, (version.strip().splitlines() or [''])[0])
        body = 'exec ' + shlex.quote(item.resolved) + ' "$@"\n'
        try:
            text = item.copy.read_text(encoding='utf-8')
        except UnicodeError:
            text = ''
        prefix = next((p for p in (_OSS_PREFIX, _OSS_NATIVE_PREFIX) if text.startswith(p)), None)
        if prefix:
            # The release launchers prepend their own bin directory. Preserve their
            # runtime setup but put the captured command bindings first, including
            # when yosys-smtbmc starts a solver or Yosys starts ABC.
            bindir = Path(item.resolved).parent
            tail = text[len(prefix):]
            if name in ('sby', 'yosys-smtbmc', 'yosys-witness'):
                expected = ('export PYTHONEXECUTABLE="$release_bindir_abs/tabbypy3"\n'
                            f'exec $release_bindir_abs/tabbypy3 "$release_topdir_abs"/libexec/{name} "$@"\n')
                if tail != expected:
                    raise CaptureError(f'input_not_captured:tool:{name}', 'unknown release launcher')
            if name in ('sby', 'yosys-smtbmc', 'yosys-witness'):
                if 'tabbypy3' not in self.commands:
                    self._pin('tabbypy3', str(bindir / 'tabbypy3'))
            # The fixed original directory preserves tool data and runtime lookup.
            body = text.split('\n', 1)[1].replace(
                'release_bindir="$(dirname "${BASH_SOURCE[0]}")"',
                'release_bindir=' + shlex.quote(str(bindir)), 1).replace(
                'export PATH="$release_bindir_abs:$PATH"',
                'export PATH=' + shlex.quote(str(self.directory)) + ':"$release_bindir_abs:$PATH"', 1)
            if name in ('sby', 'yosys-smtbmc', 'yosys-witness'):
                body = body.replace('exec $release_bindir_abs/tabbypy3 ',
                                    'exec ' + shlex.quote(str(self.commands['tabbypy3'].path)) + ' ', 1)
            body = 'exec ' + shlex.quote(self.raw['bash'].resolved) + ' -c ' + shlex.quote(body) + ' -- "$@"\n'
            payload = bindir.parent / 'libexec' / ('python3.11' if name == 'tabbypy3' else name)
            if payload.is_file():
                self._file(payload)
        elif name == 'yosys-smtbmc' and text.startswith('#!') and 'python' not in text.splitlines()[0]:
            raise CaptureError('input_not_captured:tool:yosys-smtbmc',
                               'unsupported launcher; cannot guarantee pinned solver lookup')
        wrapper = self.directory / name
        restore = 'unset ' + ' '.join(self.python_env) + '\n'
        restore += ''.join('export ' + name + '=' + shlex.quote(value) + '\n'
                           for name, value in self.python_env.items() if value is not None)
        wrapper.write_text('#!/bin/sh\nif [ "${1:-}" = --version ]; then\n'
                           + 'printf %s ' + shlex.quote(version) + '\nexit 0\nfi\n'
                           + restore + body)
        wrapper.chmod(0o700)
        self.commands[name] = self.capture.tool(wrapper)

    def command(self, cmd):
        if cmd[0] not in self.commands:
            raise CaptureError(f'input_not_captured:tool:{cmd[0]}', 'command was not selected at start')
        pinned = [str(self.commands[cmd[0]].path)]
        if cmd[0] == 'sby':
            for option, name in (('yosys', 'yosys'), ('smtbmc', 'yosys-smtbmc'),
                                 ('witness', 'yosys-witness'), ('abc', 'yosys-abc'),
                                 ('pono', 'pono'), ('avy', 'avy'), ('btormc', 'btormc')):
                if name in self.commands:
                    pinned += ['--' + option, str(self.commands[name].path)]
        return [*pinned, *cmd[1:]]

    def bindings(self):
        record = self.capture.record()
        files = {item['copy']: item for item in record['files']}
        tools = {item['path']: item for item in record['tools']}
        return {name: {'input': files[item.copy.relative_to(self.capture.root).as_posix()],
                       'command': tools[str(self.commands[name].path)]}
                for name, item in self.raw.items()}

    def verify(self):
        self.capture.verify_tools()
        for item, stamp in self.checks:
            try:
                descriptor = os.open(item.resolved, os.O_RDONLY | os.O_NOFOLLOW)
                with os.fdopen(descriptor, 'rb') as stream:
                    before = os.fstat(stream.fileno())
                    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                    after = os.fstat(stream.fileno())
                if digest != item.sha256 or _stamp(before) != stamp or _stamp(after) != stamp:
                    raise ValueError('tool content or metadata changed')
            except (OSError, ValueError) as exc:
                raise CaptureError(f'input_not_captured:tool:{item.source}', str(exc)) from exc
