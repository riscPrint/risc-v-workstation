"""Expose exact database-local RTL signals before building app wrappers."""
import json
from pathlib import Path
from rvw.common.proc import run_group


def expose(plan, files, out, capture, timeout):
    from .apps import ident
    names = plan.get('internal_ports', {})
    if not names:
        return files
    top = ident(plan['top'])
    for name in names:
        ident(name)
    out.mkdir(parents=True, exist_ok=False)
    yosys = capture.tool('yosys')
    source, metadata = out/'exposed.v', out/'exposed.json'
    script = ['read_verilog -formal -sv ' + ' '.join(json.dumps(str(p)) for p in files), f'prep -top {top} -flatten']
    for name in names:
        script += [f'select -assert-count 1 {top}/w:{name}', f'expose {top}/w:{name}']
    script += ['select *', 'write_json ' + json.dumps(str(metadata)), 'write_verilog -noattr ' + json.dumps(str(source))]
    proc = run_group([str(yosys.path), '-Q', '-T', '-p', '; '.join(script)], capture=True, timeout=timeout)
    (out/'export.log').write_text((proc.stdout or '') + (proc.stderr or ''))
    if proc.returncode:
        raise ValueError('internal signal exposure failed; see export.log')
    ports = json.loads(metadata.read_text())['modules'][top]['ports']
    for name,width in names.items():
        if name not in ports or ports[name]['direction'] != 'output' or len(ports[name]['bits']) != width:
            raise ValueError('internal signal width or direction differs from database: ' + name)
    return [source]
