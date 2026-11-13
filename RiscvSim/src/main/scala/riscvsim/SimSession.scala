package riscvsim

import java.io.File

import spinal.core._
import spinal.core.sim._
import spinal.core.internals.{PhaseContext, PhaseNetlist}
import spinal.sim.SimFailure

/** Spinal simulation settings shared by adapters. */
object RiscvSimConfig {
  /** Use the native executable's version, since launcher --version can be stale. */
  private lazy val verilatorVersion: String = {
    import scala.sys.process._
    scala.util.Try(Process(Seq("verilator", "-V")).!!).getOrElse("")
  }

  private def checkedCoverageVersion(version: String): Boolean = {
    val pattern = "Verilator ([0-9]+)\\.([0-9]+)".r
    pattern.findFirstMatchIn(version).exists { m =>
      m.group(1).toInt > 5 || (m.group(1).toInt == 5 && m.group(2).toInt >= 52)
    }
  }

  private[riscvsim] def fsmSupported(version: String): Boolean = checkedCoverageVersion(version)
  private[riscvsim] def perInstanceSupported(version: String): Boolean = checkedCoverageVersion(version)
  def perInstanceCoverage: Boolean = perInstanceSupported(verilatorVersion)

  /** FSM detection was checked on 5.052; 5.049 crashes on an empty reset branch. */
  def coverageTypes: Seq[String] = {
    val supported = fsmSupported(verilatorVersion)
    val kinds = sys.env.getOrElse("RISCVSIM_COVERAGE", if (supported) "line,user,fsm" else "line,user")
      .split(",").map(_.trim).filter(_.nonEmpty).toSeq
    require(kinds.forall(Set("line", "user", "toggle", "expr", "fsm")), "unsupported coverage kind")
    require(!kinds.contains("fsm") || supported, "FSM coverage requires Verilator >= 5.052")
    kinds
  }
  private val elaborations = new java.util.concurrent.ConcurrentHashMap[ModelKey, java.lang.Double]()
  def elaborationSeconds(key: ModelKey): Option[Double] = Option(elaborations.get(key)).map(_.doubleValue)


  /** Use Spinal's simulation phases for both identity and native compilation. */
  def elaborate[T <: Component](key: ModelKey, work: File, config: SpinalConfig,
      sourceRoots: Seq[File] = Nil)(rtl: => T): SpinalReport[T] = {
    val started = System.nanoTime()
    val cfg = config.copy(targetDirectory = new File(work, key.name + "-rtl").getAbsolutePath,
      headerWithRepoHash = false, headerWithDate = false).includeSimulation
    cfg.noAssertAtTimeZero = true
    cfg.addTransformationPhase(new PhaseNetlist {
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
          case _ =>
        }
      }
    })
    if (key.faults) cfg.addTransformationPhase(new FaultFile.PublicRegisters)
    cfg.addTransformationPhase(new SimVerilatorPhase)
    val report = if (key.spinaltrace) spinaltrace.SpinalTrace.elaborate(cfg)(rtl) else cfg.generateVerilog(rtl)
    if (key.spinaltrace) {
      spinaltrace.PdgExtractor.extractTo(report, dependencyGraph(key, work), spinaltrace.ExtractOptions(sourceRoots = sourceRoots))
    }
    // Include blackbox RTL, such as an RVFI monitor, in the exact file Verilator reads.
    require(report.generatedSourcesPaths.size == 1 && report.blackboxesIncludeDir.isEmpty,
      "RTL identity requires one generated file and no external include directories")
    val file = new File(report.generatedSourcesPaths.head)
    val bytes = report.rtlSourcesPaths.toSeq.map(p => java.nio.file.Files.readAllBytes(new File(p).toPath))
    val text = bytes.map(b => new String(b, java.nio.charset.StandardCharsets.UTF_8)).mkString("\n")
    require(!"""`include\b|\$readmem[hb]\s*\(""".r.findFirstIn(text).isDefined,
      "RTL identity does not support external include or memory data files")
    java.nio.file.Files.writeString(file.toPath, text)
    report.blackboxesSourcesPaths.clear()
    elaborations.put(key, (System.nanoTime() - started) / 1e9)
    report
  }

  /** Dependency graph emitted by the same elaboration as the model RTL. */
  def dependencyGraph(key: ModelKey, work: File): File =
    new File(work, key.name + "-rtl/spinaltrace/pdg.json")

  /**
   * A Verilator SimConfig for `key`: workspace under `work` (private to this process),
   * Verilator binaries cached in `cache` (shared), and each run's wave / coverage files
   * written straight into the run directory (the test name passed to doSim is that path).
   */
  def apply(key: ModelKey, work: File, cache: File, spinalConfig: SpinalConfig): SpinalSimConfig = {
    // No repository hash or date in the Verilog header: the Verilator cache is keyed on the
    // generated files, and the hash would come from whatever directory the caller runs in.
    val cfg = SimConfig
      .withConfig(spinalConfig.copy(headerWithRepoHash = false, headerWithDate = false))
      .workspacePath(work.getAbsolutePath)
      .workspaceName(key.name)
      .maxCacheEntries(sys.env.get("RISCVSIM_CACHE_ENTRIES").map(_.toInt).getOrElse(64))
      .setTestPath("$TEST")
      .withVerilator
      .allOptimisation
    NativeBuild.cachePath(cache) match {
      case Some(path) => cfg.cachePath(path.getAbsolutePath)
      case None => cfg.disableCache
    }
    if (key.wave) cfg.withVcdWave
    // Fault models write registers from outside; Verilator must re-evaluate their readers.
    if (key.faults) cfg.addSimulatorFlag("--public-flat-rw")
    if (key.coverage) {
      // Select explicit kinds through the version gate. -DCOVERAGE enables the wrapper writer.
      cfg.addSimulatorFlag("-CFLAGS -DCOVERAGE")
      if (perInstanceCoverage) cfg.addSimulatorFlag("--coverage-per-instance")
      for (t <- coverageTypes) cfg.addSimulatorFlag(s"--coverage-$t")
    }
    cfg
  }
}

