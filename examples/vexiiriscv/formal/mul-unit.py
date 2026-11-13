#!/usr/bin/env python3
"""Check the real VexiiRiscv multiplier arithmetic helpers against M models."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from rvw.common.proc import run_group

OPS = ('mul', 'mulh', 'mulhu', 'mulhsu')


def signed_operands(op):
    if op not in OPS:
        raise ValueError('unknown multiplication operation')
    return op != 'mulhu', op in ('mul', 'mulh')


def projection(name, signed, bits):
    if not 1 <= bits <= 32:
        raise ValueError('operand bits must be in 1..32')
    if bits == 32:
        return name
    return ("{{%d{%s[%d]}},%s[%d:0]}" % (32-bits,name,bits-1,name,bits-1)) if signed else f"({name} & 32'h{(1 << bits)-1:x})"


def adapter(op, bits):
    sa, sb = signed_operands(op)
    a, b = projection('a', sa, bits), projection('b', sb, bits)
    aa = '{' + ('a[31]' if sa and bits == 32 else f'a[{bits-1}]' if sa else "1'b0") + ',' + a + '}'
    bb = '{' + ('b[31]' if sb and bits == 32 else f'b[{bits-1}]' if sb else "1'b0") + ',' + b + '}'
    result = 'product[31:0]' if op == 'mul' else 'product[63:32]'
    return f"""module dut(input [31:0] a,b,output [31:0] y);
wire [63:0] product;
VexiiMul unit0(.a({aa}),.b({bb}),.y(product));
assign y={result};
endmodule
"""


def model(root, op, bits):
    sa, sb = signed_operands(op)
    projection('a', sa, bits)
    def expr(name, signed):
        if bits == 32:
            return name
        # Cast through the projected sign bit, then extend to the model word.
        if signed:
            return f'((uint64_t)(int64_t)((int32_t)({name} << {32-bits}) >> {32-bits}))'
        return f'({name} & {(1 << bits)-1}ULL)'
    models = root / 'SpinalChecks/c2rtl/models'
    text = (models / (op + '32.c')).read_text().replace('#include "riscv_m.h"', '')
    if '32, a, b)' not in text:
        raise ValueError('reference call changed')
    return (models / 'riscv_m.h').read_text() + text.replace('32, a, b)', f'32, {expr("a",sa)}, {expr("b",sb)})')


GENERATOR = """import spinal.core._
import spinal.lib._
import vexiiriscv.misc._
import scala.collection.mutable
class VexiiMul extends Component {
 val a,b = in Bits(33 bits)
 val y = out Bits(64 bits)
 val splits = MulSpliter(33,33,17,17,true,true)
 val values = splits.map(_.toMulU(a,b,64))
 var sources = splits.map(s => AdderAggregator.Source(s,64)).toList
 val signals = mutable.LinkedHashMap[AdderAggregator.Source,UInt]()
 for((s,v) <- sources.zip(values)) signals(s)=v
 for((width,lanes) <- List((44,8),(1000,1000))) {
  val adders = AdderAggregator(sources,width,lanes)
  val outputs = adders.map(_.craft(signals.toMap))
  sources = adders.map(_.toSource()).toList
  for((s,v) <- sources.zip(outputs)) signals(s)=v
 }
 require(sources.size==1)
 y := signals(sources.head).resize(64).asBits
}
object Export extends App {
 SpinalConfig(targetDirectory=args(0)).generateVerilog(new VexiiMul)
}
"""


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--operations', default='mul,mulh,mulhu,mulhsu')
    p.add_argument('--operand-bits', type=int, default=32)
    p.add_argument('--timeout', type=float, default=180)
    a = p.parse_args()
    root = Path(__file__).resolve().parents[3]
    source, out = a.source.resolve(), a.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    revision = subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
    path = 'src/main/scala/vexiiriscv/misc/Utils.scala'
    raw = subprocess.check_output(['git','-C',str(source),'show',revision+':'+path])
    marker = 'case class AgedArbiterUp'
    if marker not in raw.decode():
        raise ValueError('utility source boundary changed')
    component = raw.decode().split(marker,1)[0]
    build = out / 'generator'
    (build/'src/main/scala').mkdir(parents=True)
    (build/'project').mkdir()
    (build/'src/main/scala/Utils.scala').write_text(component)
    (build/'src/main/scala/Export.scala').write_text(GENERATOR)
    (build/'project/build.properties').write_text('sbt.version=1.10.7\n')
    (build/'build.sbt').write_text("""scalaVersion := "2.13.14"
val spinalVersion = "1.15.0"
libraryDependencies ++= Seq(
 "com.github.spinalhdl" %% "spinalhdl-core" % spinalVersion,
 "com.github.spinalhdl" %% "spinalhdl-lib" % spinalVersion,
 "com.github.spinalhdl" %% "spinalhdl-sim" % spinalVersion,
 compilerPlugin("com.github.spinalhdl" %% "spinalhdl-idsl-plugin" % spinalVersion))
fork := true
""")
    manifest = {'schema':'rvw.vexii-mul-unit/1','source_revision':revision,'source_path':path,
                'source_sha256':hashlib.sha256(raw).hexdigest(),
                'component_sha256':hashlib.sha256(component.encode()).hexdigest(),
                'spinal_version':'1.15.0','operand_bits':a.operand_bits,'results':[],
                'scope':'real MulSpliter and AdderAggregator; default 33-bit inputs, 17-bit splits and two sum steps; combinational arithmetic only; no pipeline control'}
    r = run_group([str(root/'scripts/with-lock.sh'),'sbt-equiv','nice','-n','10','sbt','-batch',
                   '-J-Xmx2g','-J-XX:ActiveProcessorCount=2','-Dsbt.offline=true',
                   'runMain Export '+str(out/'rtl')],cwd=build,timeout=180,capture=True)
    (out/'export.log').write_text((r.stdout or '')+(r.stderr or ''))
    manifest['export']={'exit':r.returncode,'timed_out':r.timed_out}
    (out/'summary.json').write_text(json.dumps(manifest,indent=2)+'\n')
    if r.returncode:
        return 3
    rtl=out/'rtl/VexiiMul.v'
    manifest['rtl_sha256']=hashlib.sha256(rtl.read_bytes()).hexdigest()
    for op in a.operations.split(','):
        directory=out/op;directory.mkdir()
        (directory/'dut.v').write_text(rtl.read_text()+adapter(op,a.operand_bits))
        (directory/'model.c').write_text(model(root,op,a.operand_bits))
        r=run_group([str(root/'scripts/with-lock.sh'),'vex-equiv','nice','-n','10',
                     str(root/'rvw/.venv/bin/rvw'),'formal','datapath',
                     '--rtl',str(directory/'dut.v'),'--model',str(directory/'model.c'),
                     '--width','32','--timeout',str(a.timeout),'--out',str(directory/'proof')],
                    timeout=a.timeout+10,capture=True)
        (directory/'proof.log').write_text((r.stdout or '')+(r.stderr or ''))
        result=directory/'proof/result.json'
        report=json.loads(result.read_text()) if result.exists() else {}
        manifest['results'].append({'operation':op,'status':report.get('status','inconclusive'),
                                    'reason':report.get('reason'),'wall_s':report.get('wall_s')})
        (out/'summary.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))
    statuses=[r['status'] for r in manifest['results']]
    return 1 if 'counterexample' in statuses else 0 if statuses and all(s=='proved' for s in statuses) else 3


if __name__ == '__main__':
    raise SystemExit(main())
