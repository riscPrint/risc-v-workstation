"""One independent pyuvm test and DUT reset per selected ISA ELF."""
import json
import os
import re
from pathlib import Path
import pyuvm
from live_test import VexIsa

programs=json.loads(os.environ['RVW_CPU_ISA_PROGRAMS'])
if not programs or len(set(programs))!=len(programs):
    raise ValueError('nonempty unique ISA program list required')
for name in programs:
    if Path(name).name!=name:
        raise ValueError('ISA program names must be beside RVW_CPU_ELF')
    test_name='Isa_'+re.sub(r'\W','_',name)
    globals()[test_name]=pyuvm.test()(type(test_name,(VexIsa,),
        {'program':name,'__module__':__name__}))
