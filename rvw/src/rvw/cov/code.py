"""Verilator point coverage. Keep original metadata: line numbers alone lose branches."""
from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from sys import intern
from itertools import combinations

from rvw.common.proc import run_group
from . import captured
from rvw.results import RunResult, inconclusive_cause, load_results, load_run_set
from rvw.results.generation import GenerationError, locate


def iter_dat(path, metadata=True):
    with Path(path).open() as stream:
        for n, line in enumerate(stream, 1):
            line = line.rstrip('\r\n')
            if not line or line.startswith('#'):
                continue
            match = re.fullmatch(r"C '(.*)' (\d+)", line)
            if not match:
                raise ValueError(f"{path}:{n}: unsupported Verilator coverage record")
            key, count = match.groups()
            fields = {}
            if metadata:
                for field in key.split('\x01'):
                    if field:
                        name, sep, value = field.partition('\x02')
                        if not sep or name in fields:
                            raise ValueError(f"{path}:{n}: invalid coverage metadata")
                        fields[intern(name)] = intern(value)
            yield sha256(key.encode()).hexdigest(), key, fields, int(count)


def read_counts(path):
    counts = {}
    for pid, _, _, count in iter_dat(path, metadata=False):
        counts[pid] = counts.get(pid, 0) + count
    if not counts:
        raise ValueError(f'{path}: no coverage points')
    return counts


def _generation_path(path):
    """Pin each store once. Explicit generation paths retain their selected ID."""
    capture = captured.current()
    if not hasattr(capture, '_coverage_generations'):
        capture._coverage_generations = {}
    return locate(path, readers=capture._coverage_generations)


def _generation_file(path, reader):
    """Check the consumed copy against the pinned manifest, without a second live read."""
    item = captured.file(path)
    if reader is not None:
        relative = Path(path).relative_to(reader.path).as_posix()
        # Generation has no streaming capture API. Its validated manifest supplies
        # the expected digest; compare that with the exact C8 copy being consumed.
        expected = reader.entry(relative)
        if expected is None or (item.sha256, item.size, item.executable) != expected[1:]:
            raise GenerationError(f'generation artifact changed: {relative}')
    return item


def _suite_inputs(suite, reader):
    found = []
    for test in suite.tests:
        why = inconclusive_cause(test.status, test.extra, test.signature)
        if why:
            raise ValueError(f"{suite.path}: test {test.id}: inconclusive coverage evidence: {why}")
        found.extend(_run_input(suite.path / test.run, test.id, reader=reader))
    return found


@captured.command
def inputs(specs):
    """Read raw test=dat arguments, a C1 directory, or a C3 suite directory."""
    found = []
    for spec in specs:
        if '=' in spec and not Path(spec).exists():
            test, filename = spec.split('=', 1)
            found.append((test, Path(filename).absolute(), None))
            continue
        path, reader = _generation_path(Path(spec).absolute())
        if reader is not None and path == reader.path:
            for suite in load_run_set(reader):
                found.extend(_suite_inputs(suite, reader))
            continue
        if path.is_dir():
            path = path / ('results.json' if (path / 'results.json').exists() else 'result.json')
        if path.suffix == '.json':
            item = _generation_file(path, reader)
            obj = json.loads(item.copy.read_text())
            if obj.get('schema') == 'rvw.results/1':
                suite = load_results(path, generation=reader) if reader is not None else load_results(
                    path, capture=captured.current())
                found.extend(_suite_inputs(suite, reader))
            elif obj.get('schema') == 'rvw.run/1':
                found.extend(_run_input(path, obj=obj, reader=reader))
            else:
                raise ValueError(f"{path}: expected C1 or C3 schema")
        else:
            _generation_file(path, reader)
            found.append((path.parent.name + '/' + path.name, path, None))
    names = [t for t, _, _ in found]
    if len(names) != len(set(names)):
        raise ValueError("duplicate test IDs; use explicit unique test=coverage.dat arguments")
    # Freeze all data before the first parser runs.
    for _, path, _ in found:
        captured.file(path)
    return found


