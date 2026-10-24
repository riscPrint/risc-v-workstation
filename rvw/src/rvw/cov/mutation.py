"""MCY orchestration and read-only structured reporting of its SQLite database."""
import json
import os
from pathlib import Path
import re
import shlex
import sqlite3
import sys
from hashlib import sha256

from rvw.results.generation import publish, open_current
from rvw.common.capture import CaptureError, sha256_file
from . import captured

from .proof import run_job


DEPENDENCY_LIMIT = ('MCY test scripts can read transitive files, tools and other external inputs; '
                    'their complete dependency identity cannot be determined')
DECLARATION = 'rvw-external-inputs'
_UNSET = object()


def _dependencies(capture, tree, project):
    """Read the user's completeness claim from the captured project only."""
    root = Path(tree.resolved)
    entries = [(root / item.copy.relative_to(tree.copy), item) for item in tree.files]
    roots = [(root, root)]
    if root != project:
        roots.append((project, root))
    manifest = next((item for path, item in entries if path == root / DECLARATION), None)
    if manifest is None:
        print(f'cov mutate: external inputs are unknown. Create {project / DECLARATION} '
              'as a JSON list of all external input paths, relative to the project or absolute. '
              'Write [] to declare no external inputs. This declares completeness by the user.', file=sys.stderr)
        return None, entries, roots
    try:
        paths = json.loads(manifest.copy.read_bytes())
        if not isinstance(paths, list) or any(not isinstance(p, str) or not p for p in paths):
            raise ValueError('expected a JSON list of nonempty paths; [] declares no external inputs')
    except (ValueError, UnicodeError) as exc:
        raise CaptureError('input_not_captured:mcy_declaration', str(exc)) from exc
    records = []
    for path in paths:
        # Leading ../ is safe from the captured resolved root. A later .. can cross a
        # symlink inside the declared spelling; do not silently change that lookup.
        seen_name = False
        for part in Path(path).parts:
            if part == '..' and seen_name:
                raise CaptureError('input_not_captured:mcy_declaration', f'non-leading .. is unsupported: {path}')
            if part != '..':
                seen_name = True
        lookup = Path(os.path.abspath(root / path))
        if any(lookup.is_relative_to(root) or root.is_relative_to(lookup) for root, _ in roots):
            raise CaptureError('input_not_captured:mcy_declaration', f'overlapping input: {path}')
        item = capture.tree(lookup, git=False) if lookup.is_dir() else capture.file(lookup)
        resolved = Path(item.resolved)
        if any(resolved.is_relative_to(root) or root.is_relative_to(resolved) for root, _ in roots):
            raise CaptureError('input_not_captured:mcy_declaration', f'overlapping resolved input: {path}')
        roots.append((lookup, lookup))
        # Absolute references through a declared symlink's resolved name also use its copy.
        if resolved != lookup:
            roots.append((resolved, lookup))
        if hasattr(item, 'files'):
            entries.extend((lookup / f.copy.relative_to(item.copy), f) for f in item.files)
        else:
            entries.append((lookup, item))
        records.append({'path': str(lookup), 'resolved': item.resolved, 'sha256': item.sha256})
    return {'claim': 'declared complete by the user', 'paths': paths,
            'manifest': captured.record(manifest), 'inputs': records}, entries, roots


