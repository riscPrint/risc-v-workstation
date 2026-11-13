#!/usr/bin/env python3
"""Prepare RAM and register-vector configurations of the real Spinal FIFO."""
import argparse
import json
from pathlib import Path
import subprocess

EXPORT = '''import spinal.core._
import spinal.lib._
class MemoryFifo extends Component {
 val push_valid,pop_ready,flush = in Bool()
 val push_payload = in Bits(8 bits)
 val push_ready,pop_valid = out Bool()
 val pop_payload = out Bits(8 bits)
 val occupancy,availability = out UInt(3 bits)
 val fifo = new StreamFifo(Bits(8 bits),4,withAsyncRead=true,useVec=false)
 fifo.io.push.valid := push_valid
 fifo.io.push.payload := push_payload
 push_ready := fifo.io.push.ready
 fifo.io.pop.ready := pop_ready
 pop_valid := fifo.io.pop.valid
 pop_payload := Mux(fifo.io.pop.valid, fifo.io.pop.payload, B(0,8 bits))
 fifo.io.flush := flush
 occupancy := fifo.io.occupancy
 availability := fifo.io.availability
}
object Export extends App {
 SpinalConfig(targetDirectory=args(0), defaultConfigForClockDomains=ClockDomainConfig(resetKind=SYNC)).generateVerilog(new MemoryFifo)
}
'''


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def commit(root, message):
    git(root, 'add', '.')
    git(root, 'commit', '-qm', message)
    return git(root, 'rev-parse', 'HEAD')


def prepare(out, workstation):
    out.mkdir(parents=True, exist_ok=False)
    generator = out / 'generator'
    generator.mkdir()
    git(generator, 'init', '-q')
    build = generator / 'build.py'
    build.write_text('''import os, pathlib, subprocess, sys
out = pathlib.Path(sys.argv[sys.argv.index('--rtl') + 1]).resolve()
subprocess.run([os.environ['RVW_HOME'] + '/scripts/with-lock.sh', 'sbt-equiv',
 'nice', '-n', '10', 'sbt', '-batch', '-J-Xmx2g', '-J-XX:ActiveProcessorCount=2',
 '-Dsbt.offline=true', 'runMain Export ' + str(out)],
 cwd=os.environ['EQUIV_SOURCE'], check=True)
''')
    commit(generator, 'build: export private fifo configurations')
    repo = out / 'unit'
    (repo / 'src/main/scala').mkdir(parents=True)
    (repo / 'project').mkdir()
    git(repo, 'init', '-q')
    (repo / '.gitignore').write_text('target/\nproject/target/\nproject/project/\n')
    (repo / 'project/build.properties').write_text('sbt.version=1.10.7\n')
    (repo / 'build.sbt').write_text('''scalaVersion := "2.13.14"
val spinalVersion = "1.15.0"
libraryDependencies ++= Seq(
 "com.github.spinalhdl" %% "spinalhdl-core" % spinalVersion,
 "com.github.spinalhdl" %% "spinalhdl-lib" % spinalVersion,
 "com.github.spinalhdl" %% "spinalhdl-sim" % spinalVersion,
 compilerPlugin("com.github.spinalhdl" %% "spinalhdl-idsl-plugin" % spinalVersion))
fork := true
''')
    (repo / 'rvw.toml').write_text(f'''[core]
name="fifo-memory"
adapter="false"
source_repo="."
source_env="EQUIV_SOURCE"
lock="vex-equiv"
[query]
build={json.dumps([str(workstation / 'rvw/.venv/bin/python'), str(build)])}
[formal]
export_dependencies={json.dumps([str(generator)])}
''')
    exporter = repo / 'src/main/scala/Export.scala'
    exporter.write_text(EXPORT)
    gold = commit(repo, 'test: capture real memory-backed fifo')
    exporter.write_text(EXPORT.replace('useVec=false', 'useVec=true'))
    gate = commit(repo, 'test: replace fifo memory with register vector')
    cases = {'fifo': {'project': str(repo / 'rvw.toml'), 'gold': gold,
                      'gate': gate, 'top': 'MemoryFifo'}}
    (out / 'cases.json').write_text(json.dumps(cases, indent=2) + '\n')
    return cases


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.out.resolve(), Path(__file__).resolve().parents[3]), indent=2))