def _run_input(path, name=None, obj=None, reader=None):
    path = Path(path)
    if path.is_dir():
        path = path / 'result.json'
    item = _generation_file(path, reader)
    run = RunResult.from_dict(obj if obj is not None else json.loads(item.copy.read_bytes()))
    if why := run.why_inconclusive:
        raise ValueError(f"{path}: inconclusive coverage evidence: {why}")
    obj = run.to_dict()
    artifact = obj.get('artifacts', {}).get('coverage')
    if not artifact:
        raise ValueError(f"{path}: no coverage artifact; rerun with --coverage")
    artifact_path = (Path(path).parent / artifact).absolute()
    _generation_file(artifact_path, reader)
    if reader is not None:
        obj['generation'] = reader.id
    return [(name or Path(obj['elf']).name, artifact_path, obj)]


def _inconclusive_runs(data):
    """Recheck retained C1 results, including databases written before the merge guard."""
    reasons = {}
    for name, test in data['tests'].items():
        if test.get('run') is not None:
            why = RunResult.from_dict(test['run']).why_inconclusive
            if why:
                reasons[name] = why
    return reasons


def _require_conclusive(data):
    for name, why in _inconclusive_runs(data).items():
        raise ValueError(f"test {name}: inconclusive coverage evidence: {why}; recollect coverage")


