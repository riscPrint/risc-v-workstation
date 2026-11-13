"""Minimal, fail-closed Spinal core project scaffold."""
import json
from pathlib import Path
import re

import rvw
from .inputs import INPUT_COMMANDS, INPUT_ENV
from .optional import build_files, linker_platform, db_script, sim_script


def scaffold(path='.', *, isa=None, xlen=None, name=None, force=False, dry_run=False, wire_build=False, sbt_project=None,
             linker_script=None, ram_region=None, reset_pc=None, db_top=None):
    root = Path(path).resolve()
    if not root.is_dir() or not (root / 'build.sbt').is_file():
        raise ValueError('Minimal supported path: an existing Spinal/sbt core repository with build.sbt.')
    build = (root / 'build.sbt').read_text()
    sources = sorted((root / 'src').rglob('*.scala'))
    if 'spinal' not in build.lower() and not any('spinal.' in p.read_text() for p in sources):
        raise ValueError('Spinal build not detected. Supply a Spinal/sbt core project.')
    versions = sorted(set(re.findall(r'(?:spinalVersion\s*[:=]+|spinalhdl-core"\s*%+)\s*"([\d.]+)"', build)))
    tops = sorted({match for p in sources for match in re.findall(r'class\s+(\w+)\s*(?:\([^)]*\))?\s+extends\s+Component\b', p.read_text())})
    if isa is None:
        candidates = sorted({s.lower() for s in re.findall(r'\brv(?:32|64)[a-z]+(?:_[a-z0-9]+)*\b', build + '\n'.join(p.read_text() for p in sources), re.I)})
        if len(candidates) != 1:
            raise ValueError('Cannot determine one ISA. Supply --isa from the core specification.')
        isa = candidates[0]
    isa = isa.lower()
    if re.fullmatch(r'rv(32|64)[ieg][a-z]*(?:_[a-z][a-z0-9]*)*', isa) is None:
        raise ValueError('ISA must start with rv32 or rv64 and an i, e or g base. Verify extensions against the core.')
    width = int(isa[2:4])
    if xlen is not None and xlen != width:
        raise ValueError('XLEN does not match the ISA.')
    name = name or root.name
    if re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_-]*', name) is None:
        raise ValueError('Core name must start with a letter and contain letters, digits, _ or -.')
    q = json.dumps
    config = f'''[project]
schema = "rvw.project/1"
rvw_version = {q(rvw.__version__)}
root = "."

[core]
name = {q(name)}
adapter = "./rvw/run.sh"
configs = ["default"]
default_config = "default"
source_repo = "."
lock = {q(name)}
input_complete = false
identity = false
identity_capture = false
jobs = 1

[suites.smoke]
dir = "rvw/out/programs"
include = ['^smoke$']
max_cycles = 10000
timeout_s = 60

[tiers.quick]
runs = [{{ suite = "smoke" }}]
'''
    info = dict(schema='rvw.adapter/1', core=name, configs=['default'], default_config='default',
                xlen=width, isa={'default': isa}, scaffold=True)
    launcher = f'''#!/usr/bin/env bash
# Scaffold only. Replace build/run after mapping the actual core signals.
set -euo pipefail
if [ "${{1:-}}" = info ] && [ "$#" = 2 ] && [ "$2" = --json ]; then
  cat <<'RVW_INFO'
{json.dumps(info)}
RVW_INFO
  exit 0
fi
printf '%s\\n' 'Adapter not implemented. Map compile, elaborate, memory, reset, completion and RVFI in CoreAdapter.scala. See rvw/README.md.' >&2
exit 2
'''
    adapter = f'''package rvwcore

import java.io.File
import riscvsim._
import spinal.core._
import spinal.core.sim._

// Candidates from source inspection only: {', '.join(tops) or 'none detected'}.
// No signal mapping or completion rule has been inferred.
object Adapter extends CoreAdapter {{
  type Model = SimCompiled[Component]
  def core: String = {q(name)}
  def configs: Seq[String] = Seq("default")
  def isa(config: String): String = {q(isa)}
  def xlen: Int = {width}
  def sourceDir: File = new File(sys.env("RVW_CORE_SOURCE"))
  override def replayEnv: Seq[(String, String)] = Seq("RVW_CORE_SOURCE" -> sourceDir.getCanonicalPath)
  def report(key: ModelKey, work: File) =
    RiscvSimConfig.elaborate(key, work, Elaboration.config)(Elaboration.top())
  def compile(key: ModelKey, work: File, cache: File): Model =
    RiscvSimConfig(key, work, cache, Elaboration.config).compile(report(key, work))
  override def elaborate(key: ModelKey, work: File): Seq[File] =
    report(key, work).generatedSourcesPaths.toSeq.map(new File(_))
  override def generatedVerilog(model: Model): Seq[File] =
    Option(new File(model.compiledPath, "rtl").listFiles()).toSeq.flatten
      .filter(f => f.getName.endsWith(".v") || f.getName.endsWith(".sv"))
  def run(model: Model, job: RunJob, ctx: RunContext): RunOutcome =
    throw new UnsupportedOperationException("Map reset, memory, retired completion and C2 RVFI; load ctx.elf")
}}

// Edit this entry for every flow. Do not create a separate database top/config.
object Elaboration {{
  def config: SpinalConfig = SpinalConfig(
    defaultConfigForClockDomains = ClockDomainConfig(resetKind = SYNC))
  def top(): Component = {('new ' + db_top) if db_top else 'throw new UnsupportedOperationException("Map the core top")'}
}}

object Main {{
  def main(args: Array[String]): Unit = new Driver(Adapter).main(args)
}}
'''
    files = {'rvw.toml': config, 'rvw/run.sh': launcher,
             'rvw/src/main/scala/rvwcore/CoreAdapter.scala': adapter,
             'rvw/.gitignore': '/out/\n/target/\n/project/target/\n/project/project/\n',
             'rvw/README.md': '''# Core setup playbook

This scaffold supports one Spinal/sbt core and one default config.
The launcher answers C1 info only. Build and run refuse execution with exit 2.
No program pass, RVFI mapping or input-completeness claim is supplied.

1. Check the ISA and XLEN against the core specification.
2. Map the top, reset, instruction bus, data bus and retired completion rule.
3. Implement CoreAdapter.scala. Read RiscvSim/README.md and Model.scala.
4. Connect this source to the core's existing build with the generic RiscvSim library.
5. Set RVW_CORE_SOURCE to the source checkout used by the build.
6. Replace run.sh with a C1 launcher. Start from a shipped example. Preserve process supervision and native identity capture. Hold the core and sbt locks.
7. Build one smoke ELF at rvw/out/programs/smoke with the correct link address.
8. Run rvw doctor --json. Fix each reported action.
9. Use rvw doctor --smoke-elf rvw/out/programs/smoke --json for one C1 check.
10. Map C2 RVFI from retired effects. Check it against an independent reference.
11. Review all result-changing inputs before enabling input_complete and identity.
12. Commit reviewed project files before a gate check.

Optional cosim platform and SpinalDB files need explicit memory and elaboration
inputs. Use --linker-script and --db-top only after the minimum setup checks.
No integration-model policy is selected.
'''}
    from .mapped import PROBE_TEMPLATE
    files['rvw/templates/CoreProbes.scala'] = PROBE_TEMPLATE
    if sbt_project or db_top:
        wire_build = True
    if wire_build:
        if versions != ['1.15.0']:
            raise ValueError('Build wiring requires one literal Spinal version 1.15.0, matching RiscvSim. Review other builds manually.')
        paths = ['rvw/src', 'rvw/build.sbt', 'rvw/project/build.properties', 'rvw/run.sh',
                 '${RVW_HOME}/RiscvSim/src', '${RVW_HOME}/RiscvSim/scripts',
                 '${RVW_HOME}/RiscvSim/build.sbt', '${RVW_HOME}/RiscvSim/project/build.properties',
                 '${RVW_HOME}/SpinalProbes', '${RVW_HOME}/scripts/with-lock.sh',
                 '${RVW_HOME}/rvw/src/rvw/sim']
        files['rvw.toml'] = files['rvw.toml'].replace(
            'input_complete = false\nidentity = false\nidentity_capture = false',
            'input_complete = true\nidentity = true\nidentity_capture = true\n'
            + 'cache_paths = ' + q(paths) + '\n'
            + 'input_tools = ["git", "bash", "java", "verilator", "make"]\n'
            + 'input_verilator_toolchain = true\ninput_commands = ' + INPUT_COMMANDS + '\n'
            + 'input_commands_by_platform = { darwin = ["xcode-select", "xcrun"] }\n'
            + 'input_env = ' + INPUT_ENV + '\nidentity_timeout_s = 1200')
        files.update(build_files(build, sbt_project=sbt_project, db_top=db_top))
        files['rvw/run.sh'] = sim_script(name, launcher)
        files['rvw/README.md'] = files['rvw/README.md'].replace(
            'No program pass, RVFI mapping or input-completeness claim is supplied.',
            'Standard launcher inputs are declared. Review custom inputs before regression.').replace(
            '11. Review all result-changing inputs before enabling input_complete and identity.',
            '11. Extend cache_paths and input_env for custom result-changing inputs.')
        files['rvw.toml'] = files['rvw.toml'].replace('source_repo = "."', 'source_repo = "."\nsource_env = "RVW_CORE_SOURCE"')
        files['rvw/README.md'] += "\nThe generated sbt build uses the core project and generic RiscvSim library.\nSet RVW_HOME. Run sbt compile from rvw/ to check dependencies. The launcher\nuses generic supervision and identity capture. The adapter throws until mapped.\n"
    if (ram_region or reset_pc) and linker_script is None:
        raise ValueError('--ram-region and --reset-pc need --linker-script.')
    if linker_script:
        files['rvw/cosim.json'] = linker_platform(linker_script, region=ram_region, reset_pc=reset_pc,
                                                name=name, isa=isa, xlen=width)
        files['rvw.toml'] += '\n[cosim]\nplatform = "rvw/cosim.json"\n'
        files['rvw/README.md'] += "\nReview rvw/cosim.json against the core specification. The linker supplies\nonly the selected RAM region. Check MMIO, PMP, IRQ, privilege and fault policies.\nRemove review_required only after this review. The cosim loader refuses it.\n"
    if db_top:
        files['rvw/src/main/scala/rvwcore/CoreAdapter.scala'] += '''
object Database {
  def main(args: Array[String]): Unit = {
    val (opts, rtl, pos) = spinaldb.Main.parse(args.toSeq)
    require(pos.length == 1, "Expected output database path")
    spinaldb.SpinalDB.generate(
      Elaboration.config.copy(targetDirectory = rtl.getOrElse("out/db-rtl")),
      new File(pos.head), opts)(Elaboration.top())
  }
}
'''
        files['rvw/build-db.sh'] = db_script(db_top, name)
        files['rvw.toml'] += '\n[query]\nbuild = ["./rvw/build-db.sh"]\ndb = "rvw/out/design.db"\n'
        files['rvw/README.md'] += "\nThe query entry uses Elaboration.top and Elaboration.config. Check --db-top against\nthe actual source. Run rvw query build --config default after dependency setup.\n"
    conflicts = [key for key in files if (root / key).exists() or (root / key).is_symlink()]
    if conflicts and not force:
        raise ValueError('Refusing to overwrite: ' + ', '.join(conflicts) + '. Use --force only for intended replacement.')
    # Preflight all targets before the first write, including blocked parents.
    for key in files:
        target = root / key
        if target.is_dir():
            raise ValueError(f'Refusing to replace directory: {target}')
        for parent in target.parents:
            if parent == root:
                break
            if parent.exists() and not parent.is_dir():
                raise ValueError(f'Parent is not a directory: {parent}')
    if not dry_run:
        for key, content in files.items():
            target = root / key
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        for key in files:
            if key.endswith('.sh'):
                (root / key).chmod(0o755)
    return dict(schema='rvw.init/1', status='planned' if dry_run else 'created', exit_code=0,
                root=str(root), isa=isa, xlen=width, spinal_versions=versions, candidate_tops=tops, build_wired=wire_build,
                files=files, overwritten=conflicts if force else [],
                next=['Run rvw doctor --json. Project parsing should be ready; adapter, tests and gate remain not ready.',
                      'Map the adapter signals and RVFI. Follow rvw/README.md.'])
