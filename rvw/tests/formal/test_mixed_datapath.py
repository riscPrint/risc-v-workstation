import importlib.util
import json
import os
from pathlib import Path
import shutil
import pytest
from rvw.cli import main
from rvw.formal.datapath_binding import bind

ROOT=Path(__file__).resolve().parents[3]/'SpinalChecks/c2rtl'
TOOLS=all(shutil.which(t) for t in ('yosys','cbmc'))


def softfloat(operation):
    root=os.environ.get('RVW_TEST_SOFTFLOAT')
    if not root:pytest.skip('set RVW_TEST_SOFTFLOAT to the pinned external source tree')
    spec=importlib.util.spec_from_file_location('softfloat_bindings',ROOT/'softfloat.py')
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    return helper.prepare(root,operation)


@pytest.mark.skipif(not TOOLS,reason='needs Yosys and CBMC')
@pytest.mark.parametrize('bad_reference',[False,True])
def test_narrow_input_uses_free_upper_reference_bits(tmp_path,bad_reference):
    rtl=tmp_path/'dut.v';rtl.write_text('module Unit(input [15:0] operand,output [15:0] result);assign result=~operand;endmodule')
    model=tmp_path/'ref.c';model.write_text('uint64_t reference(uint64_t a,uint64_t b,uint64_t c,uint8_t rm,uint8_t *flags){return '+('~a' if bad_reference else '(~a)&65535')+';}')
    binding=tmp_path/'bind.json';binding.write_text(json.dumps({'top':'Unit','ports':{'a':'operand','y':'result'},
        'unused_inputs':{'b':64},'input_widths':{'a':64},'output_widths':{'y':64}}))
    out=tmp_path/'out'
    main(['formal','datapath','--rtl',str(rtl),'--model',str(model),'--binding',str(binding),'--width','64','--out',str(out)])
    result=json.loads((out/'result.json').read_text())
    assert result['status']==('counterexample' if bad_reference else 'proved'),result


@pytest.mark.skipif(not TOOLS,reason='needs Yosys and CBMC')
@pytest.mark.parametrize('kind,mutant',[('all',False),('normal',False),('subnormal',False),('nan',True)])
def test_f32_to_f64_mixed_interface_and_source_cases(tmp_path,kind,mutant):
    dependencies=softfloat('f32_to_f64')
    rtl=tmp_path/'dut.v'
    rtl.write_text('''module Convert(input [31:0] operand,output reg [63:0] result,output reg [4:0] flags);
wire sign=operand[31];wire [7:0] exponent=operand[30:23];wire [22:0] fraction=operand[22:0];
reg [10:0] wide_exponent;reg [51:0] wide_fraction;integer p,i;
always @* begin p=0;i=0;wide_exponent=0;wide_fraction=0;flags=0;
 if(exponent==255)begin wide_exponent=2047;end
 else if(exponent!=0)begin wide_exponent=exponent+11'd896;wide_fraction={fraction,29'b0};end
 else if(fraction!=0)begin
  for(i=0;i<23;i=i+1)if(fraction[i])p=i;
  wide_exponent=11'd874+p;wide_fraction=({41'b0,fraction}<<(52-p));
 end
 result={sign,wide_exponent,wide_fraction};
 if(exponent==255 && fraction!=0)begin result=64'h7ff8000000000000;flags={(!fraction[22]),4'b0};end
end endmodule'''.replace("flags={(!fraction[22]),4'b0}","flags=0" if mutant else "flags={(!fraction[22]),4'b0}"))
    binding=tmp_path/'bind.json';binding.write_text(json.dumps({'top':'Convert','ports':{'a':'operand','y':'result','flags':'flags'},
        'unused_inputs':{'b':64},'input_widths':{'a':64}}))
    out=tmp_path/'out'
    main(['formal','datapath','--rtl',str(rtl),'--model',str(ROOT/'models/f32_to_f64.c'),'--binding',str(binding),
          '--width','64','--case-width','32','--case',kind,*dependencies,'--timeout','60','--out',str(out)])
    result=json.loads((out/'result.json').read_text())
    assert result['status']==('counterexample' if mutant else 'proved' if kind=='all' else 'partial'),result
    assert result['case_width']==32 and result['width']==64


@pytest.mark.skipif(not TOOLS,reason='needs Yosys and CBMC')
def test_one_bit_fp_compare_output_can_use_word_reference(tmp_path):
    dependencies=softfloat('f32_eq')
    rtl=tmp_path/'dut.v';rtl.write_text('module Compare(input [31:0] a,b,output y,output [4:0] flags); '
        'wire na=(&a[30:23]) && (|a[22:0]);wire nb=(&b[30:23]) && (|b[22:0]);'
        'assign y=!(na|nb) && ((a==b) || (a[30:0]==0 && b[30:0]==0));'
        'assign flags={(na && !a[22]) || (nb && !b[22]),4\'b0};endmodule')
    binding=tmp_path/'bind.json';binding.write_text(json.dumps({'top':'Compare','ports':{},'output_widths':{'y':32}}));out=tmp_path/'out'
    main(['formal','datapath','--rtl',str(rtl),'--model',str(ROOT/'models/f32_eq.c'),'--binding',str(binding),
          '--width','32',*dependencies,'--timeout','60','--out',str(out)])
    result=json.loads((out/'result.json').read_text());assert result['status']=='proved',result


def test_padding_refuses_truncation_and_control_width_changes():
    design={'modules':{'Unit':{'ports':{'a':{'direction':'input','bits':list(range(1,33))},'y':{'direction':'output','bits':[40]}},'cells':{},'netnames':{}}}}
    with pytest.raises(ValueError,match='truncation'):bind(design,{'top':'Unit','ports':{},'input_widths':{'a':16}})
    with pytest.raises(ValueError):bind(design,{'top':'Unit','ports':{},'input_widths':{'clk':32}})