class SourceMap:
    """Explicit range mappings first; same-line Spinal location comments second."""
    @captured.command
    def __init__(self, root='.', mapping=None, hgldd=(), scala_root=None, design_db=None):
        self.root = Path(root).absolute()
        self.mapping = json.loads(captured.read_text(mapping)).get('mappings', []) if mapping else []
        self.cache = {}
        self.db_signals = {}
        self.db_assignments = {}
        self.db_rtl = {}
        self.db_top = None
        if design_db:
            import sqlite3
            db = captured.file(design_db)
            with sqlite3.connect(f'file:{db.copy}?mode=ro', uri=True) as conn:
                if conn.execute("SELECT value FROM meta WHERE key='schema'").fetchone()[0] != 'rvw.designdb/20':
                    raise ValueError('expected rvw.designdb/20')
                self.db_top = conn.execute("SELECT module FROM components WHERE path=''").fetchone()[0]
                capture = json.loads(conn.execute("SELECT value FROM meta WHERE key='input_capture'").fetchone()[0])
                self.db_rtl = {str(Path(f['resolved']).resolve()): f['sha256'] for f in capture['files']
                               if Path(f['resolved']).suffix in ('.v', '.sv')}
                rows = conn.execute("""SELECT c.path,s.name,f.path,s.line
                    FROM signals s JOIN components c ON c.id=s.component_id
                    JOIN files f ON f.id=s.file_id WHERE s.pruned=0 AND s.line>0""")
                for path, name, file, line in rows:
                    self.db_signals[(path, name)] = {'file': file, 'line': line}
                if conn.execute("SELECT 1 FROM sqlite_master WHERE name='assignments'").fetchone():
                    rows = conn.execute("""SELECT c.path,s.name,a.kind,a.component_id=s.component_id,
                        a."range",f.path,a.line FROM assignments a
                        JOIN signals s ON s.id=a.target_id JOIN components c ON c.id=s.component_id
                        LEFT JOIN files f ON f.id=a.file_id""")
                    assignments = defaultdict(list)
                    for path, name, kind, local, span, file, line in rows:
                        assignments[(path, name)].append((kind, local, span, file, line))
                    for key, items in assignments.items():
                        # Reset, partial and multiple assignments cannot identify one statement.
                        if len(items) == 1:
                            kind, local, span, file, line = items[0]
                            if kind == 'data' and local and not span and file and line and line > 0:
                                self.db_assignments[key] = {'file': file, 'line': line}
                # /20 memory keys retain the exact MemSymbolesTag emitted names.
                # Read these names; do not guess aliases from a suffix or array index.
                if conn.execute("SELECT 1 FROM sqlite_master WHERE name='memories'").fetchone():
                    rows = conn.execute("""SELECT c.path,m.key,f.path,m.line FROM memories m
                        JOIN components c ON c.id=m.component_id JOIN files f ON f.id=m.file_id
                        WHERE m.line>0""")
                    for path, key, file, line in rows:
                        tag = re.search(r'tag spinal\.core\.MemSymbolesTag:(\[[^]]*\])', key or '')
                        if tag:
                            for name in re.findall(r'("(?:\\.|[^"\\])*"):Range\(', tag[1]):
                                name = json.loads(name)
                                loc = {'file': file, 'line': line}
                                if (path, name) in self.db_signals and self.db_signals[(path, name)] != loc:
                                    raise ValueError('conflicting memory symbol declaration')
                                self.db_signals[(path, name)] = loc


        self.scala_files = defaultdict(list)
        if scala_root:
            tree = captured.current().tree(Path(scala_root), git=False)
            for item in tree.files:
                if Path(item.source).suffix == '.scala':
                    self.scala_files[Path(item.source).name].append(Path(item.source).absolute())
        self.signals = {}
        self.instance_signals = {}
        candidates = defaultdict(list)
        for filename in hgldd:
            documents = json.loads(captured.read_text(filename))
            if not isinstance(documents, list):
                documents = [documents]
            for doc in documents:
                files = doc['HGLDD']['file_info']
                structs = {o['obj_name']: o for o in doc['objects'] if o.get('kind') == 'struct'}

                def leaves(var, value, parents=()):
                    # Spinal emits aggregate expressions with matching struct fields.
                    # Attribute each leaf to its own declaration, never to its container.
                    if 'sig_name' in value:
                        yield var, value['sig_name']
                        return
                    name = var.get('type_name')
                    if name in parents:
                        raise ValueError('recursive HGLDD struct')
                    operands = value.get('operands', [])
                    if var.get('unpacked_range'):
                        element = {k: v for k, v in var.items() if k != 'unpacked_range'}
                        remaining = var['unpacked_range'][2:]
                        if remaining:
                            element['unpacked_range'] = remaining
                        for operand in operands:
                            yield from leaves(element, operand, parents)
                    elif name in structs:
                        fields = structs[name].get('port_vars', [])
                        if len(fields) != len(operands):
                            raise ValueError('HGLDD struct expression shape differs')
                        for field, operand in zip(fields, operands):
                            yield from leaves(field, operand, (*parents, name))

                # Instance overrides can retain different Scala source locations
                # even when RTL module definitions are deduplicated.
                def instance(obj, path):
                    for root_var in obj.get('port_vars', []):
                        for var, signal in leaves(root_var, root_var.get('value', {})):
                            loc = var.get('hgl_loc')
                            if loc and loc.get('begin_line'):
                                key = (path, signal)
                                value = {'file': files[loc['file'] - 1], 'line': loc['begin_line'],
                                         'method': 'hgldd-instance-declaration'}
                                if key in self.instance_signals and self.instance_signals[key] != value:
                                    self.instance_signals[key] = None
                                else:
                                    self.instance_signals[key] = value
                    for child in obj.get('children', []):
                        instance(child, path + '.' + child.get('hdl_obj_name', child.get('name', '')))
                modules = [o for o in doc['objects'] if o.get('kind') == 'module']
                referenced = {c.get('module_name') for o in modules for c in o.get('children', [])}
                for obj in modules:
                    if obj.get('module_name') not in referenced:
                        instance(obj, 'TOP.' + obj['module_name'])
                objects = list(doc['objects'])
                for obj in objects:
                    # Instance overrides can differ after RTL module deduplication.
                    # A module-level toggle point cannot choose one such location.
                    objects.extend(obj.get('children', []))
                    module = obj.get('module_name')
                    if not module:
                        continue
                    for root_var in obj.get('port_vars', []):
                        for var, signal in leaves(root_var, root_var.get('value', {})):
                            loc = var.get('hgl_loc')
                            if not loc or not loc.get('begin_line'):
                                continue
                            source = files[loc['file'] - 1]
                            candidates[(module, signal)].append({
                                "file": source, "line": loc['begin_line'],
                                "method": "hgldd-signal-declaration"})
                            hdl = var.get('hdl_loc')
                            if hdl and hdl.get('begin_line'):
                                self.mapping.append({"verilog": files[hdl['file'] - 1],
                                    "line_start": hdl['begin_line'],
                                    "line_end": hdl.get('end_line', hdl['begin_line']),
                                    "scala": source, "scala_line": loc['begin_line']})
        for key, locations in candidates.items():
            if all(loc == locations[0] for loc in locations):
                self.signals[key] = locations[0]

    def db_instance(self, fields):
        hierarchy = fields.get('h', '').split('.')
        if self.db_top and hierarchy.count(self.db_top) == 1 and '*' not in fields.get('h', ''):
            return '.'.join(hierarchy[hierarchy.index(self.db_top) + 1:])
        return None

    @captured.command
    def location(self, fields):
        file = fields.get('f', fields.get('filename', ''))
        line = int(fields.get('l', fields.get('lineno', 0)))
        if self.db_signals:
            path = str((self.root / file).resolve())
            digest = captured.sha256(path)
            expected = self.db_rtl.get(path)
            if (expected and digest != expected) or (not expected and digest not in self.db_rtl.values()):
                raise ValueError('design database RTL differs from coverage RTL')
        spans = [item for item in self.mapping if item['verilog'] == file
                 and item['line_start'] <= line <= item.get('line_end', item['line_start'])]
        if spans:
            locations = {(item['scala'], item['scala_line']) for item in spans}
            if len(locations) != 1:
                return None
            source, source_line = locations.pop()
            return {"file": source, "line": source_line, "method": "explicit-range"}
        if fields.get('t') == 'toggle':
            signal = re.sub(r'\[\d+\]$', '', fields.get('o', '').split(':')[0])
            instance = self.db_instance(fields)
            if instance is not None:
                name = re.sub(r'\[\d+\]', '', signal)
                declared = self.db_signals.get((instance, name))
                if declared:
                    return dict(declared, method='designdb-instance-declaration')
            exact = self.instance_signals.get((fields.get('h'), signal))
            if exact:
                return exact
            location = self.signals.get((fields.get('page', '').removeprefix('v_toggle/'), signal))
            if location:
                return location
        path = (self.root / file).absolute()
        if path not in self.cache:
            self.cache[path] = captured.read_text(path, errors='replace').splitlines() if path.is_file() else []
        lines = self.cache[path]
        # Do not guess from the nearest comment: it can cross unrelated assignments.
        locations = []
        declaration_used, comment_used, assignment_used = False, False, False
        ranges = [(line, line)]
        # Verilator records the exact statements covered by a point in S. The
        # instrumented branch/header line often precedes its assignment comment.
        if fields.get('S'):
            ranges = []
            for span in fields['S'].split(','):
                match = re.fullmatch(r'(\d+)(?:-(\d+))?', span)
                if match:
                    ranges.append((int(match[1]), int(match[2] or match[1])))
        for begin, end in ranges:
            for n in range(max(begin, 1), min(end, len(lines)) + 1):
                match = re.search(r'(\S+\.scala)(?::|\s+l)(\d+)', lines[n - 1])
                if not match:
                    instance = self.db_instance(fields)
                    if instance is not None:
                        text = lines[n - 1]
                        # Spinal also emits a complete assignment on an always header line.
                        text = re.sub(r'^\s*(?:always\s*@\s*\(\s*\*\s*\)|always_comb)\s+', '', text)
                        # Exact declared targets and branch operands, never a nearest-line guess.
                        targets = re.findall(r'^\s*(?:assign\s+)?([A-Za-z_]\w*)(?:\[[^;=]*?\])*\s*(?:<=|=(?!=))', text)
                        condition = re.match(r'\s*(?:end\s+else\s+)?if\s*\((.*)\)\s*(?:begin\b|$)', text.split('//', 1)[0])
                        if condition:
                            targets += re.findall(r'\b[A-Za-z_]\w*\b', condition[1])
                        targets += re.findall(r'\b(?:reg|wire)\s+(?:\[[^]]+\]\s*)?([A-Za-z_]\w*)', text)
                        assignment_targets = re.findall(r'^\s*(?:assign\s+)?([A-Za-z_]\w*)(?:\[[^;=]*?\])*\s*(?:<=|=(?!=))', text)
                        linked = set()
                        if fields.get('S') and fields.get('t') in ('line', 'branch'):
                            for target in assignment_targets:
                                loc = self.db_assignments.get((instance, target))
                                if loc:
                                    assignment_used = True
                                    linked.add(target)
                                    locations.append((loc['file'], loc['line']))
                        for target in targets:
                            if target in linked:
                                continue
                            loc = self.db_signals.get((instance, target))
                            if loc:
                                declaration_used = True
                                locations.append((loc['file'], loc['line']))
                    continue
                source = match[1].lstrip('(')
                if '/' not in source and '\\' not in source:
                    candidates = self.scala_files.get(source, [])
                    if len(candidates) > 1:
                        return None  # An ambiguous comment cannot justify attribution of this point.
                    if len(candidates) == 1:
                        source = str(candidates[0])
                comment_used = True
                locations.append((source, int(match[2])))
        if locations:
            # Multiple locations in one point are retained explicitly, rather
            # than making up a one-to-one relationship with a single assignment.
            locations = sorted(set(locations))
            source, scala_line = locations[0]
            return {"file": source, "line": scala_line,
                    "method": ("covered-span-assignment-links-mixed" if declaration_used or comment_used
                               else "covered-span-assignment-links") if assignment_used else ("covered-span-comments-and-declarations" if comment_used else "covered-span-declarations")
                    if declaration_used else "covered-span-comments" if fields.get('S') else "same-line-comment",
                    "locations": [{"file": f, "line": n} for f, n in locations]}
        return None