/**
 * Per-run control for an adapter's simulation: counts cycles, applies the wave window, stops
 * at the cycle limit, and records how the run ended. Call `tick()` once per clock sample
 * (e.g. first thing in `clockDomain.onSamplings`).
 */
class SimControl(val job: RunJob, val wall: WallClock = WallClock.none) {
  var cycle = 0L
  /** Simulation time of the first sampled cycle (waves: cycle N is at timeOfCycle1 + (N - 1) * period). */
  var timeOfCycle1 = -1L
  private[riscvsim] var ended: Option[(Status, Option[Long], Option[String])] = None
  private val waveFrom = job.waveFrom.getOrElse(0L)

  /** Call at the start of the simulation body. */
  def start(): Unit = if (job.wave && waveFrom > 0) disableSimWave()

  def tick(): Unit = {
    cycle += 1
    if (cycle == 1) timeOfCycle1 = simTime()
    if (job.wave) {
      if (waveFrom > 0 && cycle == waveFrom) enableSimWave()
      if (job.waveTo.contains(cycle)) disableSimWave()
    }
    if (cycle >= job.maxCycles && ended.isEmpty) finish(Status.Timeout, message = Some(s"no result after ${job.maxCycles} cycles"))
    if ((cycle & 1023) == 0 && ended.isEmpty && wall.over()) {
      wall.expired = true
      finish(Status.Timeout, message = Some(f"wall-clock timeout after ${wall.limitS.get}%.0f s at cycle $cycle"))
    }
  }

  /** Ends the simulation now with this status. */
  def finish(status: Status, failCode: Option[Long] = None, message: Option[String] = None): Nothing = {
    if (ended.isEmpty) ended = Some((status, failCode, message))
    simSuccess()
  }

  def isEnded: Boolean = ended.isDefined
}

object SimSession {
  /** Wave file name Spinal writes in the run directory. */
  val waveFile = "wave.vcd"
  val coverageFile = "coverage.dat"

  /**
   * Runs `body` as one simulation named after the run directory (so Spinal writes the wave
   * and coverage there). Returns how it ended: the status `finish` set, or `assert` for an
   * HDL assertion / simulation exception (with the assertion text and source location when
   * the native output and the assertion index have them).
   */
  def run[T <: Component](compiled: SimCompiled[T], job: RunJob, ctx: RunContext)(body: (T, SimControl) => Unit)
      : (Status, Option[Long], Option[String], Long) = runCtl(compiled, job, ctx)(body) match { case (s, c, m, n, _) => (s, c, m, n) }

  /** Like `run`, also returning the SimControl (cycle count, time of cycle 1). */
  def runCtl[T <: Component](compiled: SimCompiled[T], job: RunJob, ctx: RunContext)(body: (T, SimControl) => Unit)
      : (Status, Option[Long], Option[String], Long, SimControl) = {
    val ctl = new SimControl(job, ctx.wallClock)
    val name = job.out.getAbsolutePath
    compiled.testNameMap.synchronized(compiled.testNameMap.remove(name))
    val failure: Option[Throwable] =
      try {
        compiled.doSim(name, job.seed) { dut =>
          ctl.start()
          FaultInjector.forJob(job).foreach(_.attach(dut, ctl))
          body(dut, ctl)
        }
        None
      } catch {
        case e: Throwable => Some(e)
      }
    failure match {
      case None =>
        val (s, c, m) = ctl.ended.getOrElse((Status.Error, None, Some("simulation ended without a result")))
        (s, c, m, ctl.cycle, ctl)
      case Some(e) if ctl.ended.isDefined && !e.isInstanceOf[SimFailure] =>
        // the run already had a result; an exception while shutting down is only logged
        ctx.log(s"exception after the run ended: $e")
        val (s, c, m) = ctl.ended.get
        (s, c, m, ctl.cycle, ctl)
      case Some(e: SimFailure) =>
        (Status.Assert, None, Some(assertionMessage(e, ctx)), ctl.cycle, ctl)
      case Some(e) =>
        val where = e.getStackTrace.headOption.map(f => s" at $f").getOrElse("")
        ctx.log(s"simulation exception: $e")
        e.getStackTrace.take(12).foreach(f => ctx.log(s"    at $f"))
        (Status.Assert, None, Some(s"${e.getClass.getName}: ${e.getMessage}$where"), ctl.cycle, ctl)
    }
  }

  /** The assertion text the model printed, with its Scala location, else the exception text. */
  def assertionMessage(e: Throwable, ctx: RunContext): String = {
    val line = NativeOutput.await(ctx.outputMark, 500)(l => AssertIndex.isFailureLine(l.text))
    line match {
      case Some(l) =>
        val locs = ctx.assertIndex.locate(l.text)
        l.text.trim + (if (locs.nonEmpty) s" (${locs.mkString(", ")})" else "")
      case None => s"${e.getMessage} (no assertion text captured)"
    }
  }
}
