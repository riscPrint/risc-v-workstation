"""One capture scope across all reads in a wave command."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from pathlib import Path
import os
import inspect
import shutil

from rvw.common.interpreter import script_interpreter
import tempfile

from rvw.common.capture import Capture, CaptureError, _read_into, _stamp

_current = ContextVar('rvw_wave_capture', default=None)


class WaveInputs:
    """Also pins executables whose CLI has no --version (GTKWave converters)."""
    def __init__(self, capture):
        self.capture = capture
        self.environment = dict(os.environ)
        capture.env('PATH', 'HOME', 'LD_LIBRARY_PATH', 'DYLD_LIBRARY_PATH', 'DYLD_FALLBACK_LIBRARY_PATH')
        self.programs = {}
        self.copies = set()
        self.tool_names = {}

    def file(self, path):
        path = Path(path)
        if path in self.copies or path.is_relative_to(self.capture.root):
            return path
        item = self.capture.file(path)
        self.copies.add(item.copy)
        return item.copy

    def program(self, path):
        key = str(path)
        if key not in self.programs:
            resolved = Path(path).resolve(strict=True)
            stamp = _stamp(resolved.stat())
            item = self.capture.file(Path(path))
            if item.resolved != str(resolved):
                raise CaptureError(f'input_not_captured:tool:{key}', 'executable link changed')
            digest, size, info = _read_into(Path(item.resolved))
            if digest != item.sha256 or size != item.size or stamp != _stamp(info):
                raise CaptureError(f'input_not_captured:tool:{key}', 'executable changed during capture')
            self.programs[key] = (item, stamp)
            with item.copy.open('rb') as stream:
                header = stream.readline(4096)
            if header.startswith(b'#!'):
                interpreter = script_interpreter(header)
                selected = shutil.which(interpreter[0], path=self.environment.get('PATH'))
                if selected is None:
                    raise CaptureError(f'input_not_captured:tool:{key}', 'interpreter not found')
                self.program(selected)
            # oss-cad-suite launchers execute a second file relative to bin/.
            payload = Path(item.resolved).parent.parent / 'libexec' / Path(item.resolved).name
            if payload.is_file():
                self.program(payload)
        return self.programs[key][0].resolved

    def verify(self):
        self.capture.verify_tools()
        for key, (item, stamp) in self.programs.items():
            try:
                digest, size, info = _read_into(Path(item.resolved))
                if digest != item.sha256 or size != item.size or _stamp(info) != stamp:
                    raise ValueError('executable changed')
            except (OSError, ValueError) as exc:
                raise CaptureError(f'input_not_captured:tool:{key}', str(exc)) from exc


@contextmanager
def scope(inputs):
    token = _current.set(inputs)
    try:
        yield inputs
    finally:
        _current.reset(token)


@contextmanager
def wave_input(path):
    active = _current.get()
    if active is not None:
        yield str(active.file(path))
        return
    with tempfile.TemporaryDirectory(prefix='rvw-wave-') as directory:
        inputs = WaveInputs(Capture(Path(directory) / 'inputs'))
        with scope(inputs):
            yield str(inputs.file(path))
            inputs.verify()


def captured(fn):
    parameter = next(iter(inspect.signature(fn).parameters))
    @wraps(fn)
    def call(*args, **kwargs):
        if args:
            path, args = args[0], args[1:]
        else:
            path = kwargs.pop(parameter)
        # Check before replacing the lookup path with a private copy.
        if fn.__name__ in ('cut', '_cut'):
            out = args[0] if args else kwargs.get('out')
            if out and os.path.exists(out) and os.path.samefile(path, out):
                from .vcd import WaveError
                raise WaveError(f'{out} is the input wave; cut to a different file')
        with wave_input(path) as saved:
            result = fn(saved, *args, **kwargs)
            if fn.__name__ == 'info':
                result.path = str(path)
            elif fn.__name__ == '_info':
                result['path'] = str(path)
            return result
    return call