@captured.command
def merge(specs, root='.', mapping=None, hgldd=(), revision=None, scala_root=None, design_db=None):
    merged, tests, universe, contexts = {}, {}, None, set()
    collected = inputs(specs)
    smap = SourceMap(root, mapping, hgldd, scala_root, design_db)
    if revision is not None:
        revision = captured.current().git_ref(Path(root), revision)
    for name, path, run in collected:
        first = not merged
        if run:
            contexts.add(json.dumps({"core": run.get('core'), "config": run.get('config'),
                                     "source": run.get('source'), "tools": run.get('tools')}, sort_keys=True))
        seen = set()
        item = captured.file(path)
        for pid, key, fields, count in iter_dat(item.copy, metadata=first):
            if pid not in merged:
                if not first:
                    raise ValueError('coverage point universes differ; merge only runs of the same instrumented model')
                merged[pid] = {"id": pid, "key": key, "fields": fields, "count": 0, "tests": {},
                               "scala": smap.location(fields)}
            point = merged[pid]
            seen.add(point['id'])
            point['count'] += count
            if count:
                point['tests'][name] = point['tests'].get(name, 0) + count
        if len(seen) != len(merged) or not seen:
            raise ValueError('coverage point universes differ; merge only runs of the same instrumented model')
        if first:
            universe = sha256('\n'.join(sorted(merged)).encode()).hexdigest()
        tests[name] = {"coverage": item.resolved, "sha256": item.sha256, "point_universe": universe, "run": run,
                       **({"generation": run["generation"]} if run and "generation" in run else {})}
    if not merged:
        raise ValueError('no coverage inputs')
    if len(contexts) > 1:
        raise ValueError('C1 source/config/tool provenance differs; coverage must come from the same instrumented build')
    sources = {}
    for point in merged.values():
        source = point['fields'].get('f', '')
        path = (Path(root).absolute() / source).absolute()
        if source not in sources:
            item = captured.file(path) if path.is_file() else None
            sources[source] = {"path": item.resolved if item else str(path),
                               "sha256": item.sha256 if item else None}
    return {"schema": "rvw.coverage/1", "point_universe": universe, "source_root": str(Path(root).absolute()),
            "source_revision": revision, "sources": sources, "tests": tests, "points": list(merged.values()),
            "generations": sorted({t["generation"] for t in tests.values() if "generation" in t})}


