"""Prepare a project-owned live SV VexRiscv bench with captured Spike inputs."""
import argparse
import json
import shutil
from pathlib import Path
from rvw.common.capture import Capture
from rvw.common.proc import run_group
from rvw.cosim.elf import Elf
from rvw.cosim.spike import FIELDS, capture_shim


def prepare(out, shim, rtl):
    out, shim, rtl = map(lambda p: Path(p).resolve(), (out, shim, rtl))
    out.mkdir(parents=True, exist_ok=False)
    here = Path(__file__).resolve().parent
    root = here.parents[3]
    elf_path = out/'program.elf'
    result = run_group(['/opt/homebrew/opt/riscv-gnu-toolchain/bin/riscv64-unknown-elf-gcc',
        '-nostdlib', '-march=rv32im_zicsr', '-mabi=ilp32', '-Wl,--no-relax',
        '-Wl,-T,'+str(here.parent/'program.ld'), str(here/'program.S'), '-o', str(elf_path)],
        capture=True, timeout=30)
    if result.returncode or result.timed_out:
        raise ValueError('program build failed: '+result.stderr)
    elf = Elf(elf_path)
    image = out/'image.txt'
    image.write_text(''.join(f'{address+i:x} {byte:x}\n'
        for address,data,memsz in elf.segments for i,byte in enumerate(data)))
    shutil.copyfile(rtl, out/'VexTop.v')
    capture = Capture(out/'capture')
    captured = capture_shim(capture, shim)
    (out/'spike_effect.h').write_text('#include <cstdint>\nstruct Effect {\n'+''.join(
        f'uint64_t {field};\n' for field in FIELDS)+'uint64_t regs[32]; char disasm[256];\n};\n')
    args = [json.dumps(captured['library']['copy']), json.dumps(captured['source']['sha256']),
            json.dumps(captured['manifest_data']['build_id']), '"rv32im_zicsr_zifencei_zicntr_zihpm"',
            '"M"', '32', '0', '1', '1', "64'h80000000", '16777216', "64'h80000000", json.dumps(str(image)), '4']
    (out/'spike_setup.svh').write_text('''
 import "DPI-C" function int rvw_uvm_init(input string lib, source_hash, build_hash,
 input string isa, modes, input int unsigned bits, pmp, input int absent_zero, align,
 input longint unsigned base, size, pc, input string image, input longint unsigned grain);
 initial begin
  if(rvw_uvm_init('''+','.join(args)+''')!=0) $fatal(1,"Spike init: %s",rvw_uvm_error());
  ram=new("memory");
  uvm_config_db#(cpu_memory)::set(null,"uvm_test_top.env","memory",ram);
  uvm_config_db#(virtual rvw_cpu_if)::set(null,"*","vif",bus);
  run_test("vex_program");
 end
''')
    binding = json.loads((here.parent/'bindings.json').read_text())['fields']
    pins = dict(clk='clk', reset='!bus.reset_n', timerInterrupt="1'b0", softwareInterrupt="1'b0",
        externalInterrupt="1'b0", iBus_cmd_ready='i_ready', iBus_rsp_valid='i_valid',
        iBus_rsp_payload_error='i_error', iBus_rsp_payload_inst='i_data',
        dBus_cmd_ready='d_ready', dBus_rsp_ready='d_valid', dBus_rsp_error='d_error', dBus_rsp_data='d_data')
    # All unconnected outputs remain observable through the instance.
    (out/'core_binding.svh').write_text('VexTop core('+','.join(f'.{k}({v})' for k,v in pins.items())+');\n'
        +'always_comb begin\n bus.rvfi_valid=core.rvfi_valid; bus.rvfi_order=core.rvfi_order;\n'
        +' bus.state_valid=0; bus.csr_count=0;\n'
        +''.join(f' bus.retirement[{i}]='+('0' if name=='mem_fault' else 'core.'+binding[name])+';\n'
           for i,name in enumerate('pc pc_next insn mode rd rd_wdata mem_addr mem_rmask mem_wmask mem_rdata mem_wdata trap mem_fault rs1 rs1_rdata rs2 rs2_rdata intr halt'.split()))
        +' if($test$plusargs("corrupt")) bus.retirement[1]^=4;\nend\n')
    dependencies = [p for p in out.rglob('*') if p.is_file()]
    manifest = dict(schema='rvw.uvm/1', name='vex_sv_cpu', top='top', tests=['vex_program'],
        sources=[str(root/'Uvm/cpu/rvw_cpu_if.sv'), str(root/'Uvm/cpu/rvw_cpu_pkg.sv'),
                 str(out/'VexTop.v'), str(here/'top.sv'), str(root/'Uvm/spike_bridge.cpp')],
        include_dirs=[str(out)], build_args=['-CFLAGS','-I'+str(out), '-MAKEFLAGS','OPT_FAST=-O0 OPT_SLOW=-O0'],
        native_dependencies=[str(out),str(here/'program.S'),str(here.parent/'program.ld'),
            captured['source']['source'], captured['dependency']['source']],
        plusargs=['+image='+str(image), '+tohost='+hex(elf.symbols['tohost'])])
    (out/'bench.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return out/'bench.json'


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--shim',type=Path,required=True)
    p.add_argument('--rtl',type=Path,required=True)
    a=p.parse_args()
    print(prepare(a.out,a.shim,a.rtl))
