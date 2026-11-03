package spinalchecks

import spinal.core._

import scala.collection.mutable
import scala.collection.mutable.ArrayBuffer

/** Check kinds. A check's id is `<kind>:<instance path>.<object>`, e.g.
  * `stream.valid_hold:core.rob.io_enq`; waivers and enables match ids with globs. Ids are unique: the
  * instance path is the identity path (`SpinalChecks.instanceIds`, sibling segments made distinct
  * before the checks are inserted) and objects are made distinct within their component. */
object Kind {
  val StreamValidHold     = "stream.valid_hold"
  val StreamPayloadStable = "stream.payload_stable"
  val MemIndex            = "mem.index"
  val VecIndex            = "vec.index"
  val EnumLegal           = "enum.legal"
  val FsmStateLegal       = "fsm.state_legal"
  val Progress            = "progress.watchdog"
  val TileLinkBurstStable = "tilelink.burst_stable"
  val all = Seq(StreamValidHold, StreamPayloadStable, MemIndex, VecIndex, EnumLegal, FsmStateLegal, Progress,
    TileLinkBurstStable, "tilelink.response_match", "tilelink.source_busy", "tilelink.request_legal",
    "tilelink.response_legal", "tilelink.sink_busy", "tilelink.sink_match", "tilelink.release_busy",
    "tilelink.release_match", "axi4.address_legal", "axi4.read_match", "axi4.read_capacity",
    "axi4.write_match", "axi4.write_beats", "axi4.write_capacity")

  /** Short tag used in generated signal names (`chk_<tag>_<object>`). */
  def tag(kind: String): String = kind match {
    case StreamValidHold     => "hold"
    case StreamPayloadStable => "stable"
    case MemIndex            => "memidx"
    case VecIndex            => "vecidx"
    case EnumLegal           => "enum"
    case FsmStateLegal       => "fsm"
    case Progress            => "progress"
    case TileLinkBurstStable => "tlburst"
    case other               => other.replaceAll("[^A-Za-z0-9]", "_")
  }
}

/** How a check is turned into hardware.
  *  - `Assert`: a Spinal `assert` (`assume` for environment rules in formal configs). In Verilog it is a
  *    real `assert` under `ifdef FORMAL` (SymbiYosys) and a `$display` otherwise (Verilator).
  *  - `Monitor`: simulation bookkeeping instead: a sticky `fired` flag, a firing count, the first firing
  *    cycle (all `simPublic`, read back by [[ChecksSim]]) and a `$display` of the first few firings.
  *  - `Both`: both of the above. */
sealed trait Mode { def name: String }
object Mode {
  case object Assert  extends Mode { val name = "assert" }
  case object Monitor extends Mode { val name = "monitor" }
  case object Both    extends Mode { val name = "both" }
  def parse(s: String): Mode = s.toLowerCase match {
    case "assert" => Assert
    case "monitor" => Monitor
    case "both" => Both
    case other => throw new IllegalArgumentException(s"unknown SpinalChecks mode '$other' (assert, monitor, both)")
  }
}

/** A waiver: checks whose id matches `pattern` (a glob, `*` matches anything including dots) are not
  * inserted; the report keeps them with `reason`. */
case class Waiver(pattern: String, reason: String)

/** A Decoupled producer can withdraw or replace an offer before acceptance. */
case class StreamSemantics(pattern: String, reason: String) {
  require(reason.trim.nonEmpty, "may-drop-valid settings need a reason")
}

/** Opt-in progress watchdog: `signal` (a regex over `<instance path>.<signal name>`, e.g.
  * `io_trace_insns_\d+_valid`) must show progress at least once every `maxCycles` cycles. When all
  * matches are Bools, progress is any of them being high; a single wider signal makes progress by
  * changing value. All matches must live in one component. */
case class ProgressSpec(name: String, signal: String, maxCycles: Int)

case class ChecksConfig(
    enable: Seq[String] = Seq("*"),
    disable: Seq[String] = Nil,
    waivers: Seq[Waiver] = Nil,
    progress: Seq[ProgressSpec] = Nil,
    mode: Mode = Mode.Assert,
    /** Severity of the generated `assert`s; ERROR prints in simulation without stopping it. */
    severity: AssertNodeSeverity = ERROR,
    /** Stream rules on the toplevel's slave (input) streams describe the environment: emit them as
      * `assume` when the config includes formal (`SpinalConfig.includeFormal`). */
    envAsAssume: Boolean = true,
    /** Also check streams that are not ports (wires between logic inside a component). */
    internalStreams: Boolean = true,
    /** Monitor mode: `$display` the first N firings of each check. */
    monitorReports: Int = 3,
    /** Where to write the report; null means `<targetDirectory>/<toplevel>.checks.json`. */
    reportPath: String = null,
    mayDropValid: Seq[StreamSemantics] = Nil
) {
  private def globs(ps: Seq[String]) = ps.map(Glob(_))
  private lazy val enableR  = globs(enable)
  private lazy val disableR = globs(disable)
  private lazy val waiverR  = waivers.map(w => (Glob(w.pattern), w))

  /** `None` to insert the check, else `(status, reason)`. */
  def decide(id: String): Option[(String, String)] = {
    if (!enableR.exists(_.matches(id))) Some(("disabled", "not matched by enable"))
    else disableR.find(_.matches(id)) match {
      case Some(r) => Some(("disabled", s"matched disable pattern ${r.regex}"))
      case None => waiverR.find(_._1.matches(id)).map { case (_, w) => ("waived", s"${w.pattern}: ${w.reason}") }
    }
  }

  def streamReason(path: String): Option[String] =
    mayDropValid.find(s => Glob(s.pattern).matches(path)).map(_.reason)

  def withStreamFile(path: String): ChecksConfig = copy(mayDropValid = mayDropValid ++
    ChecksConfig.readWaivers(path).map(w => StreamSemantics(w.pattern, w.reason)))

  def withWaiverFile(path: String): ChecksConfig = copy(waivers = waivers ++ ChecksConfig.readWaivers(path))
}