def summary(points):
    points = list(points)
    excluded = sum(bool(p.get('exclusion')) for p in points)
    eligible = [p for p in points if not p.get('exclusion')]
    hit = sum(p['count'] > 0 for p in eligible)
    return {"total": len(points), "excluded": excluded, "eligible": len(eligible), "hit": hit,
            "never_hit": len(eligible) - hit, "percent": 100 * hit / len(eligible) if eligible else None}


@captured.command
def report(data, exclusions=None):
    _require_conclusive(data)
    # Imported lazily to keep ordinary reports independent of external formal tools.
    if exclusions:
        from .proof import apply_exclusions
        data = apply_exclusions(data, exclusions)
    groups = {kind: defaultdict(list) for kind in ('modules', 'instances', 'scala', 'types')}
    module_types = defaultdict(lambda: defaultdict(list))
    warnings = set()
    source_states = {}
    for name, source in data.get('sources', {}).items():
        path = Path(source['path'])
        state = ('unavailable-at-collection' if not source['sha256'] else 'missing' if not path.is_file()
                 else 'unchanged' if captured.sha256(path) == source['sha256'] else 'changed')
        source_states[name] = state
        if state != 'unchanged':
            warnings.add(f'Source {name}: {state}; coverage refers to the collected instrumented model.')
    for p in data['points']:
        f = p['fields']
        # Verilator's page is a coverage type plus module name, not a hierarchy.
        page = f.get('page', 'unknown')
        module = re.sub(r'^v_(?:line|toggle|branch|expr|fsm(?:_arc|_state)?|user)/', '', page)
        groups['modules'][module].append(p)
        groups['types'][f.get('t', 'unknown')].append(p)
        module_types[module][f.get('t', 'unknown')].append(p)
        hierarchy = f.get('h', f.get('hier', 'unknown'))
        groups['instances'][hierarchy].append(p)
        if '*' in hierarchy:
            warnings.add('Wildcard hierarchy is aggregated across instances; instance counts are not separable.')
        if p.get('scala'):
            for loc in p['scala'].get('locations', [p['scala']]):
                groups['scala'][f"{loc['file']}:{loc['line']}"].append(p)
    never = [{"id": p['id'], "fields": p['fields'], "scala": p.get('scala')} for p in data['points']
             if p['count'] == 0 and not p.get('exclusion')]
    instance_scope = {
        name: {"scope": "aggregate" if '*' in name else "unknown" if name == 'unknown' else "instance",
               "instrumented_points": len(points),
               "mapped_scala_points": sum(bool(p.get("scala")) for p in points),
               "unmapped_scala_points": sum(not p.get("scala") for p in points),
               "exact_instance_denominator": None if '*' in name or name == 'unknown' else len(points)}
        for name, points in groups['instances'].items()}
    mapping_methods = defaultdict(int)
    for point in data['points']:
        if point.get('scala'):
            mapping_methods[point['scala'].get('method', 'unspecified')] += 1
    from .line_metrics import line_metrics
    return {"schema": "rvw.coverage-report/1", "instance_scope": instance_scope,
            "scala_line_metrics": line_metrics(data["points"], summary),
            "scala_mapping": {"denominator": len(data['points']),
                              "mapped": sum(bool(p.get('scala')) for p in data['points']),
                              "methods": dict(sorted(mapping_methods.items())),
                              "statement_hit_status": "undetermined",
                              "note": "Source links navigate to declarations or assignments. Point hits do not establish individual Scala statement hits.",
                              "unit": "instrumented points; a point can link to several Scala lines"}, "summary": summary(data['points']),
            **{kind: {k: summary(v) for k, v in sorted(items.items())} for kind, items in groups.items()},
            "module_types": {module: {kind: summary(points) for kind, points in sorted(kinds.items())}
                             for module, kinds in sorted(module_types.items())},
            "unmapped_scala_points": sum(not p.get('scala') for p in data['points']),
            "sources": source_states,
            "never_hit": never, "warnings": sorted(warnings),
            "exclusions": [p['exclusion'] for p in data['points'] if p.get('exclusion')]}


