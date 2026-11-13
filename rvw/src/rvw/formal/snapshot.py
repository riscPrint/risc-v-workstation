"""Copy formal inputs before elaboration and record the model used by every later tool."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from rvw.common.capture import Capture, CaptureError

from . import common


# Skip comments and strings before looking for include directives. Macro-computed include
# operands are refused. The frontend's dependency report also checks this conservative scan.
_TOKENS = re.compile(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|`include\b'
                     r'|\$(?:readmem[hb]|fopen|fread|fscanf|fgets|fgetc|sreadmem)\b', re.S)
_OPERAND = re.compile(r'[ \t]*"([^"\r\n\\]+)"')
_FILE_READS = re.compile(r'\$(?:readmem[hb]|fopen|fread|fscanf|fgets|fgetc|sreadmem)\b')


def _has_file_read(text: str) -> bool:
    return any(_FILE_READS.fullmatch(token.group()) for token in _TOKENS.finditer(text))


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class InputSnapshot:
    def __init__(self, args, out: Path):
        self.frontend = getattr(args, "frontend", "verilog")
        self.project_capture = getattr(args, "_project_capture", None)
        self.out = out
        self.directory = out / 'inputs'
        for name in [*args.verilog, args.checks, getattr(args, 'trace', None)]:
            if name and Path(name).resolve().is_relative_to(self.directory):
                common.die('an input is inside --out/inputs; use a different --out')
        common.clear_outputs(out, 'inputs')
        self.directory.mkdir()
        self.capture = Capture(self.directory / 'original')
        self.files: list[dict] = []
        self.artifacts: list[dict] = []
        self.tools = None
        self._copies: dict[Path, Path] = {}
        self._pending: set[Path] = set()
        self.sources = [self._copy(Path(f), 'source') for f in args.verilog]
        if self.frontend == 'temporal':
            from .temporal import lower
            # Bind files and checker declarations can refer to another source.
            # Keep each original captured file and seal the combined proof input.
            combined = self.directory / 'temporal.sv'
            text = '\n'.join(path.read_text() for path in self.sources)
            if getattr(args, 'raw_events', False):
                from .raw_events import rewrite
                text, self.raw_events = rewrite(text, args.top, force=getattr(args, 'raw_events_force', False))
            lowered, self.temporal_properties = lower(text)
            combined.write_text(lowered)
            self.sources = [self.seal(combined)]
        if self.frontend == 'slang':
            from .sva import validate_sources
            if getattr(args, 'event_model', False):
                raise ValueError('slang SVA supports single-clock BMC only')
            if args.engine not in ('smtbmc:yices', 'abc:bmc3'):
                raise ValueError('slang SVA is qualified only for smtbmc:yices and abc:bmc3')
            validate_sources(self.sources, args.clock)
        self.checks = self._copy(Path(args.checks), 'checks') if args.checks else None
        trace = getattr(args, 'trace', None)
        self.trace = self._copy(Path(trace), 'trace') if trace else None

    def _copy(self, original: Path, kind: str) -> Path:
        # Keep the lookup path in the report as well as the resolved target. Once copied,
        # symlink changes in the live tree cannot affect the proof.
        original = original if original.is_absolute() else Path.cwd() / original
        common.check_path('input', original)
        if original in self._pending or len(self._pending) >= 100:
            common.die(f'cyclic include dependency: {original}')
        if original in self._copies:
            return self._copies[original]
        self._pending.add(original)
        number = len(self.files)
        try:
            item = self.capture.file(original)
            raw = item.copy
            front = self.directory / 'frontend' / str(number) / original.name if kind in ('source', 'include') else raw
            front.parent.mkdir(parents=True, exist_ok=True)
            record = {'kind': kind, 'original': item.source, 'resolved': item.resolved,
                      'path': str(raw.relative_to(self.out)), 'sha256': item.sha256,
                      'size': item.size,
                      'symlinks': [{'path': p, 'target': t} for p, t in item.symlinks]}
            self.files.append(record)
            self._copies[original] = front
            if kind in ('source', 'include'):
                text = raw.read_text(encoding='utf-8')
                if _has_file_read(text):
                    common.die(f'{original}: file-reading system tasks are not supported in formal snapshots')
                edits = []
                for token in _TOKENS.finditer(text):
                    if token.group() != '`include':
                        continue
                    operand = _OPERAND.match(text, token.end())
                    if not operand:
                        common.die(f'{original}: cannot determine include files; use literal quoted include paths')
                    name = Path(operand[1])
                    if name.is_absolute():
                        included = name
                    else:
                        # Yosys searches the working directory and the including file's directory.
                        # Do not guess when these two locations contain different files.
                        candidates = [p for p in (original.parent / name, self.out / name) if p.is_file()]
                        targets = {p.resolve() for p in candidates}
                        if len(targets) != 1:
                            common.die(f'{original}: include {str(name)!r} is missing or ambiguous')
                        included = candidates[0]
                    copied = self._copy(included, 'include')
                    edits.append((operand.start(1), operand.end(1), str(copied)))
                for start, end, value in reversed(edits):
                    text = text[:start] + value + text[end:]
                front.write_text(text, encoding='utf-8')
                record.update(frontend=str(front.relative_to(self.out)), frontend_sha256=digest(front))
        except (OSError, UnicodeError, CaptureError) as exc:
            common.die(f'cannot snapshot {original}: {exc}')
        self._pending.remove(original)
        return front

    def check_frontend(self) -> None:
        """No frontend read may escape the copied RTL or introduce an untracked dependency."""
        allowed = {str(self.out / r['frontend']) for r in self.files if 'frontend' in r}
        if self.frontend == 'temporal':
            allowed.add(str(self.directory / 'temporal.sv'))
        script = str(self.out / 'module_ports.ys')
        try:
            if self.frontend == 'slang':
                read = {str((self.out / line).absolute()) if not Path(line).is_absolute() else line
                        for line in (self.out / 'slang.d').read_text().splitlines()}
                if not set(map(str, self.sources)) <= read or read - allowed:
                    raise ValueError('slang read files outside the input snapshot')
                return
            deps = (self.out / 'module_ports.d').read_text().strip()
            left, separator, right = deps.partition(': ')
            expected = {str(self.out / 'module_ports.json'), str(self.out / 'module_ports.il')}
            # Paths have already passed common.check_path: no Make escapes or whitespace.
            if not separator or set(left.split()) != expected:
                raise ValueError('missing or unsupported frontend dependency report')
            read = set(right.split())
            if (not set(map(str, self.sources)) <= read
                    or not read or read - allowed - {script, 'module_ports.ys'}):
                raise ValueError('frontend read files outside the input snapshot')
        except (OSError, ValueError) as exc:
            common.die(f'cannot seal the formal input snapshot: {exc}')

    def seal(self, path: Path) -> Path:
        """Hash an elaboration or generated proof input once before a tool reads it."""
        self.artifacts.append({'path': str(path.relative_to(self.out)), 'sha256': digest(path)})
        return path

    def finish(self, result: dict) -> None:
        problems = []
        if self.tools is not None:
            result['tool_bindings'] = self.tools.bindings()
            try:
                self.tools.verify()
            except CaptureError as exc:
                problems.append(str(exc))
                result['status'] = 'unknown'
                result['cause'] = exc.cause
        if self.frontend == 'temporal':
            result['temporal_properties'] = self.temporal_properties
        result['input_capture'] = self.capture.record()
        if self.project_capture is not None:
            result['project_capture'] = self.project_capture
        result['input_capture']['problems'] = sorted(set(
            result['input_capture']['problems'] +
            ([result['cause']] if 'cause' in result else [])))
        result['input_snapshot'] = {'files': self.files, 'artifacts': self.artifacts,
                                    'problems': problems}
        if problems and result['status'] == 'pass':
            result['status'] = 'unknown'
