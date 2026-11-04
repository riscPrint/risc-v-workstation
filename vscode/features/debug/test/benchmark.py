"""Opt-in backend latency benchmark. Uses a dense synthetic index, not RTL evidence.

PYTHONPATH=rvw/src python vscode/features/debug/test/benchmark.py --db DESIGN --out /tmp/debug-bench.rvwi
"""
import argparse
import json
from pathlib import Path
import sqlite3
from time import perf_counter

from rvw.query.session import Session

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--db', required=True)
p.add_argument('--out', required=True)
a = p.parse_args()
path = Path(a.out)
if path.exists():
    p.error('output already exists')
# 540000 actual event rows of 4096 bits. No sparse allocation or padding table.
count = 540000
meta = dict(schema='rvw.wave-index/1', source='synthetic-benchmark-no-source.vcd',
            sha256='synthetic', size=0, records=count+2, tools={},
            header=dict(lines=[], timescale='1ns', vars=[
                dict(code='!', name='TOP.VexTop.execute_PC', width=32, kind='wire', range=None),
                dict(code='"', name='TOP.VexTop.background', width=4096, kind='wire', range=None)]))
start = perf_counter()
with sqlite3.connect(path) as c:
    c.execute('PRAGMA journal_mode=OFF')
    c.execute('PRAGMA synchronous=OFF')
    c.executescript('CREATE TABLE metadata(value TEXT NOT NULL); CREATE TABLE events(seq INTEGER PRIMARY KEY,t INTEGER NOT NULL,code TEXT,raw TEXT);')
    c.execute('INSERT INTO metadata VALUES(?)', (json.dumps(meta),))
    c.executemany('INSERT INTO events VALUES(?,?,?,?)', ((i+1,i,'"','b'+format(i,'04096b')) for i in range(count)))
    c.execute('INSERT INTO events VALUES(?,?,?,?)',(count+1,0,'!','b0'))
    c.execute('INSERT INTO events VALUES(?,?,?,?)',(count+2,count-1,'!','b100'))
    c.executescript('CREATE INDEX time_range ON events(t,seq); CREATE INDEX signal_time ON events(code,t,seq);')
build_seconds=perf_counter()-start
start=perf_counter()
s = Session(a.db, str(path))
opened = s.request(dict(op='open'))
open_ms=(perf_counter()-start)*1000
jumps=[]
for t in [0,count//2,count-1]:
    start=perf_counter()
    r=s.request(dict(op='select',signal='execute_PC',time=str(t)))
    assert r['result']['mapping']=='resolved'
    jumps.append((perf_counter()-start)*1000)
s.close()
print(json.dumps(dict(scope='backend only; synthetic dense index; warm filesystem cache; no browser/render measurement',
                     bytes=path.stat().st_size, rows=count+2, build_seconds=build_seconds,
                     open_ms=open_ms, jump_ms=jumps, under_1s=open_ms<1000 and max(jumps)<1000)))
