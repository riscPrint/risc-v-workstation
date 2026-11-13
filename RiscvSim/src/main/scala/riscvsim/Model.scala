package riscvsim

import java.io.File

/** Outcome of one run, as in the C1 run contract (`rvw.run/1`). */
sealed abstract class Status(val name: String) { override def toString: String = name }
object Status {
  case object Pass extends Status("pass")
  case object Fail extends Status("fail")
  case object Timeout extends Status("timeout")
  case object Assert extends Status("assert")
  case object RvfiError extends Status("rvfi_error")
  case object Error extends Status("error")
  val all: Seq[Status] = Seq(Pass, Fail, Timeout, Assert, RvfiError, Error)
}

/**
 * Which simulation model a run needs. Every distinct key is a separate Verilator build
 * (cached across processes by Spinal's compile cache, keyed on the generated Verilog).
 */
case class ModelKey(config: String, rvfi: Boolean = false, wave: Boolean = false, coverage: Boolean = false,
                    konata: Boolean = false, spinaltrace: Boolean = false, probes: Boolean = false,
                    faults: Boolean = false) {
  def name: String = config + (if (rvfi) "_rvfi" else "") + (if (konata) "_konata" else "") +
    (if (wave) "_wave_fst" else "") + (if (coverage) "_cov" else "") + (if (spinaltrace) "_spinaltrace" else "") +
    (if (probes) "_probes" else "") + (if (faults) "_fault" else "")
  def toJson: ujson.Obj = ujson.Obj("config" -> config, "rvfi" -> rvfi, "wave" -> wave, "wave_format" -> (if (wave) ujson.Str("fst") else ujson.Null), "coverage" -> coverage,
    "coverage_types" -> (if (coverage) ujson.Arr.from(RiscvSimConfig.coverageTypes) else ujson.Arr()), "konata" -> konata, "spinaltrace" -> spinaltrace, "probes" -> probes, "faults" -> faults, "name" -> name)
}

/** One simulation job (the options of `run`, or one line of a `run-many` manifest). */
case class RunJob(elf: File, out: File, config: String, seed: Int, seedPicked: Boolean, maxCycles: Long,
                  memLatency: Option[Int], rvfiTrace: Boolean, rvfiCheck: Boolean, wave: Boolean,
                  waveFrom: Option[Long], waveTo: Option[Long], konata: Boolean, coverage: Boolean,
                  wallTimeoutS: Option[Double] = None, spinaltrace: Boolean = false, irqSchedule: Option[InterruptSchedule] = None, elfLoadBias: Long = 0L, bootPayloads: Option[File] = None, socMap: Option[SimMap] = None, hartImages: Option[File] = None, probes: Boolean = false,
                  fault: Option[FaultFile] = None, debug: Option[DebugMode] = None,
                  traceIngress: Option[IngressBinding] = None) {
  def model: ModelKey = ModelKey(config, rvfi = rvfiTrace || rvfiCheck || hartImages.nonEmpty, wave = wave, coverage = coverage, konata = konata, spinaltrace = spinaltrace, probes = probes, faults = fault.nonEmpty)
}

/** What an adapter's run loop reports back. `metrics` (optional, C1) holds named numbers such as roi_cycles. */
case class RunOutcome(status: Status, cycles: Long, instret: Long, failCode: Option[Long] = None,
                      message: Option[String] = None, details: ujson.Obj = ujson.Obj(),
                      metrics: ujson.Obj = ujson.Obj())

/**
 * A core's simulation adapter. The generic driver (`Driver`) owns the command line, result
 * files, provenance and the worker pool; the adapter elaborates the core and runs one ELF.
 */
