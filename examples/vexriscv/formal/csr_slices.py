"""Inventory the pinned export and split implemented CSR addresses into jobs."""
import argparse
import json
from pathlib import Path
import re

from machine_remaining import prepare as capture
from rvw.formal.csr_slices import inventory, prepare, execute


def build(rtl, out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    machine=capture(rtl,out/'capture',depth=25)
    # These are the actual registered address-decode terms in this pinned export.
    # Resolve names through the shared catalog instead of keeping a second list.
    text=Path(rtl).read_text()
    addresses=sorted({int(n) for n in re.findall(r'\breg\s+execute_CsrPlugin_csr_(\d+)\s*;',text)})
    entries=inventory(addresses)
    binding=dict(machine['checks']['csr_consistency'],cone_cuts=['execute_SRC1'])
    machine['sources']=[str((out/'capture/observed.v').resolve())]
    machine.pop('checks')
    observed=out/'capture/observed.v'
    source=observed.read_text()
    # SRC1 is cut, but x0 and immediate operands still obey the decoder contract.
    contract = """
always @* if(!reset && execute_IS_CSR) begin
 if(execute_INSTRUCTION[14]) assume(execute_SRC1 == {27'b0,execute_INSTRUCTION[19:15]});
 else if(execute_INSTRUCTION[19:15] == 0) assume(execute_SRC1 == 0);
end
"""
    observed.write_text(source.replace('endmodule',contract+'\nendmodule',1))
    plan=dict(schema='rvw.csr-slices/1',addresses=addresses,machine=machine,
              bindings={row['csr']:(binding if row['csr']=='mscratch' else dict(
                  unsupported='Needs an independent WARL, hardware-update or read-only binding.')) for row in entries})
    (out/'slices.json').write_text(json.dumps(plan,indent=2)+'\n')
    return plan


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rtl',required=True);p.add_argument('--out',required=True)
    p.add_argument('--run',action='store_true');p.add_argument('--timeout',type=float,default=60)
    a=p.parse_args();plan=build(a.rtl,a.out)
    result=(execute(plan,Path(a.out),Path(a.out)/'jobs',a.timeout) if a.run else
            prepare(plan,Path(a.out),Path(a.out)/'jobs'))
    print(json.dumps(result))
