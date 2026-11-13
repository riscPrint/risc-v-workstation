"""Project-declared plain HDL pyuvm skeleton."""
import json
from pathlib import Path
from rvw.common.hdl_ports import load
from rvw.query.db import DesignDB
from rvw.soc.model import load as load_soc


def generate(db, soc, out, *, rtl=None, language='pyuvm', profile='auto', port_map=None):
    if language != 'pyuvm' or profile not in ('auto','ready_valid'):
        raise ValueError('declared ready_valid buses currently support pyuvm with profile auto')
    load_soc(soc)
    spec=load(db,port_map)
    if len(spec['buses'])!=1: raise ValueError('declare one bus for the UVM skeleton')
    design=DesignDB(db)
    try:
        sources=list(rtl) if rtl else [p for p, in design.q('SELECT path FROM rtl_files')]
    finally: design.close()
    if not sources: raise ValueError('supply RTL sources')
    sources=[str(Path(p).resolve(strict=True)) if rtl else str((Path(db).resolve().parent/p).resolve(strict=True)) for p in sources]
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    from rvw.vip.declared import skeleton
    result=skeleton(db,out/'test_generated.py',port_map,uvm=True)
    (out/'scenario.py').write_text('async def run(dut, agent):\n    raise NotImplementedError("supply reset, stimulus and checked expected results")\n')
    (out/'bindings.json').write_text(json.dumps(result['bindings'],indent=2)+'\n')
    manifest=dict(schema='rvw.cocotb/1',name='declared_ready_valid',backend='verilator',top=spec['top'],
                  sources=sources,test_module='test_generated',python_paths=['.'],requires=['timer'])
    (out/'bench.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (out/'README.md').write_text('Project-declared ready/valid pyuvm skeleton.\nSupply clock/reset and checked stimulus in scenario.py.\nNo CPU or memory transaction verification is inferred.\n')
    return dict(status='skeleton',out=str(out),manifest=str(out/'bench.json'),
                profile='ready_valid',scenario_required=True,agents=spec['buses'])
