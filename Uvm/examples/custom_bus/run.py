"""Generate and run the project-adapter path on a small RTL endpoint."""
import argparse
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import sqlite3
import xml.etree.ElementTree as ET
from rvw.common.proc import run_group
from rvw.uvm.scaffold import generate
from rvw.sim.cocotb import run


def prepare(out):
    src = Path(__file__).resolve().parent
    out.mkdir(parents=True, exist_ok=False)
    db = out / 'design.db'
    # A declared database fixture tests adapter selection, not Scala extraction.
    with sqlite3.connect(db) as conn:
        conn.executescript('''CREATE TABLE meta(key,value);
 INSERT INTO meta VALUES ('schema','rvw.designdb/20');
 CREATE TABLE components(id,parent_id,module);
 INSERT INTO components VALUES (1,NULL,'custom_endpoint');
 CREATE TABLE bundles(component_id,path,class_name);
 INSERT INTO bundles VALUES (1,'custom_endpoint.link','example.CustomLink');
 CREATE TABLE signals(component_id,name,direction);
 CREATE TABLE clock_domains(clock,reset,reset_active_high);
 INSERT INTO clock_domains VALUES ('tick','clear_n',0);
 CREATE TABLE rtl_files(path);''')
        bindings = json.loads((src/'adapter.json').read_text())['bindings']
        outputs = {'done', 'fault', 'read_value'}
        conn.executemany('INSERT INTO signals VALUES (1,?,?)',
                         [(name, 'out' if name in outputs else 'in')
                          for name in [*bindings.values(), 'corrupt']])
        conn.execute('INSERT INTO rtl_files VALUES (?)', (str(src/'endpoint.sv'),))
    return generate(db, src/'map.json', out/'bench', adapter=src/'adapter.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    generated = prepare(out)
    rows = []
    original = os.environ.get('CUSTOM_BUS_CORRUPT')
    try:
        for bad in (False, True):
            os.environ['CUSTOM_BUS_CORRUPT'] = str(int(bad))
            folder = out/('bad' if bad else 'good')
            result = run(Path(generated['manifest']), folder, seed=17, timeout=120)
            assert len(result['tests']) == 1, result
            row = result['tests'][0]
            xml = ET.parse(folder/'cocotb.xml')
            failures = list(xml.iter('failure'))
            if bad:
                assert row['status'] == 'fail' and failures, row
                assert 'APB_DATA' in ''.join(ET.tostring(f, encoding='unicode') for f in failures)
                assert not (folder/'custom-checks.json').exists()
                checks = None
            else:
                assert row['status'] == 'pass' and not failures, row
                checks = json.loads((folder/'custom-checks.json').read_text())
                assert checks['transfers'] == 82 and checks['checks'] == 83, checks
            rows.append(dict(corrupt=bad, status=row['status'], expected_result_checked=True,
                             counts=checks))
    finally:
        if original is None:
            os.environ.pop('CUSTOM_BUS_CORRUPT', None)
        else:
            os.environ['CUSTOM_BUS_CORRUPT'] = original
    src = Path(__file__).resolve().parent
    engine = run_group(['verilator', '--version'], capture=True, timeout=10)
    assert engine.returncode == 0 and not engine.timed_out
    report = dict(schema='rvw.custom-bus-qualification/1', seed=17, runs=rows,
                  engine=engine.stdout.strip(), cocotb=version('cocotb'), pyuvm=version('pyuvm'),
                  source_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in sorted(src.iterdir()) if p.suffix in ('.py', '.sv') or p.name in ('adapter.json', 'map.json')})
    (out/'qualification.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
