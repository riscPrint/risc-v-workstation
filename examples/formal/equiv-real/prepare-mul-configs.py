#!/usr/bin/env python3
"""Prepare two private Vexii multiplier configurations for revision equivalence."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def commit(root, message):
    git(root, 'add', '.')
    git(root, 'commit', '-qm', message)
    return git(root, 'rev-parse', 'HEAD')


def prepare(out, source, workstation):
    revision = git(source, 'rev-parse', 'HEAD')
    path = 'src/main/scala/vexiiriscv/misc/Utils.scala'
    raw = subprocess.check_output(['git', '-C', str(source), 'show', revision + ':' + path])
    marker = 'case class AgedArbiterUp'
    if raw.decode().count(marker) != 1:
        raise ValueError('utility source boundary changed')
    component = raw.decode().split(marker, 1)[0]
    spec = importlib.util.spec_from_file_location(
        'mul_unit', workstation / 'examples/vexiiriscv/formal/mul-unit.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    code = module.GENERATOR
    for old, new in (
        ('val a,b = in Bits(33 bits)', 'val a,b = in Bits(8 bits)\n'
         ' val clk,reset = in Bool()\n'
         ' val aa = a.asSInt.resize(33).asBits\n'
         ' val bb = b.asSInt.resize(33).asBits'),
        ('_.toMulU(a,b,64)', '_.toMulU(aa,bb,64)'),
    ):
        if code.count(old) != 1:
            raise ValueError('multiplier generator changed')
        code = code.replace(old, new)
    split = 'MulSpliter(33,33,17,17,true,true)'
    if code.count(split) != 1:
        raise ValueError('multiplier split configuration changed')
    out.mkdir(parents=True, exist_ok=False)
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
    (repo / 'src/main/scala/Utils.scala').write_text(component)
    exporter = repo / 'src/main/scala/Export.scala'
    exporter.write_text(code)
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
    commit(generator, 'build: export private multiplier configurations')
    # These local absolute paths point to private repositories. Public receipts
    # replace them with run-root placeholders.
    (repo / 'rvw.toml').write_text(f'''[core]
name="mul-config"
adapter="false"
source_repo="."
source_env="EQUIV_SOURCE"
lock="vex-equiv"
[query]
build={json.dumps([str(workstation / 'rvw/.venv/bin/python'), str(build)])}
[formal]
export_dependencies={json.dumps([str(generator)])}
''')
    (repo / 'provenance.json').write_text(json.dumps({
        'source_revision': revision, 'source_path': path,
        'source_sha256': hashlib.sha256(raw).hexdigest(),
        'component_sha256': hashlib.sha256(component.encode()).hexdigest(),
        'word_inputs': 8, 'internal_operands': 33, 'result_bits': 64,
        'scope': 'signed byte operands; real multiplication helpers; no pipeline',
    }, indent=2) + '\n')
    gold = commit(repo, 'test: use seventeen-bit partial products')
    exporter.write_text(code.replace(split, 'MulSpliter(33,33,9,9,true,true)'))
    gate = commit(repo, 'test: use nine-bit partial products')
    cases = {'mul': {'project': str(repo / 'rvw.toml'), 'gold': gold,
                     'gate': gate, 'top': 'VexiiMul'}}
    (out / 'cases.json').write_text(json.dumps(cases, indent=2) + '\n')
    return cases


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.out.resolve(), args.source.resolve(),
                             Path(__file__).resolve().parents[3]), indent=2))
