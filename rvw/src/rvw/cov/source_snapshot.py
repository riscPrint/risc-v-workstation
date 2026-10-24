"""Freeze the complete supported Verilog input set before running a front end.

Literal includes are redirected into the snapshot. No tool discovers dependencies by
reading live headers. Unsupported preprocessor forms refuse rather than escape the snapshot.
"""
import json
from pathlib import Path
import re

from rvw.common.capture import Capture, CaptureError, sha256_file

from . import captured


TOKENS = re.compile(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"', re.S)
INCLUDE = re.compile(r'`include\b[^\S\n]*("[^"\n]+")?')
FILE_READS = re.compile(r'\$(?:readmem[hb]|fopen|fread|fscanf|fgets|fgetc|sreadmem)\b')


def _includes(text):
    # Keep offsets when removing comments. Strings remain intact, so a directive in
    # a string can cause a conservative refusal but cannot hide a live include.
    masked = TOKENS.sub(lambda m: re.sub(r'[^\n]', ' ', m[0])
                        if m[0].startswith(('//', '/*')) else m[0], text)
    if FILE_READS.search(masked):
        raise CaptureError('input_not_captured:rtl_dependencies',
                           'source snapshot does not support file-reading system tasks')
    if re.search(r'\\\r?\n|``|`__FILE__\b', masked):
        raise CaptureError('input_not_captured:rtl_dependencies',
                           'source snapshot does not support line continuations, token pasting or `__FILE__')
    for match in INCLUDE.finditer(masked):
        if match[1] is None:
            raise CaptureError('input_not_captured:rtl_dependencies',
                               'source snapshot requires literal `include paths (no computed includes)')
        yield match.start(1) + 1, match.end(1) - 1, match[1][1:-1]


def _include_path(name, roots):
    path = Path(name)
    if path.is_absolute():
        return str(path)
    if name in roots:
        return str(roots[name])
    raise CaptureError('input_not_captured:rtl_dependencies',
                       f'source snapshot: relative include {name} must be a listed source basename')


def _rewrite(text, roots, paths):
    edits = [(start, end, paths[_include_path(name, roots)]) for start, end, name in _includes(text)]
    for start, end, value in reversed(edits):
        text = text[:start] + value + text[end:]
    return text


def create(out, sources, harness, check_paths, input_capture=None):
    directory = Path(out) / 'source-snapshot'
    directory.mkdir()
    input_capture = input_capture or Capture(Path(out) / 'input-capture')
    roots = {p.name: p for p in sources}
    entries, by_opened = [], {}

    def capture_source(path):
        opened = str(path)
        if opened in by_opened:
            return
        check_paths([Path(opened)], Path(out))
        item = next((input_capture.file(Path(r['source'])) for r in input_capture.record()['files']
                     if r['resolved'] == opened), None) or input_capture.file(Path(opened))
        record = captured.record(item, opened)
        if opened == item.resolved and opened != item.source:
            record['links'] = []  # Original lookup links remain in the plan's files record.
        content = item.copy.read_bytes()
        index = len(entries)
        target = directory / str(index) / 'rtl' / Path(opened).name
        target.parent.mkdir(parents=True)
        raw = item.copy
        entry = {'opened': opened, 'record': record, 'raw': str(raw), 'path': str(target)}
        entries.append(entry)
        by_opened[opened] = entry
        for _, _, name in _includes(content.decode('utf-8')):
            capture_source(_include_path(name, roots))

    for path in [*sources, harness]:
        capture_source(path)
    paths = {key: value['path'] for key, value in by_opened.items()}
    for entry in entries:
        target = Path(entry['path'])
        target.write_bytes(_rewrite(Path(entry['raw']).read_bytes().decode('utf-8'), roots, paths).encode('utf-8'))
        target.chmod(0o444)
        entry['sha256'] = sha256_file(target)
    listed = {str(p) for p in [*sources, harness]}
    manifest = {'capture_root': str(input_capture.root), 'capture': input_capture.record(),
                'entries': entries, 'sources': [paths[str(p)] for p in sources],
                'harness': paths[str(harness)],
                'dependencies': {e['opened']: e['record'] for e in entries if e['opened'] not in listed}}
    path = directory / 'manifest.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    path.chmod(0o444)
    return {'path': str(path), 'sha256': sha256_file(path)}, manifest


@captured.command
def verify(reference, sources, harness, files, out, stale_record):
    path = Path(out) / 'source-snapshot/manifest.json'
    if reference['path'] != str(path) or captured.sha256(path) != reference['sha256']:
        raise ValueError('source snapshot manifest changed')
    manifest = json.loads(captured.read_text(path))
    entries = manifest['entries']
    paths = {e['opened']: e['path'] for e in entries}
    if len(paths) != len(entries):
        raise ValueError('duplicate source snapshot entries')
    roots = {p.name: p for p in sources}
    if manifest['sources'] != [paths[str(p)] for p in sources] or manifest['harness'] != paths[str(harness)]:
        raise ValueError('source snapshot roots differ from the plan')
    listed = {str(p) for p in [*sources, harness]}
    expected_dependencies = {}
    for index, entry in enumerate(entries):
        opened = entry['opened']
        target = path.parent / str(index) / 'rtl' / Path(opened).name
        raw_records = [r for r in manifest['capture']['files']
                       if str(Path(manifest['capture_root']) / r['copy']) == entry['raw']
                       and r['resolved'] == entry['record']['resolved']
                       and r['sha256'] == entry['record']['sha256']]
        if len(raw_records) != 1:
            raise ValueError('source snapshot has no unique capture record')
        raw = Path(manifest['capture_root']) / raw_records[0]['copy']
        record = entry['record']
        if entry['path'] != str(target) or entry['raw'] != str(raw) or record['opened'] != opened:
            raise ValueError('source snapshot entry paths differ')
        if stale_record(record) or captured.sha256(raw) != record['sha256']:
            raise ValueError(f'source snapshot input changed: {opened}')
        if opened in listed:
            # The plan may use a symlink, while the snapshot root uses its resolved path.
            if not any(r['resolved'] == opened and r['sha256'] == record['sha256'] for r in files.values()):
                raise ValueError(f'source snapshot input was not in the plan: {opened}')
        else:
            expected_dependencies[opened] = record
        expected = _rewrite(captured.read_bytes(raw).decode('utf-8'), roots, paths).encode('utf-8')
        if captured.read_bytes(target) != expected or captured.sha256(target) != entry['sha256']:
            raise ValueError(f'source snapshot contents changed: {target}')
    if manifest['dependencies'] != expected_dependencies:
        raise ValueError('source snapshot dependency records differ')
    return manifest


def input_hashes(manifest, copies):
    """Expected exact frozen files plus the copies read by this front end."""
    result = {e['path']: e['sha256'] for e in manifest['entries']}
    result.update({str(target): expected for target, expected in copies})
    return result


@captured.command
def check_inputs(recorded, expected):
    if recorded != expected:
        raise ValueError('job input hashes differ from the source snapshot')
    for path, sha256 in expected.items():
        if not sha256 or not Path(path).is_file() or Path(path).is_symlink() or captured.sha256(path) != sha256:
            raise ValueError(f'job input differs from the source snapshot: {path}')