def rank(data, exact=False):
    _require_conclusive(data)
    covered = {name: {p['id'] for p in data['points'] if p['count'] and name in p['tests']
                      and not p.get('exclusion')} for name in data['tests']}
    remaining = set().union(*covered.values()) if covered else set()
    frequency = defaultdict(int)
    for hits in covered.values():
        for pid in hits:
            frequency[pid] += 1
    order = []
    while remaining:
        name = min(covered, key=lambda name: (-len(covered[name] & remaining), name))
        gained = covered[name] & remaining
        order.append({"test": name, "new_points": len(gained), "covered_points": len(covered[name]),
                      "unique_points": sum(frequency[p] == 1 for p in covered[name])})
        remaining -= gained
    # Greedy set cover is deterministic and useful, but not a globally minimal set.
    selected = [item['test'] for item in order]
    target = set().union(*covered.values()) if covered else set()
    # Remove any now-redundant choices, yielding an inclusion-minimal set.
    for name in list(reversed(selected)):
        others = set().union(*(covered[n] for n in selected if n != name))
        if others == target:
            selected.remove(name)
    if exact:
        if len(covered) > 20:
            raise ValueError('--exact is bounded to 20 tests; use the greedy inclusion-minimal set for larger suites')
        names = sorted(covered)
        index = {pid: n for n, pid in enumerate(sorted(target))}
        masks = {name: sum(1 << index[pid] for pid in covered[name]) for name in names}
        full = (1 << len(target)) - 1
        def complete(combination):
            mask = 0
            for name in combination:
                mask |= masks[name]
            return mask == full
        for size in range(len(selected) + 1):
            solution = next((list(c) for c in combinations(names, size)
                             if complete(c)), None)
            if solution is not None:
                selected = solution
                break
    redundant = sorted(set(covered) - set(selected))
    return {"schema": "rvw.coverage-rank/1", "algorithm": "exact-set-cover" if exact else "greedy-set-cover-with-pruning",
            "optimal": exact, "inclusion_minimal": True, "selected": selected, "ranking": order,
            "redundant": redundant,
            "contribution": {n: {"covered_points": len(h), "unique_points": sum(frequency[p] == 1 for p in h)}
                             for n, h in sorted(covered.items())}}


