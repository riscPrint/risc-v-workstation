package riscvsim

import java.io.File

/** Command-line and manifest parsing for the run contract (C1). */
object Cli {
  class UsageError(msg: String) extends Exception(msg)

  /** Flags without a value, and options with one. Dashes and underscores are equivalent. */
  val flags = Set("rvfi-trace", "rvfi-check", "rvfi", "wave", "konata", "coverage", "json", "help")
  val options = Set("elf", "out", "config", "seed", "max-cycles", "mem-latency", "wave-from", "wave-to",
    "manifest", "jobs", "summary", "wall-timeout", "irq-schedule")
  private val integerOptions = Set("seed", "max-cycles", "mem-latency", "wave-from", "wave-to", "jobs")

  private def booleanValue(k: String, v: String): Boolean = v.toLowerCase(java.util.Locale.ROOT) match {
    case "true" | "1" => true
    case "false" | "0" => false
    case _ => throw new UsageError(s"--$k must be true, false, 1 or 0: $v")
  }

  def norm(k: String): String = k.stripPrefix("--").replace('_', '-')

  /** Parses `--key value` / `--flag` arguments into a map (flags map to "true"). */
  def parse(args: Seq[String], identity: Boolean = false): Map[String, String] = {
    val out = scala.collection.mutable.LinkedHashMap[String, String]()
    var i = 0
    while (i < args.length) {
      val a = args(i)
      if (!a.startsWith("--")) throw new UsageError(s"unexpected argument '$a'")
      val (k, inline) = a.indexOf('=') match {
        case -1 => (norm(a), None)
        case n => (norm(a.take(n)), Some(a.drop(n + 1)))
      }
      if (flags(k)) {
        val v = inline.getOrElse("true")
        booleanValue(k, v)
        out(k) = v; i += 1
      }
      else if (options(k) || (identity && k == "options")) {
        val v = inline.getOrElse {
          if (i + 1 >= args.length) throw new UsageError(s"--$k needs a value")
          i += 1; args(i)
        }
        out(k) = v; i += 1
      } else throw new UsageError(s"unknown option --$k")
    }
    out.toMap
  }

  /** A manifest line (JSON object) as the same key/value map; JSON booleans and numbers become strings. */
  def fromJson(o: ujson.Value): Map[String, String] = o.obj.map { case (k, v) =>
    val key = norm(k)
    if (!flags(key) && !options(key)) throw new UsageError(s"unknown manifest key '$k'")
    val value = v match {
      case ujson.Str(s) => s
      case ujson.Bool(b) => b.toString
      // ujson stores numbers as Double. Refuse integers outside the exact range rather than
      // rounding or saturating them via toLong. Strings retain the full supported Long range.
      case ujson.Num(n) if integerOptions(key) =>
        if (!java.lang.Double.isFinite(n) || n % 1 != 0 || math.abs(n) > 9007199254740991d)
          throw new UsageError(s"manifest '$k' must be an exact integer in [-9007199254740991, 9007199254740991]; use a string for larger integers")
        n.toLong.toString
      case ujson.Num(n) => if (n == n.toLong) n.toLong.toString else n.toString
      case ujson.Null if !flags(key) => null
      case other => throw new UsageError(s"bad value for '$k': $other")
    }
    if (flags(key)) booleanValue(key, value)
    key -> value
  }.filter(_._2 != null).toMap

  def bool(m: Map[String, String], k: String): Boolean = m.get(k).map(booleanValue(k, _)).getOrElse(false)

  def file(base: File, p: String): File = {
    val f = new File(p)
    (if (f.isAbsolute) f else new File(base, p)).getAbsoluteFile.toPath.normalize.toFile
  }

  def long(m: Map[String, String], k: String, min: Long = Long.MinValue, max: Long = Long.MaxValue): Option[Long] =
    m.get(k).map { v =>
      val n = try v.toLong catch {
        case _: NumberFormatException => throw new UsageError(s"--$k: not a signed 64-bit integer: $v")
      }
      if (n < min || n > max) throw new UsageError(s"--$k must be in [$min, $max]: $v")
      n
    }