trait CoreAdapter {
  /** A compiled simulation model (e.g. a SimCompiled[Top]); shared by concurrent runs. */
  type Model
  /** Short core name for result files ("boom"). */
  /** True only when run constructs a fresh native instance and fresh harness state.
    * Persistent serve refuses adapters that do not make this declaration. */
  def freshInstancePerRun: Boolean = false
  def supportsBootPayloads: Boolean = false
  /** True when the adapter elaborates with `spinalprobes.Probe.enabled(key.probes)` and writes
    * `probe-events.jsonl` through `ProbeCollector.open`. */
  def supportsProbes: Boolean = false
  /** Opt in only when the adapter uses shared memory and per-hart RVFI. */
  def hartIds(config: String): Seq[Int] = Nil
  def core: String
  def configs: Seq[String]
  def defaultConfig: String = configs.head
  def irqInputMask: BigInt = 0
  def defaultMaxCycles: Long = 200000L
  /** ISA string for the RVFI trace header. */
  def isa(config: String): String
  def xlen: Int
  /** Number of byte lanes in the store data bus. Override when it differs from XLEN. */
  def busBytes: Int = xlen / 8
  /** The core's source checkout, for `source.core_repo/core_rev/core_dirty`. */
  def sourceDir: File
  /** Builds (or loads from cache) the model. `work` is this process's workspace, `cache` is shared. */
  def compile(key: ModelKey, work: File, cache: File): Model
  /** Elaborates the same RTL used by compile, without building native code. */
  def elaborate(key: ModelKey, work: File): Seq[File] =
    throw new UnsupportedOperationException("adapter does not provide RTL identity")
  /** Runs one job on a model built for `job.model`. Exceptions become status `assert` (or `error` before the sim starts). */
  def run(model: Model, job: RunJob, ctx: RunContext): RunOutcome
  /** Extra environment a replay command needs (e.g. where the core sources are). */
  def replayEnv: Seq[(String, String)] = Nil
  /** Generated Verilog files of a compiled model (for mapping assertion messages to source lines). */
  def generatedVerilog(model: Model): Seq[File] = Nil
}

/**
 * A run's wall-clock limit (C1 `wall_timeout`, seconds), counted from when its model is ready.
 * `SimControl.tick` ends a slow simulation at the limit; the driver's watchdog abandons one that
 * stops advancing. Either way the result is a `timeout` with `wall_clock_timeout: true`.
 */
class WallClock(val limitS: Option[Double]) {
  @volatile private var startNs = -1L
  @volatile var expired = false
  def start(): Unit = if (startNs < 0) startNs = System.nanoTime()
  def started: Boolean = startNs >= 0
  def elapsedS: Double = if (startNs < 0) 0.0 else (System.nanoTime() - startNs) / 1e9
  /** True once the limit is past by `graceS` seconds. */
  def over(graceS: Double = 0): Boolean = limitS.exists(l => startNs >= 0 && elapsedS > l + graceS)
}
object WallClock { val none = new WallClock(None) }

/** Services the driver gives an adapter during one run. */
trait RunContext {
  def job: RunJob
  /** The ELF captured before compilation. Use it for loading, symbols and disassembly.
    * `job.elf` is the original path for metadata only; never reopen it during this run. */
  def elf: ElfFile
  def hartImages: Option[HartImages] = None
  def loadMemory(write: (Long, Array[Byte]) => Unit): Unit =
    hartImages match { case Some(h) => h.load(write); case None => elf.load(write) }
  /** A line for this run's run.log (also echoed to stderr). */
  def log(line: String): Unit
  /** RVFI trace header fields (core, config, elf, isa, xlen); the writer adds the schema. */
  def rvfiHeader: ujson.Obj
  /** Request identity for live bus captures. Keep process IDs out of C2 bytes. */
  def captureIdentity: ujson.Obj = rvfiHeader
  /** Index of assertion messages for the model being run. */
  def assertIndex: AssertIndex
  /** Native-output mark taken when the run started (see NativeOutput). */
  def outputMark: Long
  /** This run's wall-clock limit (none unless the job has `wall_timeout`). */
  def wallClock: WallClock = WallClock.none
}
