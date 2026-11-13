"""Proof boundaries must reject a changed state or partial-product interface."""
from copy import deepcopy
from pathlib import Path
import runpy
import pytest

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[3]
product = runpy.run_path(str(ROOT/'examples/vexiiriscv/formal/mul-composition.py'))['products']
step = runpy.run_path(str(ROOT/'examples/naxriscv/formal/step-invariant.py'))


def multiplier():
    a=list(range(2,35)); b=list(range(35,68)); cells={}
    specs={'ll':(a[:17],b[:17],0,34),
           'lh':(a[:17]+['0']*17,b[17:]+[b[-1]]*18,1,34),
           'hl':(a[17:]+[a[-1]]*18,b[:17]+['0']*17,1,34),
           'hh':(a[17:]+[a[-1]]*16,b[17:]+[b[-1]]*16,1,32)}
    for role,(aa,bb,signed,w) in specs.items():
        cells[role]={'type':'$mul','connections':{'A':aa,'B':bb,'Y':list(range(100,100+w))},
                     'parameters':{'A_SIGNED':str(signed),'B_SIGNED':str(signed)}}
    return {'ports':{'a':{'bits':a},'b':{'bits':b},'y':{'bits':list(range(64))}},'cells':cells}


def test_partial_products_require_exact_slices_and_signedness():
    m=multiplier(); assert set(product(m))=={'ll','lh','hl','hh'}
    m['cells']['lh']['connections']['A'][0]='0'
    with pytest.raises(ValueError,match='binding'): product(m)
    m=multiplier();m['cells']['hh']['parameters']['A_SIGNED']='0'
    with pytest.raises(ValueError,match='binding'): product(m)


def state_design():
    widths=dict(counter=2,busy=1,done=1,shifter=8,numerator=8,result=8,div1=10,div3=10)
    mod={'ports':{'clk':{'direction':'input','bits':[1]}},'netnames':{},'cells':{}}
    at=2
    for name,width in widths.items():
        q=list(range(at,at+width)); at+=width
        d=list(range(at,at+width)); at+=width
        mod['netnames'][name]={'bits':q,'attributes':{'init':'0'}}
        mod['cells'][name]={'type':'$dff','parameters':{'CLK_POLARITY':'1'},'connections':{'Q':q,'D':d,'CLK':[1]}}
    return {'modules':{'DivRadix4':mod}}


def test_every_state_cell_must_be_accounted_for():
    design=state_design(); extra=deepcopy(design['modules']['DivRadix4']['cells']['busy'])
    design['modules']['DivRadix4']['cells']['extra']=extra
    with pytest.raises(ValueError): step['cut_state'](design,8)
    design=state_design();step['cut_state'](design,8)
    mod=design['modules']['DivRadix4']
    assert not mod['cells']
    assert set(mod['ports'])-{'clk'}=={'state_'+n for n in step['NAMES']} | {'next_'+n for n in step['NAMES']}


def test_state_cut_refuses_another_clock():
    design=state_design()
    design['modules']['DivRadix4']['cells']['result']['connections']['CLK']=[999]
    with pytest.raises(ValueError,match='public rising-edge'):
        step['cut_state'](design,8)


def test_prefix_certificate_checks_each_counter_value():
    text=step['prefix_lemmas'](32)
    assert text.count('(check-sat)')==48
    assert '(_ bv32 32)' in text and '(_ bv30 32)' in text
