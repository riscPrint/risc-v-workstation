"""Keep the generated example's check selection explicit and bounded."""
import json
from pathlib import Path


def test_generated_vex_plan_selects_fast_instruction_engines():
    root=Path(__file__).resolve().parents[2]
    plan=json.loads((root/'examples/vexriscv/formal/binding.json').read_text())
    checks=plan['checks']
    assert len(checks)==44 and len(set(checks))==44
    for name in checks:
        if name.startswith('insn_'):
            assert plan['check_options'][name]['engine']=='abc bmc3'
            assert plan['check_options'][name]['cycles']==[20]
    for name in ('reg_ch0','pc_fwd_ch0','pc_bwd_ch0','causal_ch0','liveness_ch0','unique_ch0','cover'):
        assert name in checks
    assert 'VEXRISCV_FAIRNESS' not in str(plan)
