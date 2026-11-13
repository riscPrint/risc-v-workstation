"""Lower pinned Ibex SV for the upstream Verilog-only riscv-formal loader."""
import json, os, subprocess
from pathlib import Path
work=Path(os.environ['IBEX_WORK']).resolve()
spec=json.loads((work/'hdl.json').read_text())
# Let SBY's multiclock flow lower the clocks after the formal wrapper is joined.
args=['read_slang --top ibex_top --ignore-assertions --ignore-initial',
      '-GRV32M=ibex_pkg::RV32MSlow']
args += ['-I'+p for p in spec['include_dirs']]
args += ['-D'+p for p in spec['defines']]
args += spec['sources']
script=' '.join(args)+'\nproc\nopt_clean\nwrite_verilog -noattr '+str(work/'formal-core.v')+'\n'
(work/'formal-export.ys').write_text(script)
with (work/'formal-export.log').open('w') as log:
    subprocess.run(['yosys','-m',os.environ.get('RVW_SLANG','slang'),'-s',str(work/'formal-export.ys')],stdout=log,stderr=log,check=True,timeout=120)
