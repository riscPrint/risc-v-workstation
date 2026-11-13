"""Native unbounded checks of generated monitors against independent fixtures."""
import shutil

import pytest

from rvw.common.proc import run_group
from rvw.formal.simple_bus_checks import render as bus
from rvw.formal.csr import monitor
from rvw.formal.invariants import render as invariant
from rvw.formal.generated_checks import render as generated
from rvw.formal.resource_checks import render as resource

pytestmark = pytest.mark.slow


def fixture(kind, bad):
    if kind in ('csr', 'csr_resetless'):
        obj = dict(xlen=32, csrs=[dict(name='scratch', address=0x340, reset=5,
            privilege='M', fields=[dict(lsb=0, width=32, access=dict(U='RO', S='RO', M='RW'), legal=[], legalize={})])])
        if kind == 'csr_resetless':
            obj['csrs'][0]['reset_known'] = False
        source = monitor(obj).replace('module rvw_csr(', 'module rvw_'+kind+'(')
        ports = f'''wire valid=phase==1, rd=0, wr=1, trap=0;
wire [1:0] privilege=3; wire [11:0] address=12'h340;
wire [31:0] data=9, rdata=0, hw_set=0, hw_clear=0;
wire [31:0] state_scratch=phase<2 ? {7 if kind == 'csr_resetless' else 5} : {8 if bad else 9};'''
    elif kind == 'axis':
        source = bus(kind, 8, 4)
        ports = f'wire valid=phase==1 || phase==2, ready=phase==2; wire [7:0] payload=phase==2 ? {2 if bad else 1} : 1;'
    elif kind == 'apb':
        source = bus(kind, 8, 4)
        ports = f'wire select=phase==1 || phase==2, enable=phase==2, ready=1, error=0; wire [7:0] request=phase==2 ? {2 if bad else 1} : 1;'
    elif kind == 'ahb_lite':
        source = bus(kind, 8, 4)
        ports = f'wire select=1, ready=phase!=1, response_error=0; wire [1:0] transfer=2; wire [7:0] request=phase==2 ? {2 if bad else 1} : 1;'
    elif kind == 'hpm':
        source = generated(kind, 8, 4)
        ports = f'''wire [7:0] observed=phase<2 ? 0 : {2 if bad else 1};
wire [7:0] events=phase==1, write_data=0;
wire inhibit=0, permitted=1, write_accepted=0, clear_pending=0,
irq_enabled=0, pending=0, irq=0;'''
    elif kind == 'initialized_read':
        source = generated(kind, 8, 4)
        ports = f'''wire read_used=phase>=2; wire [7:0] read_mask={2 if bad else 1},
written_mask=phase==1 ? 1 : 0, required_mask=255;'''
    elif kind == 'axi_lite':
        source = generated(kind, 8, 4)
        ports = f'''wire awvalid=phase==1, awready=1, wvalid=phase==2, wready=1,
bvalid=phase==3, bready=1, arvalid=phase==1, arready=1, rvalid=phase==2, rready=1;
wire aw_fire=awvalid, w_fire=wvalid, b_fire=bvalid, ar_fire=arvalid, r_fire=rvalid;
wire [1:0] bresp={1 if bad else 0}, rresp=0;'''
    elif kind == 'allocation_pool':
        source = resource(kind, 3, 4)
        ports = f'''wire [3:0] live=phase==2 ? {0 if bad else 2} : 0;
wire alloc0_valid=phase==1, alloc1_valid=0, free0_valid=phase==2, free1_valid=0;
wire [2:0] alloc0=1, alloc1=0, free0=1, free1=0;'''
    elif kind == 'cam_match':
        source = resource(kind, 3, 4)
        ports = f'wire active=1, require_match=1; wire [3:0] match_bits={3 if bad else 1};'
    elif kind in ('rob', 'credit'):
        source = invariant(kind, 4, 3)
        ports = f'wire push=phase==1, pop=phase==2; wire [2:0] count=phase==2 ? {2 if bad else 1} : 0;'
    elif kind == 'freelist':
        source = invariant(kind, 4, 3)
        ports = f'wire [3:0] free_bits=1, allocated={1 if bad else 2};'
    elif kind == 'rename':
        source = invariant(kind, 4, 3)
        ports = f'wire [3:0] valid=3; wire [11:0] tags={0 if bad else 8};'
    elif kind == 'issue':
        source = invariant(kind, 4, 3)
        ports = f'wire [3:0] issued={3 if bad else 1}, valid=3, ready=3;'
    elif kind == 'lsq':
        source = invariant(kind, 4, 3)
        ports = f'wire load_fire=1, older_store=1, address_match=1, forwarded=1; wire [2:0] load_data={2 if bad else 1}, store_data=1;'
    else:
        source = resource(kind, 3, 4)
        ports = f'wire active=1; wire [2:0] value={5 if bad else 4};'
    return source + f'''module fixture(input clk);
reg [3:0] phase=0;
always @(posedge clk) if(phase<7) phase<=phase+1;
wire reset=phase==0;
{ports}
rvw_{kind} dut(.*);
endmodule
'''


@pytest.mark.parametrize('kind', ['csr', 'csr_resetless', 'hpm', 'initialized_read', 'axi_lite',
                                  'allocation_pool', 'cam_match', 'counter_bounds',
                                  'rob', 'credit', 'freelist', 'rename', 'issue', 'lsq',
                                  'axis', 'apb', 'ahb_lite'])
@pytest.mark.parametrize('bad', [False, True])
def test_generated_proof(tmp_path, kind, bad):
    if not shutil.which('sby') or not shutil.which('yices-smt2'):
        pytest.skip('SBY and Yices required')
    (tmp_path/'fixture.sv').write_text(fixture(kind, bad))
    (tmp_path/'proof.sby').write_text('''[options]
mode prove
depth 12
[engines]
smtbmc yices
[script]
read -formal fixture.sv
prep -top fixture
[files]
fixture.sv
''')
    result = run_group(['nice', '-n', '10', 'sby', '-f', 'proof.sby'],
                       cwd=tmp_path, capture=True, timeout=45)
    status = tmp_path/'proof/status'
    assert status.exists(), result.stdout + result.stderr
    assert status.read_text().split()[0] == ('FAIL' if bad else 'PASS'), result.stdout + result.stderr
