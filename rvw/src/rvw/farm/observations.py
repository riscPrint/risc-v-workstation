"""Record advisory design-signal observations from native C1 waveform artifacts."""
import hashlib
from pathlib import Path
import sqlite3
import tempfile
from rvw.common.capture import Capture
from rvw.wave.capture import WaveInputs, scope
from rvw.results import load_run
from rvw.wave.vcd import open_text, read_header, body_changes, to_int
from .recorded_results import recorded_results


def observe(db, root, wave_prefix):
    db = Path(db).resolve()
    with sqlite3.connect(db.as_uri()+'?mode=ro', uri=True) as connection:
        paths = [r[0] for r in connection.execute('SELECT path FROM signals WHERE pruned=0')]
    prefix = wave_prefix.rstrip('.') + '.' if wave_prefix else ''
    names = {prefix+p.replace('/', '.'): p for p in paths}
    tests, issues = [], []
    for suite in recorded_results(root):
        for test in suite.tests:
            if not test.conclusive:
                raise ValueError('inconclusive C3 cannot supply selection observations: '+test.id)
            if any(t['id'] == test.id for t in tests):
                raise ValueError('observation test IDs must be unique')
            if not test.wall_s or test.wall_s <= 0:
                raise ValueError('test needs positive measured wall_s: '+test.id)
            row = dict(id=test.id, wall_seconds=test.wall_s, source=suite.source)
            directory = suite.path/test.run if test.run else None
            if directory is None:
                issues.append(dict(test=test.id, error='missing C1 run path'))
                tests.append(row)
                continue
            run = load_run(directory)
            if run.why_inconclusive or (run.core,run.config,run.seed,run.elf_sha256) != (
                    suite.core,suite.config,test.seed,test.extra.get('elf_sha256')):
                raise ValueError('C1 identity differs from C3: '+test.id)
            wave = run.artifact('wave')
            if wave is None or not str(wave).endswith(('.vcd','.vcd.gz','.fst')):
                issues.append(dict(test=test.id,error='missing waveform; signals stay unknown'))
                tests.append(row)
                continue
            with tempfile.TemporaryDirectory(prefix="rvw-farm-observe-") as temporary:
                inputs = WaveInputs(Capture(Path(temporary)/"capture"))
                copied_wave = inputs.file(wave)
                with scope(inputs), open_text(str(copied_wave)) as stream:
                    header = read_header(stream)
                    codes = {}
                    for variable in header.vars:
                        if variable.name in names:
                            codes.setdefault(variable.code, set()).add(names[variable.name])
                    values, changed = {}, set()
                    for _, code, raw in body_changes(stream, set(codes)):
                        value = to_int(raw)
                        if value is not None:
                            if code in values and values[code] != value:
                                changed.update(codes[code])
                            values[code] = value
                inputs.verify()
                row["wave_capture"] = inputs.capture.record()
            row.update(wave_sha256=hashlib.sha256(wave.read_bytes()).hexdigest(),
                       rtl_sha256=run.extra.get('rtl_sha256'), mapped_signals=sum(len(paths) for paths in codes.values()), mapped_codes=len(codes),
                       database_signals=len(paths))
            if codes:
                row['signals'] = sorted(changed)
            else:
                issues.append(dict(test=test.id,error='no exact VCD/database signal mapping; signals stay unknown'))
            tests.append(row)
    if not tests:
        raise ValueError('no C3 tests to observe')
    return dict(schema='rvw.impact-observations/1',database_sha256=hashlib.sha256(db.read_bytes()).hexdigest(),
                wave_prefix=wave_prefix,tests=tests,issues=issues,
                basis='known-value changes including reset and boot; exact signal names; partial observations',
                coverage_claim='not statement, branch or functional coverage; advisory only')