  def int(m: Map[String, String], k: String, min: Int = Int.MinValue, max: Int = Int.MaxValue): Option[Int] =
    long(m, k, min, max).map(_.toInt)

  /** Builds a job from options; `cwd` resolves relative paths. */
  def job(m: Map[String, String], adapter: CoreAdapter, cwd: File): RunJob = {
    // Validate even a flag bypassed by short-circuit evaluation in the model selection.
    for (k <- flags if m.contains(k)) bool(m, k)
    def need(k: String) = m.getOrElse(k, throw new UsageError(s"--$k is required"))
    val config = m.getOrElse("config", adapter.defaultConfig)
    if (!adapter.configs.contains(config)) throw new UsageError(s"unknown config '$config' (${adapter.configs.mkString(", ")})")
    val (seed, picked) = int(m, "seed") match {
      case Some(s) => (s, false)
      case None => (scala.util.Random.nextInt(Int.MaxValue), true)
    }
    val maxCycles = long(m, "max-cycles", min = 1).getOrElse(adapter.defaultMaxCycles)
    if (maxCycles <= 0) throw new UsageError("--max-cycles must be positive")
    val memLatency = int(m, "mem-latency", min = 0)
    val waveFrom = long(m, "wave-from", min = 0)
    val waveTo = long(m, "wave-to", min = 1)
    for (f <- waveFrom; t <- waveTo) if (t <= f) throw new UsageError("--wave-to must be after --wave-from")
    val schedule = m.get("irq-schedule").map(InterruptSchedule.parse)
    schedule.foreach(s => {
      if ((s.mask & ~adapter.irqInputMask) != 0) throw new UsageError("adapter does not support these IRQ inputs")
      if (s.changes.last._1 >= maxCycles) throw new UsageError("IRQ schedule must finish before --max-cycles")
    })
    RunJob(
      elf = file(cwd, need("elf")), out = file(cwd, need("out")), config = config, seed = seed, seedPicked = picked,
      maxCycles = maxCycles, memLatency = memLatency,
      rvfiTrace = bool(m, "rvfi-trace"), rvfiCheck = bool(m, "rvfi-check") || bool(m, "rvfi"),
      wave = bool(m, "wave") || waveFrom.isDefined || waveTo.isDefined, waveFrom = waveFrom, waveTo = waveTo,
      konata = bool(m, "konata"), coverage = bool(m, "coverage"),
      irqSchedule = schedule,
      wallTimeoutS = m.get("wall-timeout").map { v =>
        val d = try v.toDouble catch { case _: NumberFormatException => throw new UsageError(s"--wall-timeout: not a number: $v") }
        if (!java.lang.Double.isFinite(d) || d <= 0)
          throw new UsageError("--wall-timeout must be finite and positive")
        d
      })
  }

  val usage: String =
    """usage:
      |  run.sh build    --config NAME[,NAME...] [--rvfi] [--wave] [--coverage] [--konata] [--json]
      |  run.sh run      --elf PATH --out DIR [--config NAME] [--seed N] [--max-cycles N] [--mem-latency N]
      |                  [--rvfi-trace] [--rvfi-check] [--wave [--wave-from CYCLE] [--wave-to CYCLE]]
      |                  [--konata] [--coverage] [--wall-timeout SECONDS] [--irq-schedule CYCLE:0xLEVELS,...] [--json]
      |  run.sh run-many --manifest jobs.jsonl [--jobs N] [--summary FILE] [--json] [defaults for every job...]
      |  run.sh identity [--config NAME] [--options JSON]
      |  run.sh info     [--json]
      |  Boolean flags accept =true, =false, =1 or =0 (case-insensitive). A bare flag means true.
      |""".stripMargin
}
