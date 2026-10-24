"""Capture the complete literal HDL input set before either Yosys session.

Only the supported preprocessor subset is accepted. Include names in private execution
copies point at other private copies. The fingerprint uses the original captured bytes.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import re
import tempfile

from rvw.common.capture import Capture, CaptureError
from rvw.common.proc import run_group

CONTEXT = ('yosys read_verilog -sv; SYNTHESIS defined and undefined; literal includes only; '
           'all literal branches captured; no include directories; empty cwd; '
           'hierarchy -check -top under generics; capture/1')
INCLUDE = re.compile(r'`include([^\r\n]*)')
FILE_READS = re.compile(r'\$(?:readmem[hb]|fopen|fread|fscanf|fgets|fgetc|sreadmem)\b')
FILE_PUSH = re.compile(r'^`file_push "(.*)"$', re.M)


def audit(label, text):
    problems = []
    for m in re.finditer(r'`(?:ifdef|ifndef|elsif)([^\r\n]*)', text):
        if m[1].strip() != 'SYNTHESIS':
            problems.append(f'{label}: conditional define {m[1].strip()} is outside the supported contexts')
    for m in INCLUDE.finditer(text):
        if not re.fullmatch(r'"[^"`\\]+"', m[1].strip()):
            problems.append(f'{label}: a macro-built or unresolved include cannot be scanned')
    if '`undefineall' in text or '`resetall' in text:
        problems.append(f'{label}: a directive resets the preprocessor context')
    for m in re.finditer(r'`(?:define|undef)([^\r\n]*)', text):
        body = m[1].strip()
        name = re.match(r'[\w$]+', body)
        if (name is not None and name[0] == 'SYNTHESIS') or '`' in body or body.endswith('\\'):
            problems.append(f'{label}: a preprocessor context or directive is changed by a macro')
    problems += [f'{op} in {label} reads a file during elaboration; such inputs are not hashed'
                 for op in sorted(set(FILE_READS.findall(text)))]
    return problems


def prepare(request, root, capture):
    """Return only complete evidence. Never read a live HDL path after capture."""
    chunks, nodes, active, problems = [], {}, set(), []
    execution = root / 'execution'
    execution.mkdir()
    cwd = root / 'cwd'
    cwd.mkdir()
    env = os.environ.copy()
    env.update({k: v for k, v in capture.env('PATH', 'SPINALDB_YOSYS').items() if v is not None})
    top = request['top']
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_$]*', top):
        raise ValueError(f'module name {top} cannot be given to Yosys')
    params = request['params']
    for name, value in params:
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_$]*', name) or any(ord(c) < 32 or c in ';#' for c in value):
            raise ValueError('generic cannot be given to Yosys')

    def materialize(label, text, base, identity):
        if identity in active:
            raise ValueError(f'{label}: cyclic include')
        if identity in nodes:
            return nodes[identity]
        if len(nodes) >= 10000:
            raise ValueError('HDL input entry limit exceeded')
        active.add(identity)
        dest = execution / f'{len(nodes)}.v'
        nodes[identity] = dest
        problems.extend(audit(label, text))
        if problems:
            raise ValueError('; '.join(problems))

        def include(m):
            name = m[1].strip()[1:-1]
            p = Path(name)
            if not p.is_absolute():
                p = base / p
            target = file_input(f'include {name}', p)
            return f'`include "{target}"'

        transformed = INCLUDE.sub(include, text)
        dest.write_text(transformed, encoding='utf-8')
        dest.chmod(0o400)
        active.remove(identity)
        return dest

    def file_input(label, path):
        # Capture memoizes the lookup path. Resolve symlinks once, including nested includes.
        item = capture.file(path)
        identity = item.source
        if identity in active:
            raise ValueError(f'{label}: cyclic include')
        if identity in nodes:
            return nodes[identity]
        data = item.copy.read_bytes()
        if sum(len(b) for _, b in chunks) + len(data) > 256 * 1024 * 1024:
            raise ValueError('HDL input byte limit exceeded')
        chunks.append((label, data))
        return materialize(label, data.decode('utf-8'), Path(item.source).parent, identity)

    roots = []
    for label, path in request['files']:
        if Path(path).suffix.lower() in ('.vhd', '.vhdl'):
            raise ValueError(f'{label} is VHDL: its dependencies cannot be listed')
        roots.append(file_input(label, Path(path)))
    for i, (language, text) in enumerate(request['inline']):
        if language != 'verilog':
            raise ValueError('an inline VHDL body cannot be scanned for its dependencies')
        chunks.append(('inline verilog', text.encode('utf-8')))
        # An inline include has no source file directory. Only absolute includes are supported.
        for m in INCLUDE.finditer(text):
            if not Path(m[1].strip().strip('"')).is_absolute():
                raise ValueError('inline HDL has a relative include without a source directory')
        roots.append(materialize('inline verilog', text, cwd, f'inline:{i}'))
    return roots, chunks, nodes, cwd, env


def run_prepared(request, root, prepared, solver):
    roots, chunks, nodes, cwd, env = prepared
    top, params = request['top'], request['params']
    if any(c.isspace() or c in '\";#' for c in str(root)):
        raise ValueError('private input path cannot be given to Yosys')
    for no_synthesis in (False, True):
        script = root / f'deps-{no_synthesis}.ys'
        commands = []
        for i, path in enumerate(roots):
            pp = root / f'pp-{no_synthesis}-{i}.txt'
            commands.append(f'tee -q -o {pp} read_verilog -sv ' +
                            ('-nosynthesis ' if no_synthesis else '') + f'-ppdump {path}')
        if params:
            commands.append('chparam ' + ' '.join(f'-set {n} {v}' for n, v in params) + f' {top}')
        commands.append(f'hierarchy -check -top {top}')
        script.write_text('\n'.join(commands) + '\n')
        result = run_group([str(solver.path), '-q', '-s', str(script)], cwd=cwd, env=env,
                           capture=True, timeout=request.get('timeout', 120))
        if result.returncode:
            raise ValueError(f'yosys could not read the body (exit {result.returncode}): ' +
                             ' | '.join((result.stdout + result.stderr).splitlines()[-2:]))
        allowed = {str(p) for p in nodes.values()}
        for i, path in enumerate(roots):
            pp = (root / f'pp-{no_synthesis}-{i}.txt').read_text()
            pushed = FILE_PUSH.findall(pp)
            if str(path) not in pushed or any(p not in allowed for p in pushed):
                raise ValueError('the preprocessor opened an input outside the capture')
            if FILE_READS.search(pp):
                raise ValueError('preprocessor output reads a file during elaboration')
        chunks.append(('context', (CONTEXT + f'; nosynthesis={no_synthesis}; generics=' +
                                   json.dumps(params, separators=(',', ':'))).encode()))
    return {'chunks': [[label, base64.b64encode(data).decode()] for label, data in chunks],
            'problems': []}


def capture_batch(requests, root, extra=(), source_roots=(), optional_source_roots=()):
    capture = Capture(root / 'inputs')
    file_result = {'chunks': [], 'problems': []}
    for path in extra:
        try:
            item = capture.file(Path(path))
            file_result['chunks'].append([item.source, base64.b64encode(item.copy.read_bytes()).decode()])
        except CaptureError as exc:
            file_result['problems'].append(str(exc))
    optional_roots = []
    roots = list(source_roots)
    for source_root in optional_source_roots:
        path = Path(source_root).absolute()
        try:
            # A dangling symlink is an input failure, not an absent default directory.
            path.lstat()
        except FileNotFoundError:
            optional_roots.append({'source': str(path), 'state': 'absent'})
        except OSError as exc:
            file_result['problems'].append(f'input_not_captured:source_root: {exc}')
        else:
            optional_roots.append({'source': str(path), 'state': 'present'})
            roots.append(path)
    for source_root in roots:
        try:
            capture.tree(Path(source_root), git=False)
        except CaptureError as exc:
            file_result['problems'].append(str(exc))
    prepared = []
    results = []
    for i, request in enumerate(requests):
        private = root / str(i)
        private.mkdir()
        try:
            prepared.append((private, prepare(request, private, capture)))
            results.append(None)
        except (CaptureError, OSError, ValueError, UnicodeError, RecursionError) as exc:
            prepared.append(None)
            results.append({'chunks': [], 'problems': [f'input_not_captured:hdl: {exc}']})
    # Capture all roots and includes of all bodies before the first solver read.
    try:
        env = capture.env('SPINALDB_YOSYS')
        solver = capture.tool(next((r['yosys'] for r in requests if r.get('yosys')), None) or
                              env['SPINALDB_YOSYS'] or 'yosys') if any(prepared) else None
        for i, item in enumerate(prepared):
            if item is not None:
                try:
                    results[i] = run_prepared(requests[i], *item, solver)
                except (OSError, ValueError) as exc:
                    results[i] = {'chunks': [], 'problems': [f'input_not_captured:hdl: {exc}']}
        capture.verify_tools()
    except (CaptureError, OSError, ValueError) as exc:
        results = [{'chunks': [], 'problems': [f'input_not_captured:hdl: {exc}']} for _ in requests]
    record = capture.record()
    # Capture.tree traverses the pinned resolved root. Its member records can therefore
    # use resolved paths. Keep logical navigation aliases from the captured layout too.
    # This projection uses no live path resolution or file reads.
    bindings = {item['source']: item for item in record['files']}
    for tree in record['trees']:
        for item in tree['files']:
            relative = Path(item['copy']).relative_to(tree['copy'])
            logical = str(Path(tree['source']) / relative)
            links = {link['path']: link['target'] for link in (*tree['symlinks'], *item['symlinks'])}
            alias = {**item, 'source': logical,
                     'symlinks': [{'path': p, 'target': t} for p, t in sorted(links.items())]}
            previous = bindings.get(logical)
            if previous is not None:
                if (previous['resolved'], previous['sha256']) != (alias['resolved'], alias['sha256']):
                    record['problems'].append(f'input_not_captured:source_alias: {logical} has conflicting bindings')
            else:
                bindings[logical] = alias
    record['files'] = [bindings[path] for path in sorted(bindings)]
    record['optional_source_roots'] = optional_roots
    # File-level errors must invalidate the record too, including an optional root
    # whose existence cannot be checked. Diff validates this record, not warnings.
    record['problems'] = list(dict.fromkeys(record['problems'] + file_result['problems']))
    if record['problems'] or file_result['problems']:
        cause = 'input_not_captured:batch: ' + '; '.join(record['problems'] + file_result['problems'])
        results = [{'chunks': [], 'problems': [cause]} for _ in requests]
    for result in results:
        result['capture'] = record
    file_result['capture'] = record
    return {'results': results, 'files': file_result}


def execute(request):
    try:
        with tempfile.TemporaryDirectory(prefix='spinaldb-hdl-') as private:
            return capture_batch(request['requests'], Path(private), request.get('files', []),
                                 request.get('source_roots', []), request.get('optional_source_roots', []))
    except (CaptureError, OSError, ValueError, UnicodeError, RecursionError) as exc:
        return {'chunks': [], 'problems': [f'input_not_captured:hdl: {exc}']}
