#!/usr/bin/env python3
"""Prepare private, committed Spinal source cases for revision equivalence."""
import argparse
from pathlib import Path
import shutil
import subprocess
import json


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def commit(root, message):
    git(root, 'add', '.')
    git(root, 'commit', '-qm', message)
    return git(root, 'rev-parse', 'HEAD')


def prepare(out, spinal, vex, workstation):
    out.mkdir(parents=True, exist_ok=False)
    generator = out / 'generator'
    generator.mkdir()
    git(generator, 'init', '-q')
    build = generator / 'build.py'
    build.write_text('''import os, pathlib, subprocess, sys
args = sys.argv
rtl = pathlib.Path(args[args.index('--rtl') + 1]).resolve()
source = pathlib.Path(os.environ['EQUIV_SOURCE'])
cmd = [os.environ['RVW_HOME'] + '/scripts/with-lock.sh', 'sbt-equiv', 'nice', '-n', '10',
       'sbt', '-batch', '-J-Xmx2g', '-J-XX:ActiveProcessorCount=2', '-Dsbt.offline=true',
       'runMain RealExport ' + args[1] + ' ' + str(rtl)]
subprocess.run(cmd, cwd=source, check=True)
''')
    commit(generator, 'build: add private revision generator')
    cases = {}
    for name in ('divider', 'sqrt'):
        repo = out / name
        (repo / 'src/main/scala').mkdir(parents=True)
        (repo / 'project').mkdir()
        git(repo, 'init', '-q')
        (repo / 'project/build.properties').write_text('sbt.version=1.10.7\n')
        (repo / '.gitignore').write_text('target/\nproject/target/\nproject/project/\n')
        (repo / 'build.sbt').write_text('''scalaVersion := "2.13.14"
val spinalVersion = "1.15.0"
libraryDependencies ++= Seq(
 "com.github.spinalhdl" %% "spinalhdl-core" % spinalVersion,
 "com.github.spinalhdl" %% "spinalhdl-lib" % spinalVersion,
 "com.github.spinalhdl" %% "spinalhdl-sim" % spinalVersion,
 compilerPlugin("com.github.spinalhdl" %% "spinalhdl-idsl-plugin" % spinalVersion))
fork := true
''')
        src = repo / 'src/main/scala/Unit.scala'
        if name == 'divider':
            path = 'lib/src/main/scala/spinal/lib/math/Divider.scala'
            revision = git(spinal, 'rev-parse', 'HEAD')
            text = git(spinal, 'show', revision + ':' + path) + '\n'
            top = 'UnsignedDivider'
            construct = 'new spinal.lib.math.UnsignedDivider(4,4,true)'
        else:
            path = 'src/main/scala/vexriscv/ip/fpu/FpuSqrt.scala'
            revision = '7445c66b'
            text = git(vex, 'show', revision + ':' + path) + '\n'
            top = 'FpuSqrt'
            construct = 'new vexriscv.ip.fpu.FpuSqrt(4)'
        src.write_text(text)
        (repo / 'src/main/scala/RealExport.scala').write_text(f'''import spinal.core._
object RealExport extends App {{
 SpinalConfig(targetDirectory=args(1), defaultConfigForClockDomains=ClockDomainConfig(resetKind=SYNC)).generateVerilog({construct})
}}
''')
        (repo / 'provenance.json').write_text(json.dumps({'repository':str(spinal if name=='divider' else vex), 'revision':revision, 'path':path}, indent=2)+'\n')
        (repo / 'rvw.toml').write_text(f'''[core]
name="{name}"
adapter="false"
source_repo="."
source_env="EQUIV_SOURCE"
lock="vex-equiv"
[query]
build=["{workstation}/rvw/.venv/bin/python", "{build}"]
[formal]
export_dependencies=["{generator}"]
''')
        gold = commit(repo, 'test: capture upstream module')
        if name == 'divider':
            import re
            updated = re.sub(r'\bdone\s*:=', 'doneNext :=', text)
            updated = re.sub(r'\bwaitRsp\s*:=', 'waitRspNext :=', updated)
            old = '  val done = RegInit(True)\n  val waitRsp = RegInit(False)'
            new = """  val stateCode = Reg(Bits(3 bits)) init(B"001")
  val done = stateCode(0) || stateCode(2)
  val waitRsp = stateCode(2)
  val doneNext = Bool()
  val waitRspNext = Bool()
  doneNext := done
  waitRspNext := waitRsp
  stateCode := Mux(!doneNext, B"010", Mux(waitRspNext, B"100", B"001"))"""
            if old not in updated:
                raise ValueError('upstream divider changed; inspect the refactor')
            src.write_text(updated.replace(old,new))
        else:
            # The component source stays fixed. Compare two RTL export settings.
            exporter = repo / 'src/main/scala/RealExport.scala'
            exporter.write_text(exporter.read_text().replace(
                'targetDirectory=args(1),', 'targetDirectory=args(1), oneFilePerComponent=true,'))
        gate = commit(repo, 'test: capture comparison revision')
        cases[name] = dict(project=str(repo/'rvw.toml'),gold=gold,gate=gate,top=top)
    (out/'cases.json').write_text(json.dumps(cases,indent=2)+'\n')
    return cases


if __name__ == '__main__':
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--spinal', type=Path, required=True)
    p.add_argument('--vex', type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(prepare(a.out.resolve(), a.spinal.resolve(), a.vex.resolve(), Path(__file__).resolve().parents[3]),indent=2))