def _git(repo, *args):
    tool = captured.current().tool('git')
    argv = [str(tool.path), '-C', str(repo), *args]
    env = captured.environment()
    env['GIT_NO_REPLACE_OBJECTS'] = '1'
    result = run_group(argv, capture=True, env=env, timeout=30)
    if result.returncode:
        raise subprocess.CalledProcessError(result.returncode, argv, output=result.stdout, stderr=result.stderr)
    return result.stdout


@captured.command
def select(data, revision, repo):
    inconclusive = _inconclusive_runs(data)
    # Parse zero-context hunks on the BASE side: coverage was collected before the edit.
    if not re.fullmatch(r'[^\s.][^\s]*\.\.[^.\s][^\s]*', revision) or '...' in revision:
        raise ValueError('--diff must be BASE..HEAD')
    base, head = revision.split('..', 1)
    if base.startswith('-') or head.startswith('-'):
        raise ValueError('git revisions cannot start with an option prefix')
    repo = Path(repo).resolve()
    # Resolve each distinct ref once. Later ref moves cannot change either diff or its identity.
    resolved = {rev: captured.current().git_ref(repo, rev)
                for rev in dict.fromkeys((base, head))}
    base_revision, head_revision = resolved[base], resolved[head]
    commit_range = f'{base_revision}..{head_revision}'
    # Every changed path, not only Scala: a Verilog blackbox, build.sbt or a resource file can
    # change the hardware without touching a mapped Scala line.
    names = [n for n in _git(repo, 'diff', '--no-ext-diff', '--no-renames',
                            '--name-only', '-z', commit_range).split('\0') if n]
    non_scala = sorted(n for n in names if not n.endswith('.scala'))
    diff = _git(repo, 'diff', '--no-ext-diff', '--no-renames',
                '--unified=0', commit_range, '--', '*.scala')
    changes, file = [], None
    for line in diff.splitlines():
        if line.startswith('--- a/'):
            file = line[6:]
        elif line.startswith('--- '):
            # New files and quoted/escaped paths need full regression rather than
            # borrowing the preceding file's location.
            file = None
        elif line.startswith('@@'):
            hunk = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
            start, count = int(hunk[1]), int(hunk[2] if hunk[2] is not None else 1)
            new_count = int(hunk[4] if hunk[4] is not None else 1)
            # Insertion has no old lines (git puts `start` at the line before it). Lines a hunk
            # adds beyond the ones it removes have no BASE line, so no coverage can map them.
            changes.append({"file": file, "start": max(1, start), "end": start + max(count, 1) - 1,
                            "insertion": count == 0, "new_file": file is None,
                            "added_lines": max(0, new_count - count)})
    # A changed Scala file without a text hunk (mode change, binary) has no lines to map.
    hunk_files = {c['file'] for c in changes}
    changes += [{"file": n, "start": None, "end": None, "insertion": False, "new_file": False, "no_hunk": True}
                for n in sorted(n for n in names if n.endswith('.scala') and n not in hunk_files)]
    selected, uncovered = set(), []
    def hit_tests(p):
        return {name for name, hits in (p.get('tests') or {}).items() if hits and name not in inconclusive}
    for change in changes:
        if change.get('no_hunk'):
            uncovered.append(change)
            continue
        # Evidence per changed BASE line: a line counts only if a point maps to it and some test
        # hit that point. One covered line never vouches for the others in its hunk.
        lines = [] if change['insertion'] else list(range(change['start'], change['end'] + 1))
        mapped, hit = set(), set()
        for p in data['points']:
            source = p.get('scala')
            if not source or not change['file']:
                continue
            tests = hit_tests(p)
            for loc in source.get('locations', [source]):
                f = Path(loc['file'])
                # Absolute paths can be rebased only by an exact repository-relative suffix.
                same = str(f) == change['file'] or (f.is_absolute() and str(f).endswith('/' + change['file']))
                if same and loc['line'] in lines:
                    mapped.add(loc['line'])
                    if tests:
                        hit.add(loc['line'])
                        selected.update(tests)
        change['unmapped_lines'] = [n for n in lines if n not in mapped]
        change['unhit_lines'] = [n for n in lines if n in mapped and n not in hit]
        if (not change['file'] or change['insertion'] or change['added_lines']
                or change['unmapped_lines'] or change['unhit_lines']):
            uncovered.append(change)
    # Missing mappings and newly added/uncovered code cannot justify dropping tests.
    unmapped = sum(not p.get('scala') for p in data['points'])
    coverage_revisions = [t['run'].get('source', {}).get('core_rev') if t.get('run') else data.get('source_revision')
                          for t in data['tests'].values()]
    stale = any(not rev or not base_revision.startswith(rev) for rev in coverage_revisions)
    dirty = any(t.get('run') and t['run'].get('source', {}).get('core_dirty') for t in data['tests'].values())
    clean_unverified = any(t.get('run') and t['run'].get('source', {}).get('core_dirty') is not False
                           for t in data['tests'].values())
    # An empty diff between two different commits proves nothing about the elaborated design
    # (e.g. a submodule or generated input moved): run everything.
    empty_between_revisions = not names and base_revision != head_revision
    reasons = [r for r, hit in (("non_scala_changes", non_scala), ("uncovered_changes", uncovered),
                                ("unmapped_points", unmapped), ("stale_or_unknown_revision", stale),
                                ("source_clean_unverified", clean_unverified),
                                ("inconclusive_runs", inconclusive),
                                ("empty_diff_between_revisions", empty_between_revisions)) if hit]
    fallback = bool((names or empty_between_revisions) and reasons)
    return {"schema": "rvw.coverage-select/1", "diff": revision, "changed": changes,
            "base_revision": base_revision, "head_revision": head_revision,
            "changed_files": names, "non_scala_changes": non_scala, "fallback_reasons": reasons if fallback else [],
            "direct_tests": sorted(selected), "tests": sorted(data['tests']) if fallback else sorted(selected),
            "fallback_all": fallback, "unmapped_points": unmapped, "uncovered_changes": uncovered,
            "coverage_revisions": sorted({r for r in coverage_revisions if r}),
            "stale_or_unknown_revision": stale, "dirty_source": bool(dirty),
            "source_clean_unverified": clean_unverified,
            "inconclusive_runs": inconclusive,
            "note": "BASE-side line mapping; stale coverage or changed elaboration requires a full regression."}
