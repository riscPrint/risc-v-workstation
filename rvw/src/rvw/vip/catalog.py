"""Agent inventory and type-selected cocotb bench skeletons."""
import importlib
import json
from pathlib import Path
import re
from rvw.query.db import run_on, QueryError

# Use exact Spinal class names. Stream payload types need a project adapter.
TYPES = {
    'spinal.lib.bus.amba3.apb.Apb3': 'apb',
    'spinal.lib.bus.amba4.apb.Apb4': 'apb',
    'spinal.lib.bus.amba3.ahblite.AhbLite3': 'ahb',
    'spinal.lib.bus.amba4.axi.Axi4': 'axi',
    'spinal.lib.bus.amba4.axilite.AxiLite4': 'axi',
    'spinal.lib.com.uart.Uart': 'uart',
    'spinal.lib.com.spi.SpiMaster': 'spi',
}
MODULES = ('apb','ahb','axis','axi','tilelink','uart','spi','i2c','gpio')


def agents():
    return {'agents': [{'name': n, 'python': 'rvw.vip.'+n,
                        'sv': 'Uvm/vip/'+n+'/',
                        'spinal_types': [t for t, agent in TYPES.items() if agent==n]}
                       for n in MODULES]}


def _buses(db):
    return [dict(path=p, spinal_type=t, agent=TYPES[t])
            for p,t in db.conn.execute('SELECT path,class_name FROM bundles ORDER BY path') if t in TYPES]


def buses(db): return run_on(db, lambda design: {'buses': _buses(design)})


def skeleton(db, out, bus=None, clock='clk', reset='reset_n'):
    def generate(design):
        found = [b for b in _buses(design) if bus is None or b['path']==bus]
        if len(found)!=1:
            raise QueryError('select exactly one supported bus: '+', '.join(b['path'] for b in found))
        selected=found[0]; proto=selected['agent']; prefix=selected['path']
        signals=design.conn.execute('SELECT path,spinal_path FROM signals').fetchall()
        mapping={}
        for path,spinal in signals:
            for name in (spinal,path):
                if name and (name.startswith(prefix+'.') or name.startswith(prefix+'_')):
                    suffix=name[len(prefix)+1:].replace('.','_').lower()
                    key=re.sub(r'_(payload)_', '_', suffix)
                    if proto in ('apb','ahb','axi'): key=key.replace('_','')
                    if key in mapping and mapping[key]!=path: raise QueryError('ambiguous bus pin '+key)
                    mapping[key]=path
        if not mapping: raise QueryError('no captured signals for bus '+prefix)
        # Prefix-free adapters and prefix adapters share one explicit view.
        bound={'clk':clock,'reset_n':reset}
        bound.update({(k if proto in ('apb','ahb') else 'bus_'+k):v for k,v in mapping.items()})
        module=importlib.import_module('rvw.vip.'+proto)
        if proto in ('apb','ahb'):
            missing=set(module.Pins.__dataclass_fields__)-set(bound)
            if missing: raise QueryError('missing required agent pins: '+', '.join(sorted(missing)))
        args='view' if proto in ('apb','ahb') else "view, 'bus'"
        if selected['spinal_type'].endswith('.AxiLite4'): args+=', lite=True'
        text='''"""Generated bench skeleton. Add reset, stimulus and expected results before use."""
from types import SimpleNamespace
import cocotb
from rvw.vip.PROTOCOL import CocotbAgent

BINDINGS = MAPPING

def handle(dut, path):
    node = dut
    for part in path.split('.'):
        node = getattr(node, part)
    return node

@cocotb.test()
async def bench(dut):
    view = SimpleNamespace(**{key: handle(dut, path) for key, path in BINDINGS.items()})
    agent = CocotbAgent(ARGS)
    raise NotImplementedError('add project reset, stimulus and scoreboard expectations')
'''.replace('PROTOCOL',proto).replace('MAPPING',repr(bound)).replace('ARGS',args)
        # A skeleton must never overwrite an existing bench.
        target=Path(out); target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('x') as f: f.write(text)
        return {'status':'skeleton','path':str(target),'bus':selected,'bindings':bound,
                'note':'not a verification result; reset, stimulus and expectations are required'}
    return run_on(db, generate)