# This is a cheap literal-path check, not a shell/HDL parser or a sandbox.
_ABSOLUTE = re.compile(r'(?:(?<![A-Za-z0-9_$}./])|(?<=-I)|(?<=-L)|(?<=-f)|(?<=-o))/(?:[A-Za-z0-9_.+~-]+/?)+')
_HDL_STRINGS = re.compile(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"', re.DOTALL)
_SHELL_ARGUMENT = re.compile(r'''[ \t]+((?:'[^']*'|"(?:\\.|[^"\\])*"|\\.|[^\s;&|()<>'"\\])+)''')
_SHELL_COMMAND = re.compile(r'(?:^|[;&|(\n])[ \t]*(?:(?:if|then|do|!|command|exec)[ \t]+)*'
                            r'([A-Za-z0-9_./+~-]+)(?=[\s;&|()<>]|$)')
_OUTPUT_COMPILER = re.compile(r'(?:[A-Za-z0-9_]+-)*(?:gcc|g\+\+|cc|c\+\+|clang|clang\+\+|ld)(?:-\d+)?$')


def _shell_syntax(text):
    """Mask literal strings and comments, but retain $(...) command bodies."""
    scan = list(text)

    def mask(start, end):
        scan[start:end] = ' ' * (end - start)

    def code(index, nested=False):
        while index < len(text):
            char = text[index]
            if char == ')' and nested:
                return index + 1
            if char == '(':
                index = code(index + 1, True)
            elif char == '\\':
                mask(index, min(index + 2, len(text)))
                index += 2
            elif char in ("'", '`'):
                end = text.find(char, index + 1)
                end = len(text) if end < 0 else end + 1
                mask(index, end)
                index = end
            elif char == '"':
                mask(index, index + 1)
                index += 1
                while index < len(text) and text[index] != '"':
                    if text.startswith('$(', index):
                        index = code(index + 2, True)
                    else:
                        end = min(index + (2 if text[index] == '\\' else 1), len(text))
                        mask(index, end)
                        index = end
                if index < len(text):
                    mask(index, index + 1)
                    index += 1
            elif char == '#' and (not index or text[index - 1] in ' \t\n;&|()'):
                end = text.find('\n', index)
                end = len(text) if end < 0 else end
                mask(index, end)
                index = end
            else:
                index += 1
        return index

    code(0)
    return ''.join(scan)


def _shell_output_paths(text):
    """Find literal output destinations for known producers, in source order.

    Only later uses of a generated path can use its scratch copy. Append and read/write
    redirects do not establish an output: their initial contents remain an input.
    """
    outputs = {}

    def word(raw):
        if not re.fullmatch(r"'[^']*'", raw) and re.search(r'[$`]', raw):
            return None
        try:
            values = shlex.split(raw)
            return values[0] if len(values) == 1 else None
        except ValueError:
            return None

    def output(value, position):
        if value and value.startswith('/'):
            path = Path(os.path.normpath(value))
            outputs[path] = min(position, outputs.get(path, position))

    syntax = _shell_syntax(text)
    for command in _SHELL_COMMAND.finditer(syntax):
        name = Path(command[1]).name
        mktemp = name == 'mktemp'
        compiler = name in ('iverilog', 'yosys', 'verilator') or bool(_OUTPUT_COMPILER.fullmatch(name))
        if not mktemp and not compiler:
            continue
        position, pending, options = command.end(), None, True
        while argument := _SHELL_ARGUMENT.match(text, position):
            position = argument.end()
            value = word(argument[1])
            if value is None:
                break
            if pending:
                if pending == 'output':
                    output(value, argument.start(1))
                pending = None
            elif options and value == '--':
                options = False
            elif compiler and options and value in ('-o', '--output'):
                pending = 'output'
            elif compiler and options and value.startswith(('-o', '--output=')):
                output(value[2:] if value.startswith('-o') else value.partition('=')[2], argument.start(1))
            elif mktemp and value.startswith('-') and options:
                if value not in ('--directory', '--quiet', '--dry-run') and not re.fullmatch(r'-[dqu]+', value):
                    # Directory and prefix options need separate argument rules.
                    break
            elif mktemp:
                output(value, argument.start(1))

    # The word must immediately follow a truncating redirect. Do not match >>, <>,
    # descriptor duplication, process substitution or a redirect inside a quoted word.
    # Mask quoted strings and comments while locating the operator; parse its word
    # from the original text so quoted literal destinations still work.
    for match in re.finditer(r'(?<![<>])>(?![>&])\|?', syntax):
        argument = _SHELL_ARGUMENT.match(' ' + text[match.end():])
        if argument:
            output(word(argument[1]), match.end())
    return outputs


def _shell_data_spans(text):
    """Locate literal sed/grep expressions by argument role, including inside $(...).

    This only exempts known data syntax. File operands, -f scripts, redirections,
    and sed r/w filenames still pass through the literal-path guard.
    """
    spans = []

    def expression(raw, start, sed):
        # A substituted pattern can read inputs. Only a single-quoted word is
        # guaranteed literal when it contains shell substitution syntax.
        if not re.fullmatch(r"'[^']*'", raw) and re.search(r'(?<!\\)(?:\$\(|`)', raw):
            return
        if raw.startswith(('"', "'")) and raw[-1:] == raw[:1]:
            raw, start = raw[1:-1], start + 1
        if not sed:
            spans.append((start, start + len(raw)))
            return
        # Slash-delimited address regexes are data. The command after the closing
        # slash can read a file, so do not exempt the whole sed program.
        for match in re.finditer(r'(?:^|[,;{}\n])\s*(/(?:\\.|[^/\\])*/)', raw):
            spans.append((start + match.start(1), start + match.end(1)))
            attached = re.match(r'\s*([rRwW])(?=/)', raw[match.end(1):])
            if attached:
                offset = start + match.end(1)
                spans.append((offset + attached.start(1), offset + attached.end(1)))
        for match in re.finditer(r'(?:^|[;{}\n])\s*([rRwW])(?=/)', raw):
            spans.append((start + match.start(1), start + match.end(1)))
        for match in re.finditer(r'(?:^|[;{}\n])\s*s([^A-Za-z0-9\\\s])', raw):
            delimiter = match[1]
            index, remaining = match.end(), 2
            while index < len(raw) and remaining:
                if raw[index] == '\\':
                    index += 2
                    continue
                if raw[index] == delimiter:
                    remaining -= 1
                index += 1
            if not remaining:
                spans.append((start + match.start(1), start + index))
                attached = re.match(r'[0-9gp]*w(?=/)', raw[index:])
                if attached:
                    spans.append((start + index, start + index + attached.end()))

    for command in re.finditer(r'(?:^|[;&|(\n])[ \t]*(?:(?:if|then|do|!|command|exec)[ \t]+)*'
                               r'(sed|grep|egrep|fgrep)\b', text):
        sed = command[1] == 'sed'
        position, selected, pending = command.end(), False, None
        while argument := _SHELL_ARGUMENT.match(text, position):
            position = argument.end()
            raw, start = argument[1], argument.start(1)
            try:
                values = shlex.split(raw)
            except ValueError:
                break
            if len(values) != 1:
                break
            value = values[0]
            if pending:
                if pending == 'expression':
                    expression(raw, start, sed)
                    selected = True
                pending = None
            elif value in ('-e', '--expression' if sed else '--regexp'):
                pending = 'expression'
            elif value in ('-f', '--file') or (not sed and value in ('-A', '-B', '-C', '-m')):
                pending = 'file'
                if value in ('-f', '--file'):
                    selected = True
            elif value.startswith(('--expression=' if sed else '--regexp=', '-e')):
                prefix = raw.index('=') + 1 if raw.startswith('--') else 2
                expression(raw[prefix:], start + prefix, sed)
                selected = True
            elif value.startswith(('-f', '--file=')):
                selected = True
            elif value.startswith('-') and value != '-':
                continue
            elif not selected:
                expression(raw, start, sed)
                selected = True
    return spans


def _execution_bytes(item, roots, workspace, complete, tools):
    raw = item.copy.read_bytes()
    if Path(item.source).name == DECLARATION or b'\0' in raw:
        return raw
    try:
        text = raw.decode('utf-8')
    except UnicodeError:
        return raw
    shell = (Path(item.source).suffix.lower() in ('.sh', '.bash')
             or bool(re.match(r'#![^\n]*\b(?:ba|da|z|k)?sh\b', text)))
    data_spans = _shell_data_spans(text) if shell else []
    outputs = _shell_output_paths(text) if shell else {}

    def relocate(match):
        literal = match.group()
        path = Path(os.path.normpath(literal))
        for source, target in sorted(roots, key=lambda pair: len(str(pair[0])), reverse=True):
            if path.is_relative_to(source):
                return str(workspace / (target / path.relative_to(source)).relative_to('/'))
        # Device streams and interpreter shebangs belong to the installed runtime.
        shebang = text.startswith('#!') and match.start() < text.find('\n')
        if (path in (Path('/dev/null'), Path('/dev/stdin'), Path('/dev/stdout'), Path('/dev/stderr'))
                or shebang or any(path == tool.path for tool in tools.values())):
            return literal
        if path in outputs and match.start() >= outputs[path]:
            scratch = workspace.parent / 'scratch' / path.relative_to('/')
            scratch.parent.mkdir(parents=True, exist_ok=True)
            return str(scratch)
        if complete:
            raise CaptureError('input_not_captured:mcy_dependencies',
                               f'undeclared absolute path {literal} in {item.source}; add its input to {DECLARATION}')
        return literal

    if Path(item.source).suffix.lower() in ('.v', '.sv', '.vh', '.svh'):
        # HDL paths, including `include and $readmemh/$readmemb arguments, are
        # string literals. A slash in an expression is division or a comment.
        def hdl_literal(match):
            token = match.group()
            return _ABSOLUTE.sub(relocate, token) if token.startswith('"') else token
        text = _HDL_STRINGS.sub(hdl_literal, text)
    else:
        # Mask known data and command syntax for scanning only. Keep the original
        # bytes in the execution script. A sed address must not hide an attached
        # r/w filename in the same slash-led token.
        scan = list(text)
        for start, end in data_spans:
            scan[start:end] = ' ' * (end - start)
        parts, previous = [], 0
        for match in _ABSOLUTE.finditer(''.join(scan)):
            parts.extend((text[previous:match.start()], relocate(match)))
            previous = match.end()
        text = ''.join([*parts, text[previous:]])
    return text.encode('utf-8')


def _fresh_project(project):
    for name in ('database', 'rvw-results', 'rvw-mcy-inputs.json', 'rvw-mcy-config.sha256'):
        path = project / name
        if path.exists() or path.is_symlink():
            raise ValueError(f'{DEPENDENCY_LIMIT}; use a fresh project to run, '
                             'or omit --run to inspect historical results read-only')


def _stage_failure(stage, rc, log):
    # Failed generation staging is deleted. Retain bounded evidence in the error.
    try:
        with log.open('rb') as stream:
            stream.seek(0, os.SEEK_END)
            stream.seek(max(0, stream.tell() - 4096))
            tail = stream.read(4096).decode('utf-8', errors='replace')
    except OSError:
        tail = '[log unavailable]'
    return ValueError(f'{stage} failed ({rc}); {log.name} tail (up to 4096 bytes):\n{tail}')


def _control_failures(result, detection_tests, equivalence_tests):
    controls = [row for row in result['mutants'] if row['mutation'].strip() == 'mutate -mode none']
    required = set(equivalence_tests)
    required.update(detection_tests if detection_tests is not None else
                    (test for row in result['mutants'] for test in (*row['tests'], *row['pending'])))
    failures = []
    if not controls:
        return [{'test': test, 'result': 'missing-control'} for test in sorted(required or {'*'})]
    for test in sorted(required):
        observations = [row for row in controls if test in row['tests'] or test in row['pending']]
        if not observations:
            failures.append({'test': test, 'result': 'missing-result'})
    for row in controls:
        for test in sorted(set(row['tests']) | set(row['pending'])):
            state = 'pending' if test in row['pending'] else row['tests'][test]
            if state != 'PASS':
                failures.append({'id': row['id'], 'test': test, 'result': state})
        if not row['tests'] and not row['pending']:
            failures.append({'id': row['id'], 'test': '*', 'result': 'missing-result'})
    return failures


def _classify(result, detection_tests, equivalence_tests, incomplete=False):
    failures = _control_failures(result, detection_tests, equivalence_tests)
    result['control_failures'] = failures
    if failures:
        incomplete = True
        failed = any(f['result'] not in ('missing-control', 'missing-result') for f in failures)
        if result.get('cause') not in ('mcy_run_failed', 'input_not_captured:mcy_dependencies',
                                       'input_not_captured:mcy_test_roles'):
            result.update(cause='mcy_control_failed' if failed else 'mcy_control_missing',
                          reason='Required unmutated MCY controls did not all pass')
    for row in result['mutants']:
        results = row['tests']
        observed = {k: v for k, v in results.items()
                    if k not in equivalence_tests and (detection_tests is None or k in detection_tests)}
        missing = set(detection_tests or ()) - observed.keys()
        state = ('pending' if row['pending'] or not observed or missing else
                 'error' if any(r not in ('PASS', 'FAIL') for r in results.values()) else
                 'killed' if 'FAIL' in observed.values() else
                 'equivalent' if any(results.get(t) == 'PASS' for t in equivalence_tests) else 'survived')
        if row['mutation'].strip() == 'mutate -mode none' and state not in ('pending', 'error'):
            state = 'control' if all(r == 'PASS' for r in results.values()) else 'error'
        if 'FAIL' in observed.values() and any(results.get(t) == 'PASS' for t in equivalence_tests):
            state = 'error'
        row['state'] = state
        if incomplete:
            row['observed_state'] = state
            if state not in ('pending', 'error'):
                row['state'] = 'inconclusive'
    states = ('killed', 'survived', 'equivalent', 'control', 'pending', 'error')
    if incomplete:
        result['observed_counts'] = {s: sum(r['observed_state'] == s for r in result['mutants']) for s in states}
        states += ('inconclusive',)
        result.update(status='inconclusive', cache_key=None)
        result.setdefault('cause', 'input_not_captured:mcy_dependencies')
        result.setdefault('dependency_complete', False)
        result.setdefault('reason', DEPENDENCY_LIMIT)
    result['counts'] = {s: sum(r['state'] == s for r in result['mutants']) for s in states}
    result['survivors'] = [r for r in result['mutants'] if r['state'] == 'survived']
    result['detection_tests'] = None if detection_tests is None else list(detection_tests)
    result['equivalence_tests'] = list(equivalence_tests)
    return result


@captured.command
def mutation_report(project, detection_tests=_UNSET, equivalence_tests=_UNSET):
    project = Path(project).absolute()
    if (project / 'rvw-results/current').is_file():
        generation = open_current(project / 'rvw-results')
        result = json.loads(generation.read_bytes('result.json'))
        result['generation'] = generation.id
    else:
        result = _read_database(project)
    saved_detection = result.get('detection_tests', _UNSET)
    saved_equivalence = result.get('equivalence_tests', _UNSET)

    def names(value):
        return isinstance(value, list) and all(isinstance(t, str) and t for t in value)

    roles_recorded = ((saved_detection is None or (names(saved_detection) and saved_detection))
                      and names(saved_equivalence))
    if detection_tests is _UNSET:
        detection_tests = saved_detection if roles_recorded else None
    if equivalence_tests is _UNSET:
        equivalence_tests = saved_equivalence if roles_recorded else ()
    complete = result.get('schema') == 'rvw.mutation/2' and result.get('dependency_complete') is True
    if not complete:
        result.update(dependency_complete=False, cause='input_not_captured:mcy_dependencies',
                      reason=DEPENDENCY_LIMIT,
                      evidence='historical-observations; dependency completeness is unverified')
    elif not roles_recorded:
        result.update(cause='input_not_captured:mcy_test_roles',
                      reason='Saved campaign has no complete detection and equivalence test roles')
    return _classify(result, detection_tests, equivalence_tests,
                     incomplete=not complete or not roles_recorded or result.get('status') == 'inconclusive')


def _read_database(project):
    """Read raw outcomes. Only the fresh-run caller can supply dependency evidence."""
    dbpath = project / 'database/db.sqlite3'
    # A live WAL database has inputs outside the main file; refuse a partial capture.
    if any(Path(str(dbpath) + suffix).exists() for suffix in ('-wal', '-journal')):
        raise CaptureError('input_not_captured:mcy_database', 'stop the MCY writer and checkpoint SQLite first')
    config = captured.file(project / 'config.mcy')
    database = captured.file(dbpath)
    db = sqlite3.connect(database.copy.as_uri() + '?mode=ro&immutable=1', uri=True)
    try:
        rows = []
        for mid, mutation in db.execute('SELECT mutation_id, mutation FROM mutations ORDER BY mutation_id'):
            tags = [r[0] for r in db.execute('SELECT tag FROM tags WHERE mutation_id=? ORDER BY tag', (mid,))]
            results = dict(db.execute('SELECT test, result FROM results WHERE mutation_id=? ORDER BY test', (mid,)))
            pending = list(db.execute('SELECT test, running FROM queue WHERE mutation_id=?', (mid,)))
            rows.append({"id": mid, "mutation": mutation, "tags": tags, "tests": results,
                         "pending": [t for t, _ in pending]})
    finally:
        db.close()
    return {"schema": "rvw.mutation/1", "project": str(project), "config_sha256": config.sha256, "database_sha256": database.sha256,
            "evidence": "historical-observations; dependency completeness is unverified",
            "mutants": rows,
            "note": "Survivors include equivalent mutations unless the MCY project also runs equivalence checks."}


@captured.command
def mutate(project, run=False, timeout=120, jobs=1, baseline=None,
           detection_tests=_UNSET, equivalence_tests=_UNSET):
    project = Path(project).absolute()
    if jobs < 1 or jobs > 4:
        raise ValueError('--jobs must be between 1 and 4')
    config = project / 'config.mcy'
    if not config.is_file():
        raise CaptureError('input_not_captured:mcy_config',
                           f'{project}: missing config.mcy; select module, tests, size and seed there')
    if run:
        detection_tests = None if detection_tests is _UNSET else detection_tests
        equivalence_tests = () if equivalence_tests is _UNSET else equivalence_tests
        if detection_tests is not None and not detection_tests:
            raise ValueError('select at least one detection test, or use None for all non-equivalence tests')
        if baseline is None:
            raise ValueError('--run requires --baseline SCRIPT to verify the unmutated test suite first')
        _fresh_project(project)
        # Freeze the whole declared project, including testbench headers and scripts,
        # before baseline validation. Arbitrary scripts can still read external inputs.
        capture = captured.current()
        tree = capture.tree(project, git=False)
        declaration, entries, roots = _dependencies(capture, tree, project)
        complete = declaration is not None
        try:
            relative_baseline = Path(baseline).absolute().relative_to(project)
        except ValueError as exc:
            raise CaptureError('input_not_captured:baseline', 'baseline must be inside the MCY project') from exc
        baseline_item = next((item for item in tree.files
                              if item.copy.relative_to(tree.copy) == relative_baseline), None)
        if baseline_item is None:
            raise CaptureError('input_not_captured:baseline', 'baseline is not in the captured project')
        tools = {name: captured.tool(name) for name in ('bash', 'mcy', 'yosys')}
        captured.environment()
        inputs = {'complete': complete, 'reason': declaration['claim'] if complete else DEPENDENCY_LIMIT,
                  'dependency_declaration': declaration,
                  'config': captured.record(next(item for item in tree.files
                                                if item.copy.relative_to(tree.copy) == Path('config.mcy'))),
                  'baseline': captured.record(baseline_item),
                  'tools': {name: {'executable': str(tool.path), 'sha256': tool.sha256, 'version': tool.version}
                            for name, tool in tools.items()},
                  'capture': capture.record(), 'cache_key': None}
        audit = project / 'rvw-mcy-inputs.json'
        with audit.open('x') as stream:
            json.dump(inputs, stream, indent=2)
        result = None

        def build(directory):
            nonlocal result
            workspace = directory / 'workspace'
            work = workspace / Path(tree.resolved).relative_to('/')
            work.mkdir(parents=True)
            expected = {}
            for source, item in entries:
                target = workspace / source.relative_to('/')
                target.parent.mkdir(parents=True, exist_ok=True)
                content = _execution_bytes(item, roots, workspace, complete, tools)
                target.write_bytes(content)
                target.chmod(0o600 | item.executable)
                expected[target] = sha256(content).hexdigest()
            # Preserve empty directories too. Relative ../ reads use the mirrored layout.
            for name in tree.directories:
                (work / name).mkdir(parents=True, exist_ok=True)
            for source, _ in roots[1:]:
                for external in capture.record()['trees']:
                    if external['source'] == str(source):
                        (workspace / source.relative_to('/')).mkdir(parents=True, exist_ok=True)
                        for name in external['directories']:
                            (workspace / source.relative_to('/') / name).mkdir(parents=True, exist_ok=True)
            # Copies used by tools may be writable. Verify each original input after each
            # stage. This never reopens the live project and cannot authorize reuse.
            def check_inputs():
                for path, expected_hash in expected.items():
                    if sha256_file(path) != expected_hash:
                        raise CaptureError('input_not_captured:mcy_project', f'execution changed input {path.relative_to(workspace)}')

            rc = run_job([str(tools['bash'].path), str(work / relative_baseline)], work,
                         directory / 'baseline.log', timeout)
            if rc:
                raise _stage_failure('unmutated baseline', rc, directory / 'baseline.log')
            check_inputs()
            if (work / 'database').exists():
                raise ValueError('baseline created an MCY database; use a fresh project')
            rc = run_job([str(tools['mcy'].path), 'init'], work, directory / 'init.log', timeout)
            if rc:
                raise _stage_failure('mcy init', rc, directory / 'init.log')
            check_inputs()
            dbpath = work / 'database/db.sqlite3'
            with sqlite3.connect(dbpath.as_uri() + '?mode=ro', uri=True) as db:
                for filename, original in db.execute('SELECT filename, data FROM files'):
                    relative = Path(filename)
                    path = Path(os.path.abspath(work / relative))
                    if path not in expected or expected[path] != sha256(original).hexdigest():
                        raise CaptureError('input_not_captured:mcy_files', f'uncaptured MCY source: {filename}')
            rc = run_job([str(tools['mcy'].path), 'run', '-j', str(jobs)], work, directory / 'run.log', timeout)
            check_inputs()
            captured.verify_tools()
            result = _read_database(work)
            result.update(dependency_complete=complete, dependency_declaration=declaration,
                          cache_key=None, project=str(project), run_exit_code=rc,
                          config_sha256=inputs['config']['sha256'],
                          baseline={'script': baseline_item.resolved, 'sha256': baseline_item.sha256, 'exit_code': 0},
                          tools=inputs['tools'], capture=capture.record())
            if complete:
                # _dependencies captured the declaration and every declared input. Check
                # command linkage before the /2 writer can classify this fresh campaign.
                evidence = result['capture']
                identities = {(tool['path'], tool['sha256']) for tool in evidence['tools']}
                if evidence['problems'] or any((tool['executable'], tool['sha256']) not in identities
                                               for tool in result['tools'].values()):
                    raise CaptureError('input_not_captured:mcy_dependencies', 'incomplete fresh-run tool evidence')
                result['schema'] = 'rvw.mutation/2'
            if rc:
                result.update(status='inconclusive', cause='mcy_run_failed', reason=f'mcy run exited {rc}')
            elif complete:
                result.update(status='complete', evidence=declaration['claim'])
            _classify(result, detection_tests, equivalence_tests, incomplete=not complete or bool(rc))
            # Record the deterministic relocation separately from the raw capture identity.
            result['execution_inputs'] = {str(path.relative_to(workspace)): expected_hash
                                          for path, expected_hash in expected.items()}
            result['replay'] = ['rvw', 'cov', 'mutate', str(project), '--run', '--baseline', baseline_item.source,
                                '--jobs', str(jobs), '--timeout', str(timeout), '--json']
            for test in detection_tests or ():
                result['replay'].append('--test=' + test)
            for test in equivalence_tests:
                result['replay'].append('--equivalence-test=' + test)
            # Paths written into the report refer to the live lookup or capture record,
            # never to the transient .building directory.
            (directory / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
            (directory / 'inputs.json').write_text(json.dumps(inputs, indent=2) + '\n')

        identifier = publish(project / 'rvw-results', build)
        result['generation'] = identifier
        return result
    return mutation_report(project, detection_tests, equivalence_tests)
