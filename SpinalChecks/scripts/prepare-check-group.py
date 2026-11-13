#!/usr/bin/env python3
"""Assert a generated check and its helper invariants in one portfolio job."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re


def module(name):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(name+'.py'))
    result=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def prepare(rtl,inventory,out,check_id,helper_ids=None,depth=8):
    data=json.loads(Path(inventory).read_text())
    records={c['id']:c for c in data['checks']}
    primary=records[check_id]
    if helper_ids is None:
        kind,_,name=check_id.partition(':')
        implied={'csr.read':['csr.state'],'queue.order':['queue.capacity','queue.occupancy']}
        helper_ids=[kind+':'+name for kind in implied.get(kind,[]) if kind+':'+name in records]
    helper_ids=list(dict.fromkeys(helper_ids))
    if check_id in helper_ids:
        raise ValueError('primary check cannot also be a helper')
    helpers=[records[key] for key in helper_ids]
    for helper in helpers:
        if (helper['status']!='inserted' or helper.get('path')!=primary.get('path') or
            helper.get('module')!=primary.get('module') or helper.get('clock_domain')!=primary.get('clock_domain')):
            raise ValueError('helpers must be inserted in the same module instance and clock domain')
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_$]*',helper['fail_signal'].split('.')[-1]):
            raise ValueError('helper must have a local fail signal')
    out=Path(out)
    module('prepare-connected-formal').prepare(rtl,inventory,out,[check_id],depth=depth,mode='prove')
    directory=out/'0'
    ports=[f'helper_{n}' for n in range(len(helpers))]
    connections=', '.join('.'+p+'('+h['fail_signal'].split('.')[-1]+')' for p,h in zip(ports,helpers))
    if helpers:
        for source in directory.glob('*.v'):
            text=source.read_text().replace('rvw_selected_check_instance(',
                'rvw_selected_check_instance('+connections+', ')
            source.write_text(text)
        for filename in ('monitor.sv','activation.sv'):
            file=directory/filename
            if not file.exists():continue
            text=file.read_text().replace('input clk, reset_active, fail)',
                'input clk, reset_active, fail, '+', '.join(ports)+')')
            if filename=='monitor.sv':
                statements=''.join('always @(posedge clk) if (!reset_active) assert(!'+p+');\n' for p in ports)
                text=text.replace('endmodule',statements+'endmodule')
            file.write_text(text)
    # The regress runner intentionally requires one assertion. Groups go through
    # the portfolio, which retains and proves every helper assertion too.
    manifest=out/'regress.toml'
    text=manifest.read_text().replace('requirements = ['+json.dumps(check_id)+']',
                                     'requirements = '+json.dumps([check_id,*helper_ids]))
    (out/'group.toml').write_text(text)
    manifest.unlink()
    result=dict(schema='rvw.check-proof-group/1',primary=check_id,helpers=helper_ids,
                assertions=1+len(helpers),all_asserted=True,
                inventory_sha256=hashlib.sha256(Path(inventory).read_bytes()).hexdigest(),
                limitations=['Every helper is asserted, never assumed. Preparation is not proof.',
                             'Use the engine portfolio; the single-assertion regress guard rejects groups.'])
    (out/'group.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rtl',type=Path,required=True)
    p.add_argument('--inventory',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--check-id',required=True)
    p.add_argument('--helper-id',action='append')
    p.add_argument('--depth',type=int,default=8)
    p.add_argument('--timeout',type=float,default=20)
    a=p.parse_args()
    print(json.dumps(prepare(a.rtl,a.inventory,a.out,a.check_id,a.helper_id,a.depth),indent=2))
    print(json.dumps(module('export-portfolio').export(a.out,a.timeout,'group.toml'),indent=2))
