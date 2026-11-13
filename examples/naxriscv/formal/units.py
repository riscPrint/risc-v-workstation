#!/usr/bin/env python3
"""Export pinned Nax arithmetic helpers and prove explicitly confirmed bindings.

These are standalone helper configurations. Core pipeline control is not checked.
All native steps use private locks, nice 10, and a two-minute maximum budget.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from rvw.common.proc import run_group


def component_source(name, text):
    if name == 'DivRadix4.scala':
        if 'object DivRadix4Tester' not in text:
            raise ValueError('divider simulation boundary changed')
        return text.split('object DivRadix4Tester',1)[0].replace('import naxriscv.Global','')
    if name != 'Misc.scala':
        raise ValueError('unknown helper source')
    return ('package naxriscv.utilities\nimport spinal.core._\nimport spinal.lib._\n'
            'import scala.collection.mutable\nimport scala.collection.mutable.ArrayBuffer\n'
            +text[text.index('object MulSpliter'):text.index('  //Here is an example of usage.')]
            +'}\n')


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--widths', default='8,16,32')
    p.add_argument('--timeout', type=float, default=60)
    a = p.parse_args()
    if not 0 < a.timeout <= 120: p.error('timeout must be in 0..120 seconds')
    widths = [int(x) for x in a.widths.split(',')]
    if not widths or set(widths) - {8,16,32}: p.error('widths must be 8,16,32')
    root = Path(__file__).resolve().parents[3]
    out = a.out.resolve(); out.mkdir(parents=True, exist_ok=False)
    source = a.source.resolve()
    revision = subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'], text=True).strip()
    build = out/'generator'; (build/'src/main/scala').mkdir(parents=True); (build/'project').mkdir()
    ledger = dict(schema='rvw.nax-datapath/1', source_revision=revision, spinal_version='1.15.0',
                  scope='real arithmetic helper source; parameterized standalone configurations; no core pipeline proof',
                  source_files={}, cases=[])
    for name in ('DivRadix4.scala','Misc.scala'):
        relative='src/main/scala/naxriscv/utilities/'+name
        raw=subprocess.check_output(['git','-C',str(source),'show',revision+':'+relative])
        text=raw.decode()
        text=component_source(name, text)
        (build/'src/main/scala'/name).write_text(text)
        ledger['source_files'][relative]=dict(sha256=hashlib.sha256(raw).hexdigest(),selected_sha256=hashlib.sha256(text.encode()).hexdigest())
    (build/'project/build.properties').write_text('sbt.version=1.10.7\n')
    (build/'build.sbt').write_text('''scalaVersion := "2.12.18"
val v="1.15.0"
libraryDependencies ++= Seq("core","lib","sim").map(n => "com.github.spinalhdl" %% ("spinalhdl-"+n) % v)
libraryDependencies += compilerPlugin("com.github.spinalhdl" %% "spinalhdl-idsl-plugin" % v)
fork := true
''')
    (build/'src/main/scala/Export.scala').write_text('''import spinal.core._
import spinal.lib._
import naxriscv.utilities._
import scala.collection.mutable
class NaxMul(w:Int) extends Component {
 val a,b=in Bits(w bits); val y=out Bits(w bits)
 val aa=False ## a; val bb=False ## b
 val splits=MulSpliter(w+1,w+1,17,17,true,true)
 val values=splits.map(_.toMulU(aa,bb,w*2))
 var sources=splits.map(s=>AdderAggregator.Source(s,w*2)).toList
 val signals=mutable.LinkedHashMap[AdderAggregator.Source,UInt]()
 for((s,v)<-sources.zip(values)) signals(s)=v
 for((width,lanes)<-List((44,8),(1000,1000))) {
  val adders=AdderAggregator(sources,width,lanes)
  val outputs=adders.map(_.craft(signals.toMap))
  sources=adders.map(_.toSource()).toList
  for((s,v)<-sources.zip(outputs)) signals(s)=v
 }
 require(sources.size==1)
 y:=signals(sources.head).resize(w).asBits
 setDefinitionName("NaxMul"+w)
}
object Export extends App {
 for(w<-args(1).split(",").map(_.toInt)) {
  val cfg=SpinalConfig(targetDirectory=args(0)+"/"+w,defaultConfigForClockDomains=ClockDomainConfig(resetKind=SYNC))
  cfg.generateVerilog(new NaxMul(w))
  cfg.generateVerilog(new DivRadix4(w))
 }
}
''')
    def execute(command, log, timeout, cwd=None, lock='vex-equiv'):
        r=run_group([str(root/'scripts/with-lock.sh'),lock,'nice','-n','10',*command],cwd=cwd,timeout=timeout,capture=True)
        log.write_text((r.stdout or '')+(r.stderr or ''))
        return r
    r=execute(['sbt','-batch','-J-Xmx2g','-J-XX:ActiveProcessorCount=2','-Dsbt.offline=true',
               'runMain Export '+str(out/'rtl')+' '+a.widths],out/'export.log',120,build,'sbt-equiv')
    if r.returncode:
        ledger['export']='inconclusive';(out/'summary.json').write_text(json.dumps(ledger,indent=2)+'\n');return 3
    for w in widths:
        for op in ('mul','divu'):
            case=out/f'{op}{w}';case.mkdir()
            if op=='mul':
                top=f'NaxMul{w}';rtl=(out/f'rtl/{w}/{top}.v').read_text();latency=[]
            else:
                top=f'NaxDiv{w}';rtl=(out/f'rtl/{w}/DivRadix4.v').read_text()
                rtl+=f'''\nmodule {top}(input clk,reset,start,input [{w-1}:0] a,b,output [{w-1}:0] y,output done);
wire [{w+2}:0] q; wire [{w}:0] r;
DivRadix4 unit0(.clk(clk),.reset(reset),.io_flush(reset),.io_cmd_valid(start),.io_cmd_ready(),
 .io_cmd_payload_a(a),.io_cmd_payload_b(b),.io_rsp_valid(done),.io_rsp_ready(1'b1),
 .io_rsp_payload_result(q),.io_rsp_payload_remain(r));
assign y=q[{w-1}:0]; endmodule\n'''
                latency=['--max-latency',str(w//2+4)]
            (case/'dut.v').write_text(rtl)
            model=root/f'SpinalChecks/c2rtl/models/{op}{w}.c'
            # The immutable model includes its shared header. Keep both in the supplied source.
            text=model.read_text().replace('#include "riscv_m.h"','')
            (case/'model.c').write_text((model.parent/'riscv_m.h').read_text()+text)
            r=execute([str(root/'rvw/.venv/bin/rvw'),'query','build-hdl',str(case/'dut.v'),'--top',top,'--out',str(case/'design.db')],case/'db.log',60)
            if r.returncode:
                ledger['cases'].append(dict(operation=op,width=w,status='inconclusive',reason='database export failed'));continue
            r=execute([str(root/'rvw/.venv/bin/rvw'),'formal','datapath','--unit',op,'--component','',
                       '--db',str(case/'design.db'),'--rtl',str(case/'dut.v'),'--model',str(case/'model.c'),
                       '--width',str(w),'--confirm','--timeout',str(a.timeout),'--out',str(case/'confirmed'),*latency,'--json'],case/'proof.log',a.timeout+5)
            report=case/'confirmed/proof/result.json'
            data=json.loads(report.read_text()) if report.exists() else {}
            ledger['cases'].append(dict(operation=op,width=w,status=data.get('status','inconclusive'),reason=data.get('reason'),
                                        wall_s=data.get('wall_s'),rtl_sha256=hashlib.sha256(rtl.encode()).hexdigest()))
            (out/'summary.json').write_text(json.dumps(ledger,indent=2)+'\n')
    (out/'summary.json').write_text(json.dumps(ledger,indent=2)+'\n')
    print(json.dumps(ledger,indent=2))
    return 0 if ledger['cases'] and all(c['status']=='proved' for c in ledger['cases']) else 3


if __name__=='__main__':
    raise SystemExit(main())