object ChecksConfig {
  /** Waiver file: one `<glob> <reason>` per line; `#` starts a comment; blank lines ignored. */
  def readWaivers(path: String): Seq[Waiver] = {
    val src = scala.io.Source.fromFile(path)
    try src.getLines().map(_.trim).filter(l => l.nonEmpty && !l.startsWith("#")).map { l =>
      val parts = l.split("\\s+", 2)
      Waiver(parts(0), if (parts.length > 1) parts(1) else "")
    }.toVector
    finally src.close()
  }

  /** A config from environment variables, for harnesses that are not Scala code:
    * `SPINALCHECKS_MODE`, `SPINALCHECKS_ENABLE` / `_DISABLE` (comma-separated globs),
    * `SPINALCHECKS_WAIVERS` (waiver file), `SPINALCHECKS_STREAMS` (channel semantics file),
    * `SPINALCHECKS_PROGRESS` (`name=regex@cycles`, comma-separated). */
  def fromEnv(base: ChecksConfig = ChecksConfig(), env: Map[String, String] = sys.env): ChecksConfig = {
    def list(k: String) = env.get(k).map(_.split(",").map(_.trim).filter(_.nonEmpty).toSeq)
    var c = base
    env.get("SPINALCHECKS_MODE").foreach(m => c = c.copy(mode = Mode.parse(m)))
    list("SPINALCHECKS_ENABLE").foreach(e => c = c.copy(enable = e))
    list("SPINALCHECKS_DISABLE").foreach(d => c = c.copy(disable = c.disable ++ d))
    env.get("SPINALCHECKS_WAIVERS").foreach(f => c = c.withWaiverFile(f))
    env.get("SPINALCHECKS_STREAMS").foreach(f => c = c.withStreamFile(f))
    list("SPINALCHECKS_PROGRESS").foreach(ps => c = c.copy(progress = c.progress ++ ps.map(parseProgress)))
    c
  }

  /** `name=regex@cycles` */
  def parseProgress(s: String): ProgressSpec = {
    val eq = s.indexOf('='); val at = s.lastIndexOf('@')
    require(eq > 0 && at > eq, s"progress spec '$s' is not name=regex@cycles")
    ProgressSpec(s.substring(0, eq), s.substring(eq + 1, at), s.substring(at + 1).toInt)
  }
}

object Glob {
  def apply(p: String): scala.util.matching.Regex =
    p.map {
      case '*' => ".*"
      case '?' => "."
      case c if "\\.[]{}()+-^$|".contains(c) => "\\" + c
      case c => c.toString
    }.mkString.r
}

final case class SourceLoc(file: String, line: Int, className: String) {
  override def toString = s"$file:$line"
}

object SourceLoc {
  /** Frames that are never the user's source: the JVM, Scala, Spinal itself and this library. */
  private val skip = Seq("java.", "jdk.", "sun.", "scala.", "spinal.core", "spinal.sim", "spinal.lib.",
    "spinalchecks.SpinalChecks", "spinalchecks.PhaseInsertChecks", "spinalchecks.PhaseChecksReport")

  /** The innermost user frame of the object's creation stack (Spinal keeps stacks only for
    * `debugComponents`; see [[SpinalChecks.withLocations]]). Falls back to a spinal.lib frame. */
  def of(x: ScalaLocated): Option[SourceLoc] = Option(x).flatMap(v => Option(v.scalaTrace)).flatMap { t =>
    val frames = t.getStackTrace.filter(f => f.getFileName != null && f.getLineNumber > 0)
    frames.find(f => !skip.exists(f.getClassName.startsWith(_)))
      .orElse(frames.find(_.getClassName.startsWith("spinal.lib.")))
      .map(f => SourceLoc(f.getFileName, f.getLineNumber, f.getClassName))
  }
}

/** One generated check. Hardware handles are set while it is inserted; names are final after the
  * report phase. */
class CheckRecord(val id: String, val kind: String, val component: Component, val path: String,
                  val objName: String, val env: Boolean, val location: Option[SourceLoc], val detail: String) {
  var status: String = "inserted"
  var reason: String = null
  var fail: Bool = null
  var fired: Bool = null
  var count: UInt = null
  var firstCycle: UInt = null
  /** Verilog names, filled in by the report phase. */
  var module: String = null
  var failName: String = null
  /** Signals the check watches, by role (valid, ready, payload, address, state, ...). */
  val signals = mutable.LinkedHashMap[String, Seq[BaseType]]()
  def inserted: Boolean = status == "inserted"
}

/** A Stream or Flow seen in the design, for the X-propagation flow (valid, ready, payload). */
class Channel(val kind: String, val component: Component, val path: String, val objName: String,
              val valid: Bool, val ready: Bool, val payload: Seq[BaseType], val location: Option[SourceLoc])

class ChecksResult(val config: ChecksConfig) {
  var top: Component = null
  var formal: Boolean = false
  var reportFile: String = null
  val records = ArrayBuffer[CheckRecord]()
  val channels = ArrayBuffer[Channel]()
  val notes = ArrayBuffer[String]()
  def inserted: Seq[CheckRecord] = records.filter(_.inserted).toSeq
  def clear(): Unit = { top = null; records.clear(); channels.clear(); notes.clear() }
}

/** Attached to the toplevel so simulations can find the checks of the design they run. */
class ChecksTag(val result: ChecksResult) extends SpinalTag
