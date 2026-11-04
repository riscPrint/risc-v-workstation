package spinalwaves

import java.nio.file.{Files, Path, Paths}
import scala.jdk.CollectionConverters._
import scala.sys.process.Process
import spinal.core._
import spinal.core.sim._
import spinal.core.internals.{PhaseContext, PhaseNetlist}

/** Opt-in Verilator/VCD simulation with typed metadata. A GUI launches only with launchViewer=true. */
case class SpinalWavesSim(config: SpinalSimConfig = SimConfig,
                          sourceRoots: Seq[Path] = SourceLocator.defaultRoots,
                          launchViewer: Boolean = false,
                          viewerBinary: String = "surfer-tywaves",
                          /** Sim-time limit per doSim (None: unlimited). See [[SimGuard]]. */
                          simTimeout: Option[Long] = SimGuard.defaultTimeout) {
  def compile[T <: Component](gen: => T): SpinalWavesCompiled[T] = {
    val sim = config.copy().withVerilator.withVcdWave
    if (sim._workspacePath.startsWith("~"))
      sim._workspacePath = System.getProperty("user.home") + sim._workspacePath.drop(1)
    // Keep generated sources/runtime assets, just as SpinalSim does in tmp/job_*.
    // SimCompiled.report and $readmem files can still refer to these after compilation.
    val temporaryRoot = Files.createDirectories(Paths.get(sim._workspacePath).resolve("tmp"))
    val rtlDir = Files.createTempDirectory(temporaryRoot, "spinalwaves-rtl-")
    locally {
      // Match SpinalSim's usual Verilator elaboration hooks, without naming or keeping any signal.
      val rtlConfig = sim._spinalConfig.copy(targetDirectory = rtlDir.toString, noAssertAtTimeZero = true,
        transformationPhases = sim._spinalConfig.transformationPhases.clone())
        .addTransformationPhase(new PhaseNetlist {
          override def impl(pc: PhaseContext): Unit = {
            pc.topLevel.rework {
              val cd = pc.topLevel.clockDomain
              if (cd != null) {
                if (cd.clock != null) cd.readClockWire
                if (cd.reset != null) cd.readResetWire
                if (cd.softReset != null) cd.readSoftResetWire
                if (cd.clockEnable != null) cd.readClockEnableWire
              }
            }
            pc.walkComponents {
              case b: BlackBox if b.isBlackBox && b.isSpinalSimWb => b.clearBlackBox()
              case _ => ()
            }
          }
        }).addTransformationPhase(new SimVerilatorPhase)
      val report = SpinalWaves.elaborateWithLocations(rtlConfig)(gen)
      report.blackboxesSourcesPaths ++= sim._additionalRtlPath
      report.blackboxesIncludeDir ++= sim._additionalIncludeDir
      val compiled = sim.compile(report)
      val hgldd = HglddEmitter.emit(report, compiled.compiledPath.toPath, sourceRoots)
      new SpinalWavesCompiled(compiled, hgldd, launchViewer, viewerBinary, simTimeout)
    }
  }
}

final class SpinalWavesCompiled[T <: Component](val compiled: SimCompiled[T], val hglddFile: Path,
                                               launchViewer: Boolean, viewerBinary: String,
                                               simTimeout: Option[Long] = SimGuard.defaultTimeout) {
  def report: SpinalReport[T] = compiled.report
  def dut: T = compiled.dut
  def workspace: Path = compiled.compiledPath.toPath
  def hglddDir: Path = hglddFile.getParent
  private var lastWave: Option[Path] = None
  def vcdFile: Path = lastWave.getOrElse(throw new IllegalStateException("Run doSim before requesting the VCD"))
  def extraScopes: Seq[String] = SimLayout.extraScopes(vcdFile, report.toplevelName)

  def doSim(body: T => Unit): Unit = doSim("test")(body)
  def doSim(name: String)(body: T => Unit): Unit = run(name) { compiled.doSim(name)(guarded(body)) }
  def doSim(name: String, seed: Int)(body: T => Unit): Unit = run(name) { compiled.doSim(name, seed)(guarded(body)) }

  private def guarded(body: T => Unit): T => Unit = { dut => SimGuard.arm(simTimeout); body(dut) }

  private def run(name: String)(simulation: => Unit): Unit = {
    lastWave = None
    val index = compiled.testNameMap.synchronized { compiled.testNameMap.getOrElse(name, 0) }
    val allocated = if (index == 0) name else s"${name}_$index"
    simulation
    val prefix = Option(compiled.simConfig._waveFilePrefix).map(_.replace("$TEST", allocated) + "_").getOrElse("")
    val wave = Paths.get(compiled.simConfig.getTestPath(allocated)).resolve(prefix + "wave.vcd").toAbsolutePath.normalize
    require(Files.isRegularFile(wave), s"Simulation produced no VCD at configured path $wave")
    lastWave = Some(wave)
    if (launchViewer) Process(Seq(viewerBinary, vcdFile.toString, "--hgldd-dir", hglddDir.toString,
      "--extra-scopes") ++ extraScopes ++ Seq("--top-module", report.toplevelName)).run()
  }
}
