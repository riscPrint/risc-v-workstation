package riscvsim

import java.io.{File, PrintWriter}
import java.nio.channels.FileChannel
import java.nio.file.StandardOpenOption
import java.util.concurrent.{ConcurrentHashMap, ThreadFactory, TimeUnit}
import java.util.concurrent.atomic.AtomicInteger

import scala.jdk.CollectionConverters._

/**
 * The run contract's command line (C1) for one core adapter:
 * `build`, `run`, `run-many` and `info`. See `Cli.usage` and RiscvSim/README.md.
 *
 * System properties (set by the adapter's launcher script):
 *  - riscvsim.cwd     directory relative paths are resolved against (default: the JVM's cwd)
 *  - riscvsim.script  launcher path, used in `replay` commands (relative to the tools checkout when inside it)
 *  - riscvsim.tools   the tools checkout (risc-v-workstation), for provenance and the replay path
 * Environment:
 *  - RISCVSIM_WORK    work root (default ~/.cache/rvw/riscvsim/<core>): `cache/` holds the shared
 *                     Verilator builds, `ws/<pid>/` this process's workspace (deleted at exit
 *                     unless RISCVSIM_KEEP_WS=1)
 */
object Driver {

  case class Ctx(job: RunJob, elf: ElfFile, logF: String => Unit, rvfiHeader: ujson.Obj, assertIndex: AssertIndex, outputMark: Long,
                 override val wallClock: WallClock = WallClock.none) extends RunContext {
    def log(line: String): Unit = logF(line)
  }

  /**
   * One run in progress. `overlapped`: another run of this process was active at some time during
   * this one, so native output (assertion text, RVFI monitor messages) cannot be attributed to it.
   * `claim()` decides who writes result.json: the run itself, or the watchdog that abandoned it.
   */
  final class RunState(val tag: String, val wall: WallClock) {
    @volatile var overlapped = false
    @volatile var abandoned = false
    /** The worker (not the watchdog) claimed this run's result: the worker reports it. */
    @volatile var owned = false
    private val claimed = new java.util.concurrent.atomic.AtomicBoolean(false)
    def claim(): Boolean = claimed.compareAndSet(false, true)
  }

  /** Seconds past the wall-clock limit before the watchdog abandons a run that did not stop itself. */
  def abandonGraceS(limitS: Double): Double = math.max(2.0, 0.1 * limitS)

  /** Failures whose message comes from native output, which carries no run identity. */
  def attributable(status: String): Boolean = status == Status.Assert.name || status == Status.RvfiError.name
  val pendingReason = "failure while other simulations ran; attribution pending (the serial rerun did not finish)"
}

class Driver(val adapter: CoreAdapter) {
  val cwd: File = new File(sys.props.getOrElse("riscvsim.cwd", ".")).getAbsoluteFile
  val script: String = sys.props.getOrElse("riscvsim.script", s"${adapter.core}-run")
  val workRoot: File = new File(sys.env.getOrElse("RISCVSIM_WORK",
    s"${sys.props("user.home")}/.cache/rvw/riscvsim/${adapter.core}")).getAbsoluteFile
  val cacheDir = new File(workRoot, "cache")
  @volatile private var workspaceUsed = false
  lazy val workspace: File = {
    val ws = new File(workRoot, s"ws/${ProcessHandle.current().pid()}")
    ws.mkdirs()
    workspaceUsed = true
    ws
  }
  /** Deletes this process's workspace (the loaded models stay usable), unless RISCVSIM_KEEP_WS is set. */
  def cleanWorkspace(): Unit =
    if (workspaceUsed && !sys.env.contains("RISCVSIM_KEEP_WS")) org.apache.commons.io.FileUtils.deleteQuietly(workspace)


  // ---------------------------------------------------------------- provenance
  lazy val toolsDir: File = new File(sys.props.getOrElse("riscvsim.tools", cwd.getPath))
  val source: ujson.Obj = sys.props.get("riscvsim.source").map { path =>
    ujson.read(java.nio.file.Files.readAllBytes(new File(path).toPath)).obj
  }.map(ujson.Obj.from(_)).getOrElse(ujson.Obj(
    "core_repo" -> ujson.Null, "core_rev" -> ujson.Null, "core_dirty" -> ujson.Null,
    "tools_repo" -> ujson.Null, "tools_rev" -> ujson.Null, "tools_dirty" -> ujson.Null))
  val tools: ujson.Obj = ujson.Obj(
    "verilator" -> NativeBuild.current.obj.get("tools").flatMap(_.obj.get("verilator")).map(_("version")).getOrElse(ujson.Null),
    "java" -> NativeBuild.current.obj.get("tools").flatMap(_.obj.get("java")).map(_("version")).getOrElse(ujson.Null),
    "spinalhdl" -> spinal.core.Info.version,
    "native_build" -> NativeBuild.current.obj.getOrElse("provenance", ujson.Null))

  // ---------------------------------------------------------------- models
  /** `rtlDir`: a stable copy of the generated Verilog (content-addressed), which coverage files refer to. */
  case class Built(model: adapter.Model, index: AssertIndex, compileS: Double, cached: Boolean, rtlDir: Option[File], rtlSha256: Option[String], pdg: Option[File])
  @volatile private var serverMode = false
  private val sessionId = java.util.UUID.randomUUID().toString
  private val modelRuns = new ConcurrentHashMap[ModelKey, AtomicInteger]()
  private val slots = new ConcurrentHashMap[ModelKey, Object]()
  private val models = new ConcurrentHashMap[ModelKey, Built]()
  private val jvmCompileLock = new Object

  /** The model for `key`, compiled once per process; builds of the same model are serialized across processes. */
  def model(key: ModelKey, log: String => Unit): Built = {
    val slot = slots.computeIfAbsent(key, _ => new Object)
    slot.synchronized {
      Option(models.get(key)) match {
        case Some(b) => b
        case None =>
          // one build of a model at a time across processes (the second one then hits the cache);
          // within this process, one elaboration at a time (Spinal elaboration is memory hungry)
          val b = jvmCompileLock.synchronized(withFileLock(new File(workRoot, s"locks/${key.name}.lock"), log) {
            log(s"building model ${key.name}")
            val mark = NativeOutput.mark()
            val t0 = System.nanoTime()
            val m = NativeBuild.transaction(cacheDir, NativeBuild.problem.isEmpty) {
              adapter.compile(key, workspace, cacheDir)
            }
            val s = (System.nanoTime() - t0) / 1e9
            NativeOutput.drain()
            val cached = NativeOutput.since(mark).exists(_.text.contains("Found cached verilator binaries"))
            val verilog = adapter.generatedVerilog(m)
            val (rtlDir, rtlSha) = captureRtl(verilog)
            val index = AssertIndex.fromVerilog(rtlDir.toSeq.flatMap(d => Option(d.listFiles()).toSeq.flatten).filter(_.getName.endsWith(".v")))
            log(f"model ${key.name} ready in $s%.1f s (${if (cached) "Verilator cache hit" else "Verilator build"}, ${index.size} assertion messages indexed)")
            val pdg = if (key.spinaltrace) {
              val graph = RiscvSimConfig.dependencyGraph(key, workspace)
              require(graph.isFile, "adapter did not emit the requested SpinalTrace model")
              Some(graph)
            } else None
            Built(m, index, s, cached, rtlDir, rtlSha, pdg)
          })
          models.put(key, b)
          b
      }
    }
  }

  /** Copies the generated Verilog to `work/rtl/<content hash>/` (kept across runs and processes). */
  def stableRtl(files: Seq[File]): Option[File] = captureRtl(files)._1

  private def captureRtl(files: Seq[File]): (Option[File], Option[String]) = {
    if (files.size != 1) return (None, None)
    val input = files.head
    val bytes = java.nio.file.Files.readAllBytes(input.toPath)
    val sha = ElfFile.sha256(bytes)
    val dir = new File(workRoot, "rtl/" + sha)
    if (!new File(dir, ".complete").isFile) {
      val tmp = new File(dir.getPath + s".tmp${ProcessHandle.current().pid()}")
      tmp.mkdirs()
      java.nio.file.Files.write(new File(tmp, input.getName).toPath, bytes)
      new File(tmp, ".complete").createNewFile()
      if (!tmp.renameTo(dir)) org.apache.commons.io.FileUtils.deleteQuietly(tmp)
    }
    (Some(dir), Some(sha))
  }

  /**
   * Verilator names each coverage point's source file: the temporary workspace of whichever
   * process built the (cached) model. Point them at the stable RTL copy so coverage from
   * different runs merges and can be annotated.
   */
  def rewriteCoveragePaths(cov: File, rtlDir: File): Unit = {
    val ws = new File(workRoot, "ws").getAbsolutePath + "/"
    val tmp = new File(cov.getPath + ".tmp")
    val in = new java.io.BufferedReader(new java.io.InputStreamReader(new java.io.FileInputStream(cov), "ISO-8859-1"), 1 << 20)
    val out = new java.io.BufferedWriter(new java.io.OutputStreamWriter(new java.io.FileOutputStream(tmp), "ISO-8859-1"), 1 << 20)
    val key = "\u0001f\u0002" + ws
    try {
      var line = in.readLine()
      while (line != null) {
        val i = line.indexOf(key)
        if (i < 0) out.write(line)
        else {
          val start = i + 3
          val end = line.indexOf('\u0001', start)
          val path = line.substring(start, end)
          out.write(line.substring(0, start)); out.write(rtlDir.getPath + "/" + new File(path).getName); out.write(line.substring(end))
        }
        out.write('\n')
        line = in.readLine()
      }
    } finally { in.close(); out.close() }
    java.nio.file.Files.move(tmp.toPath, cov.toPath, java.nio.file.StandardCopyOption.REPLACE_EXISTING)
  }

  private def withFileLock[T](f: File, log: String => Unit)(body: => T): T = {
    f.getParentFile.mkdirs()
    val ch = FileChannel.open(f.toPath, StandardOpenOption.CREATE, StandardOpenOption.WRITE)
    try {
      var lock = ch.tryLock()
      if (lock == null) {
        log(s"waiting for another process's model build ($f)")
        lock = ch.lock()
      }
      try body finally lock.release()
    } finally ch.close()
  }

  // ---------------------------------------------------------------- one run
  val artifactFiles: Seq[(String, String)] = Seq("log" -> "run.log", "rvfi_trace" -> "rvfi.jsonl",
    "wave" -> SimSession.waveFile, "konata" -> "konata.log", "coverage" -> SimSession.coverageFile)

  private def q(s: String): String = if (s.matches("[A-Za-z0-9_./=:,+@%-]+")) s else "'" + s.replace("'", "'\\''") + "'"

  /**
   * The launcher as a path relative to the tools checkout when it is inside it (C1:
   * `RiscvSim/boom/run.sh run ...`), so a replay runs the adapter of whichever checkout replays it
   * (`source.tools_rev` says which revision produced the result); else the path as given.
   */
  lazy val replayScript: String = {
    val sf = new File(script)
    if (!sf.isAbsolute) script
    else {
      val root = toolsDir.getCanonicalFile.toPath
      val sp = sf.getCanonicalFile.toPath
      if (sp.startsWith(root)) root.relativize(sp).toString else script
    }
  }

  def replay(job: RunJob): String = {
    val out = new File(job.out.getPath + "-replay")
    val parts = Seq(replayScript, "run", "--elf", job.elf.getPath, "--out", out.getPath, "--config", job.config,
      "--seed", job.seed.toString, "--max-cycles", job.maxCycles.toString) ++
      job.irqSchedule.toSeq.flatMap(s => Seq("--irq-schedule", s.text)) ++
      job.memLatency.toSeq.flatMap(l => Seq("--mem-latency", l.toString)) ++
      job.wallTimeoutS.toSeq.flatMap(s => Seq("--wall-timeout", s.toString)) ++
      (if (job.rvfiTrace) Seq("--rvfi-trace") else Nil) ++
      (if (job.rvfiCheck) Seq("--rvfi-check") else Nil) ++
      (if (job.wave) Seq("--wave") else Nil) ++
      job.waveFrom.toSeq.flatMap(c => Seq("--wave-from", c.toString)) ++
      job.waveTo.toSeq.flatMap(c => Seq("--wave-to", c.toString)) ++
      (if (job.konata) Seq("--konata") else Nil) ++
      (if (job.coverage) Seq("--coverage") else Nil) ++
      (if (job.spinaltrace) Seq("--spinaltrace") else Nil)
    val coverageEnv = if (job.coverage)
      Seq("RISCVSIM_COVERAGE" -> RiscvSimConfig.coverageTypes.mkString(",")) else Nil
    ((NativeBuild.replayEnv ++ adapter.replayEnv ++ coverageEnv).map { case (k, v) => s"$k=${q(v)}" } ++
      NativeBuild.replayArgs.map(q) ++ parts.map(q)).mkString(" ")
  }

  // ---------------------------------------------------------------- runs in progress
  private val capturedElfs = new ConcurrentHashMap[String, ElfFile]()
  private val activeRuns = new java.util.LinkedHashSet[Driver.RunState]()
  /** Prefixes of the driver's own stderr lines (`[tag] ...`); they never go into a run.log as native output. */
  private val driverPrefixes = ConcurrentHashMap.newKeySet[String]()
  private val tagCounter = new AtomicInteger(0)

  private def register(st: Driver.RunState): Unit = activeRuns.synchronized {
    if (!activeRuns.isEmpty) { activeRuns.forEach(_.overlapped = true); st.overlapped = true }
    activeRuns.add(st)
  }
  private def unregister(st: Driver.RunState): Unit = activeRuns.synchronized { activeRuns.remove(st); () }
  private def alone(st: Driver.RunState): Boolean = activeRuns.synchronized(activeRuns.size == 1 && activeRuns.contains(st))

  private def isDriverLine(text: String): Boolean =
    text.startsWith("[run-many]") || text.startsWith("[build]") || text.startsWith("[riscvsim]") ||
      (text.startsWith("[") && { val i = text.indexOf("] "); i > 0 && driverPrefixes.contains(text.substring(0, i + 2)) })

  /** Writes `job.out/result.json` atomically (temporary file + rename): readers never see half a file. */
  def writeResult(job: RunJob, result: ujson.Obj): Unit = {
    NativeBuild.problem.foreach { p =>
      val existing = result.obj.get("inconclusive").map(_.str + "; ").getOrElse("")
      if (!existing.contains(p)) result("inconclusive") = existing + p
    }
    if (result.obj.get("rtl_sha256").forall(_ == ujson.Null) && !result.obj.contains("inconclusive"))
      result("inconclusive") = "input_not_captured:rtl"
    job.out.mkdirs()
    val rf = new File(job.out, "result.json")
    val tmp = File.createTempFile(".result.json.", ".tmp", job.out)
    try {
      val w = new PrintWriter(tmp)
      try w.println(ujson.write(result, indent = 2)) finally w.close()
      java.nio.file.Files.move(tmp.toPath, rf.toPath, java.nio.file.StandardCopyOption.REPLACE_EXISTING,
        java.nio.file.StandardCopyOption.ATOMIC_MOVE)
    } finally { tmp.delete(); () }
  }

  private def baseResult(job: RunJob, status: Status, failCode: Option[Long], message: Option[String], cycles: Long,
                         instret: Long, wall: Double, elfSha: ujson.Value, artifacts: ujson.Obj, details: ujson.Obj): ujson.Obj =
    ujson.Obj(
      "schema" -> "rvw.run/1",
      "execution_mode" -> (if (serverMode) "server" else "process"),
      "core" -> adapter.core, "config" -> job.config,
      "elf" -> job.elf.getPath, "elf_sha256" -> elfSha,
      "seed" -> job.seed, "max_cycles" -> RvwJson.num(job.maxCycles),
      "mem_latency" -> job.memLatency.map(ujson.Num(_)).getOrElse(ujson.Null),
      "irq_schedule" -> job.irqSchedule.map(s => ujson.Str(s.text)).getOrElse(ujson.Null),
      "status" -> status.name,
      "fail_code" -> failCode.map(c => ujson.Num(c.toDouble)).getOrElse(ujson.Null),
      "message" -> message.map(ujson.Str).getOrElse(ujson.Null),
      "cycles" -> RvwJson.num(cycles), "instret" -> RvwJson.num(instret),
      "wall_s" -> math.round(wall * 100) / 100.0,
      "source" -> source, "tools" -> tools,
      "rtl_sha256" -> Option(models.get(job.model)).flatMap(_.rtlSha256).map(ujson.Str).getOrElse(ujson.Null),
      "artifacts" -> artifacts,
      "replay" -> replay(job),
      "details" -> details)

  // ---------------------------------------------------------------- one run
  /** Runs one job and writes `job.out/result.json`; returns the result. Never throws. */
  def runOne(job: RunJob): ujson.Obj = {
    capturedElfs.remove(job.elf.getAbsolutePath)
    runOne(job, newState(job))
  }

  def newState(job: RunJob): Driver.RunState = {
    val tag = s"${job.out.getName}#${tagCounter.incrementAndGet()}"
    driverPrefixes.add(s"[$tag] ")
    new Driver.RunState(tag, new WallClock(job.wallTimeoutS))
  }

  /**
   * Like `runOne(job)`; result.json is written only if `st.claim()` succeeds (not after the watchdog
   * abandoned the run). `keepResult`: leave an existing result.json in place until a new one replaces
   * it (the serial rerun: the pending result of the first attempt must survive a rerun that hangs or dies).
   */
  def runOne(job: RunJob, st: Driver.RunState, keepResult: Boolean = false): ujson.Obj = {
    val t0 = System.nanoTime()
    job.out.mkdirs()
    for ((_, f) <- artifactFiles ++ (if (keepResult) Nil else Seq("result" -> "result.json"))) new File(job.out, f).delete()
    val logW = new PrintWriter(new java.io.FileWriter(new File(job.out, "run.log")))
    val tag = st.tag
    def log(s: String): Unit = {
      logW.synchronized { logW.println(s); logW.flush() }
      System.err.println(s"[$tag] $s")
    }
    register(st)
    // Native output goes into this run.log only while no other run is active: lines carry no
    // run identity, so with concurrent runs they would land in every run's log.
    val omitted = new java.util.concurrent.atomic.AtomicBoolean(false)
    val sink: NativeOutput.Line => Unit = l => if (!isDriverLine(l.text)) {
      if (alone(st)) logW.synchronized(logW.println(l.text))
      else if (omitted.compareAndSet(false, true)) {
        logW.synchronized(logW.println("[riscvsim] native output printed while other runs were active is not in this log (see the adapter's stderr)"))
      }
    }
    NativeOutput.subscribe(sink)

    var elfSha: ujson.Value = ujson.Null
    var built: Option[Built] = None
    val outcome: RunOutcome = try {
      log(s"run ${job.elf} config=${job.config} seed=${job.seed}${if (job.seedPicked) " (picked)" else ""} max_cycles=${job.maxCycles}" +
        job.wallTimeoutS.map(w => f" wall_timeout=$w%.0fs").getOrElse(""))
      val elf = capturedElfs.computeIfAbsent(job.elf.getAbsolutePath, _ => new ElfFile(job.elf))
      elfSha = elf.sha256
      require(elf.xlen == adapter.xlen,
        s"ELF XLEN ${elf.xlen} does not match adapter XLEN ${adapter.xlen} (${adapter.core}/${job.config})")
      val b = model(job.model, log)
      built = Some(b)
      st.wall.start()
      val mark = NativeOutput.mark()
      val ctx = Driver.Ctx(job, elf, log, ujson.Obj("xlen" -> adapter.xlen, "isa" -> adapter.isa(job.config),
        "core" -> adapter.core, "config" -> job.config, "elf" -> job.elf.getPath), b.index, mark, st.wall)
      adapter.run(b.model, job, ctx)
    } catch {
      case e: Throwable =>
        log(s"harness error: $e")
        e.getStackTrace.take(15).foreach(f => log(s"    at $f"))
        RunOutcome(Status.Error, 0, 0, message = Some(s"${e.getClass.getSimpleName}: ${e.getMessage}"))
    }
    for (b <- built; dir <- b.rtlDir; cov = new File(job.out, SimSession.coverageFile) if cov.isFile)
      try rewriteCoveragePaths(cov, dir) catch { case e: Exception => log(s"could not rewrite coverage paths: $e") }
    val wall = (System.nanoTime() - t0) / 1e9
    NativeOutput.drain()
    NativeOutput.unsubscribe(sink)
    unregister(st)

    val artifacts = ujson.Obj()
    for ((k, f) <- artifactFiles if new File(job.out, f).isFile) artifacts(k) = f
    for (b <- built; graph <- b.pdg) {
      java.nio.file.Files.copy(graph.toPath, new File(job.out, "pdg.json").toPath,
        java.nio.file.StandardCopyOption.REPLACE_EXISTING)
      artifacts("pdg") = "pdg.json"
    }
    val details = outcome.details
    built.foreach { b =>
      details("model") = job.model.toJson
      details("simulation_session") = ujson.Obj("id" -> sessionId,
        "model_run" -> modelRuns.computeIfAbsent(job.model, _ => new AtomicInteger()).incrementAndGet(),
        "reset" -> (if (adapter.freshInstancePerRun) "new-native-instance" else "adapter-defined"), "verilator_cached" -> b.cached)
      details("execution_s") = st.wall.elapsedS
      RiscvSimConfig.elaborationSeconds(job.model).foreach { seconds =>
        details("model_timing") = ujson.Obj("elaboration_s" -> seconds,
          "native_and_setup_s" -> math.max(0.0, b.compileS - seconds))
      }
      details("model_compile_s") = math.round(b.compileS * 10) / 10.0
      b.rtlDir.foreach(d => details("rtl_dir") = d.getPath)
    }
    if (st.overlapped) details("concurrent") = true
    val result = baseResult(job, outcome.status, outcome.failCode, outcome.message, outcome.cycles, outcome.instret,
      wall, elfSha, artifacts, details)
    if (outcome.metrics.value.nonEmpty) result("metrics") = outcome.metrics
    if (outcome.status == Status.Timeout && st.wall.expired) result("wall_clock_timeout") = true
    // Until the serial rerun (runJobs) attributes it, a failure of a run that overlapped others
    // may carry another run's message: the result written now says nothing reliable. If the rerun
    // never finishes (the process dies), this one stays, and stays inconclusive.
    if (st.overlapped && Driver.attributable(outcome.status.name))
      result("inconclusive") = Driver.pendingReason
    log(s"${outcome.status.name}${outcome.failCode.map(c => s" code=$c").getOrElse("")} cycles=${outcome.cycles} instret=${outcome.instret} wall=${f"$wall%.1f"}s" +
      outcome.message.map(m => s" ($m)").getOrElse(""))
    logW.close()
    if (st.claim()) { st.owned = true; writeResult(job, result) }
    result
  }

  /**
   * The result of a run whose harness failed outside `runOne`'s own catch (review 11: output setup
   * or the result write threw, the worker's Future swallowed it and the batch waited forever).
   * Written when this side holds the claim (or already did, when the result write itself failed).
   */
  private def harnessFailure(job: RunJob, st: Driver.RunState, e: Throwable): ujson.Obj = {
    unregister(st)
    System.err.println(s"[riscvsim] ${st.tag}: harness error: $e")
    val r = baseResult(job, Status.Error, None, Some(s"harness error: ${e.getClass.getSimpleName}: ${e.getMessage}"),
      0, 0, st.wall.elapsedS, ujson.Null, ujson.Obj(), ujson.Obj("harness_error" -> true))
    if (st.claim()) st.owned = true
    if (st.owned) try writeResult(job, r) catch {
      case w: Throwable => System.err.println(s"[riscvsim] ${st.tag}: cannot write ${job.out}/result.json: $w")
    }
    r
  }

  /**
   * Checks every job's output directory before anything runs (review 11): it must be, or become, a
   * writable directory, and no two jobs may write to the same one, compared by canonical path (a
   * symbolic link and its target are one directory). Throws `Cli.UsageError`.
   */
  def checkOutputs(jobs: Seq[RunJob]): Unit = {
    for (j <- jobs) {
      val d = j.out
      if (d.exists && !d.isDirectory) throw new Cli.UsageError(s"output ${d.getPath} exists and is not a directory")
      if (!d.isDirectory && !d.mkdirs() && !d.isDirectory) throw new Cli.UsageError(s"cannot create the output directory ${d.getPath}")
      if (!java.nio.file.Files.isWritable(d.toPath)) throw new Cli.UsageError(s"output directory ${d.getPath} is not writable")
    }
    val canon = jobs.map { j =>
      try j.out -> j.out.getCanonicalFile
      catch { case e: java.io.IOException => throw new Cli.UsageError(s"cannot resolve the output directory ${j.out.getPath}: $e") }
    }
    val dups = canon.groupBy(_._2).filter(_._2.size > 1)
    if (dups.nonEmpty) throw new Cli.UsageError("several jobs write to the same directory: " + dups.map { case (c, xs) =>
      xs.map(_._1.getPath).distinct.mkString(", ") + (if (xs.exists(_._1.getPath != c.getPath)) s" (= ${c.getPath})" else "")
    }.mkString("; "))
  }

  /** The result the watchdog writes for a run that went past its wall-clock limit and did not stop. */
  private def abandonedResult(job: RunJob, st: Driver.RunState): ujson.Obj = {
    val limit = st.wall.limitS.getOrElse(0.0)
    val r = baseResult(job, Status.Timeout, None,
      Some(f"wall-clock timeout after $limit%.0f s (riscvsim watchdog: the simulation did not stop and was abandoned)"),
      0, 0, st.wall.elapsedS, ujson.Null, ujson.Obj("log" -> "run.log"), ujson.Obj("abandoned" -> true))
    r("wall_clock_timeout") = true
    r
  }

  /**
   * Runs jobs on `n` workers and returns their results in order. A job past its `wall_timeout`
   * (+ grace) that has not stopped is abandoned: the watchdog writes its timeout result and adds a
   * worker, so the batch goes on; the stuck thread dies with the process.
   *
   * Native output carries no run identity: an `assert` or `rvfi_error` of a run that overlapped
   * another run is rerun alone afterwards, and a message is kept only from a run that was alone.
   */
  private def captureJobs(jobs: Seq[RunJob]): Unit = {
    // Freeze every batch ELF before any worker can compile a model. Reruns use these bytes.
    capturedElfs.clear()
    for (job <- jobs) try capturedElfs.computeIfAbsent(job.elf.getAbsolutePath, _ => new ElfFile(job.elf))
      catch { case _: Exception => () } // runOne reports an invalid ELF as a harness error
  }

  def runJobs(jobs: Seq[RunJob], n: Int, progress: (Int, ujson.Obj) => Unit = (_, _) => (),
      captureInputs: Boolean = true): Array[ujson.Obj] = {
    if (captureInputs) captureJobs(jobs)
    val results = new Array[ujson.Obj](jobs.size)
    val states = jobs.map(newState).toArray
    val latch = new java.util.concurrent.CountDownLatch(jobs.size)
    val done = new AtomicInteger(0)
    val pool = new java.util.concurrent.ThreadPoolExecutor(n, n, 60, TimeUnit.SECONDS,
      new java.util.concurrent.LinkedBlockingQueue[Runnable](), new ThreadFactory {
        private val k = new AtomicInteger(0)
        // large stacks: elaborating a big core recurses deeply
        def newThread(r: Runnable): Thread = {
          val t = new Thread(null, r, s"riscvsim-worker-${k.incrementAndGet()}", 512L << 20)
          t.setDaemon(true); t
        }
      })
    val finished = Array.fill(jobs.size)(new java.util.concurrent.atomic.AtomicBoolean(false))
    def finish(i: Int, r: ujson.Obj): Unit = if (finished(i).compareAndSet(false, true)) {
      results(i) = r
      try progress(done.incrementAndGet(), r)
      finally latch.countDown()
    }
    // Every worker ends its job (review 11): an exception outside runOne's catch becomes an `error`
    // result, so the latch always completes. The side that claimed the result reports it.
    for ((job, i) <- jobs.zipWithIndex) pool.submit(new Runnable {
      def run(): Unit = {
        val st = states(i)
        val r = try runOne(job, st) catch { case e: Throwable => harnessFailure(job, st, e) }
        if (st.owned) finish(i, r)
      }
    })
    val watchdog = new Thread(() => {
      while (latch.getCount > 0) {
        for ((st, i) <- states.zipWithIndex
             if !st.abandoned && st.wall.over(st.wall.limitS.map(Driver.abandonGraceS).getOrElse(0.0)) && st.claim()) {
          st.abandoned = true
          val r = abandonedResult(jobs(i), st)
          try writeResult(jobs(i), r) catch { case e: Exception => System.err.println(s"[riscvsim] cannot write ${jobs(i).out}: $e") }
          System.err.println(s"[riscvsim] ${st.tag}: abandoned after ${f"${st.wall.elapsedS}%.0f"} s (wall_timeout ${st.wall.limitS.getOrElse(0.0)} s)")
          pool.setMaximumPoolSize(pool.getMaximumPoolSize + 1)
          pool.setCorePoolSize(pool.getCorePoolSize + 1)
          finish(i, r)
        }
        Thread.sleep(200)
      }
    }, "riscvsim-watchdog")
    watchdog.setDaemon(true)
    watchdog.start()
    latch.await()
    pool.shutdown()

    // Serial reruns: failures whose message may belong to another run. Each rerun has the batch's
    // watchdog; the first attempt's (pending, inconclusive) result stays on disk until the merged
    // result replaces it, so a rerun that hangs or dies never erases the observed failure.
    for (i <- jobs.indices if !states(i).abandoned && states(i).overlapped &&
         Driver.attributable(results(i)("status").str)) {
      val first = results(i)
      val job = jobs(i)
      new File(job.out, "run.log").renameTo(new File(job.out, "run.concurrent.log"))
      // The rerun overwrites the first attempt's artifacts: the pending result names only its log.
      val pending = ujson.copy(first).obj
      pending("artifacts") = ujson.Obj("log" -> "run.concurrent.log")
      pending("inconclusive") = Driver.pendingReason
      writeResult(job, ujson.Obj.from(pending))
      System.err.println(s"[riscvsim] ${states(i).tag}: ${first("status").str} while other runs were active; rerunning it alone to attribute its message")
      val st = newState(job)
      st.claim() // the merged result below is written instead
      val rerun = runWatched(job, st)
      val clean = rerun.isDefined && !st.overlapped
      val again = rerun.getOrElse(ujson.Obj.from(pending))
      val rerunStatus = rerun.map(_("status").str).getOrElse("abandoned")
      val same = clean && rerunStatus == first("status").str
      val why =
        if (rerun.isEmpty && st.abandoned) f" (the serial rerun did not stop and was abandoned after ${st.wall.elapsedS}%.0f s)"
        else if (rerun.isEmpty) " (the serial rerun ended without a result)"
        else if (clean) s" (serial rerun: $rerunStatus)" else " (no serial rerun alone was possible)"
      if (!same) {
        // Keep the failure (never turn it into a pass) without a message that may be another
        // run's, and mark it inconclusive: two such results of one test have the same message,
        // so without the mark they would count as the same failure (rvw: "still failing").
        again("status") = first("status")
        again("fail_code") = ujson.Null
        again("message") = s"${first("status").str} while other simulations ran; message not attributable" + why
        again("inconclusive") = "failure while other simulations ran; the serial rerun could not attribute it to this test" + why
      } else again.value.remove("inconclusive")
      again("details")("serial_rerun") = ujson.Obj(
        "first" -> ujson.Obj("status" -> first("status"), "message" -> first("message"), "log" -> "run.concurrent.log"),
        "rerun_status" -> (if (rerun.isEmpty) (if (st.abandoned) "abandoned" else "no result") else if (clean) rerunStatus else "not alone"),
        "attributed" -> same)
      writeResult(job, again)
      results(i) = again
    }
    results
  }

  /**
   * Runs `job` (a serial rerun) on its own thread under the same watchdog rule as a batch: past its
   * wall-clock limit + grace it is abandoned (None) and the stuck thread dies with the process.
   */
  private def runWatched(job: RunJob, st: Driver.RunState): Option[ujson.Obj] = {
    val box = new java.util.concurrent.atomic.AtomicReference[ujson.Obj]()
    val t = new Thread(null, () => box.set(runOne(job, st, keepResult = true)), s"riscvsim-rerun-${st.tag}", 512L << 20)
    t.setDaemon(true)
    t.start()
    while (t.isAlive) {
      if (st.wall.over(st.wall.limitS.map(Driver.abandonGraceS).getOrElse(0.0))) {
        st.abandoned = true
        System.err.println(s"[riscvsim] ${st.tag}: serial rerun abandoned after ${f"${st.wall.elapsedS}%.0f"} s (wall_timeout ${st.wall.limitS.getOrElse(0.0)} s)")
        return None
      }
      t.join(200)
    }
    Option(box.get)
  }

  // ---------------------------------------------------------------- commands
  def main(args: Array[String]): Unit = {
    val code = try {
      if (args.isEmpty || args.head == "help" || args.contains("--help")) {
        NativeOutput.writeStdout(Cli.usage); 0
      } else {
        NativeOutput.start(stdoutToStderr = true)
        val opts = Cli.parse(args.toSeq.tail, identity = args.head == "identity")
        args.head match {
          case "build" => cmdBuild(opts)
          case "run" => cmdRun(opts)
          case "run-many" => cmdRunMany(opts)
          case "serve" => cmdServe(opts)
          case "info" => cmdInfo(opts)
          case "identity" => cmdIdentity(opts)
          case other => throw new Cli.UsageError(s"unknown command '$other'")
        }
      }
    } catch {
      case e: Cli.UsageError =>
        System.err.println(s"error: ${e.getMessage}\n${Cli.usage}")
        2
      case e: Throwable =>             // never leave the JVM running without an exit code
        System.err.println(s"error: harness: $e")
        e.getStackTrace.take(15).foreach(f => System.err.println(s"    at $f"))
        2
    }
    try cleanWorkspace() catch { case e: Throwable => System.err.println(s"[riscvsim] cannot clean the workspace: $e") }
    NativeOutput.drain()
    System.out.flush(); System.err.flush()
    Runtime.getRuntime.halt(code) // Verilator models and sim threads may hold the JVM open
  }

  private def emit(json: Boolean, obj: ujson.Value, text: => String): Unit =
    NativeOutput.writeStdout((if (json) ujson.write(obj, indent = 2) else text) + "\n")

  def cmdInfo(o: Map[String, String]): Int = {
    val info = ujson.Obj("schema" -> "rvw.adapter/1", "core" -> adapter.core, "configs" -> adapter.configs,
      "default_config" -> adapter.defaultConfig, "default_max_cycles" -> RvwJson.num(adapter.defaultMaxCycles),
      "xlen" -> adapter.xlen, "isa" -> ujson.Obj.from(adapter.configs.map(c => c -> ujson.Str(adapter.isa(c)))),
      "work" -> workRoot.getPath, "script" -> script, "source" -> source, "tools" -> tools)
    emit(Cli.bool(o, "json"), info, ujson.write(info, indent = 2))
    0
  }

  def cmdIdentity(o: Map[String, String]): Int = {
    // Identity accepts run-manifest keys. Only model options affect elaboration.
    val names = Set("rvfi", "rvfi-trace", "rvfi-check", "wave", "wave-from", "wave-to", "coverage", "konata", "spinaltrace")
    val opts = o.get("options").map { text =>
      val values = ujson.read(text).obj.filter { case (name, _) => names(Cli.norm(name)) }
      Cli.fromJson(ujson.Obj.from(values))
    }.getOrElse(Map.empty[String, String]) ++ (o - "options")
    val key = ModelKey(opts.getOrElse("config", adapter.defaultConfig),
      rvfi = Cli.bool(opts, "rvfi") || Cli.bool(opts, "rvfi-trace") || Cli.bool(opts, "rvfi-check"),
      wave = Cli.bool(opts, "wave") || opts.contains("wave-from") || opts.contains("wave-to"),
      coverage = Cli.bool(opts, "coverage"), konata = Cli.bool(opts, "konata"), spinaltrace = Cli.bool(opts, "spinaltrace"))
    if (!adapter.configs.contains(key.config)) throw new Cli.UsageError(s"unknown config '${key.config}'")
    val (_, sha) = captureRtl(adapter.elaborate(key, workspace))
    if (key.spinaltrace) require(RiscvSimConfig.dependencyGraph(key, workspace).isFile,
      "adapter did not emit the requested SpinalTrace model")
    val problem = NativeBuild.problem.orElse(if (sha.isEmpty) Some("input_not_captured:rtl") else None)
    val claims = ujson.Obj("rtl_sha256" -> sha.map(ujson.Str).getOrElse(ujson.Null),
      "source.tools_rev" -> source("tools_rev"), "source.tools_dirty" -> source("tools_dirty"),
      "tools.native_build.sha256" -> NativeBuild.current.obj.getOrElse("sha256", ujson.Null))
    val identitySource = sys.env.get("RVW_CAPTURE_SOURCE").map(ujson.read(_)).getOrElse(source)
    val identity = ujson.Obj("schema" -> "rvw.adapter-capture/2", "complete" -> problem.isEmpty,
      "source" -> identitySource, "model" -> key.toJson, "result_claims" -> claims,
      "rtl_sha256" -> sha.map(ujson.Str).getOrElse(ujson.Null), "tools" -> tools)
    problem.foreach(p => identity("inconclusive") = p)
    emit(true, identity, "")
    if (problem.isEmpty) 0 else 2
  }

  def cmdBuild(o: Map[String, String]): Int = {
    val configs = o.getOrElse("config", adapter.defaultConfig).split(",").map(_.trim).filter(_.nonEmpty).toSeq
    if (configs.isEmpty) throw new Cli.UsageError("--config must name at least one config")
    for (c <- configs if !adapter.configs.contains(c)) throw new Cli.UsageError(s"unknown config '$c'")
    val results = configs.map { c =>
      val key = ModelKey(c, rvfi = Cli.bool(o, "rvfi") || Cli.bool(o, "rvfi-trace") || Cli.bool(o, "rvfi-check"),
        wave = Cli.bool(o, "wave"), coverage = Cli.bool(o, "coverage"), konata = Cli.bool(o, "konata"), spinaltrace = Cli.bool(o, "spinaltrace"))
      try {
        val b = model(key, s => System.err.println(s"[build] $s"))
        ujson.Obj("model" -> key.toJson, "status" -> "ok", "compile_s" -> math.round(b.compileS * 10) / 10.0,
          "verilator_cached" -> b.cached, "rtl_sha256" -> b.rtlSha256.map(ujson.Str).getOrElse(ujson.Null), "assertions_indexed" -> b.index.size)
      } catch {
        case e: Throwable =>
          System.err.println(s"[build] ${key.name} failed: $e")
          e.getStackTrace.take(15).foreach(f => System.err.println(s"    at $f"))
          ujson.Obj("model" -> key.toJson, "status" -> "error", "message" -> e.toString)
      }
    }
    val captureProblem = NativeBuild.problem
    val ok = results.forall(_("status").str == "ok") && captureProblem.isEmpty
    val out = ujson.Obj("schema" -> "rvw.build/1", "core" -> adapter.core, "status" -> (if (ok) "ok" else "error"),
      "models" -> results, "cache" -> cacheDir.getPath, "source" -> source, "tools" -> tools)
    captureProblem.foreach(p => out("inconclusive") = p)
    emit(Cli.bool(o, "json"), out, results.map(r => s"${r("status").str} ${r("model")("name").str}" +
      r.obj.get("compile_s").map(s => s" ${s.num}s").getOrElse("")).mkString("\n"))
    if (ok) 0 else 2
  }

  private def summaryLine(r: ujson.Obj): String = {
    val msg = r("message") match { case ujson.Str(m) => s" ($m)"; case _ => "" }
    s"${r("status").str} ${new File(r("elf").str).getName} cycles=${r("cycles").num.toLong} instret=${r("instret").num.toLong} " +
      s"seed=${r("seed").num.toLong} wall=${r("wall_s").num}s$msg"
  }

  def cmdRun(o: Map[String, String]): Int = {
    val job = Cli.job(o, adapter, cwd)
    checkOutputs(Seq(job))
    val r = runJobs(Seq(job), 1).head
    emit(Cli.bool(o, "json"), r, summaryLine(r) + s"\n  result: ${new File(job.out, "result.json")}")
    if (r("status").str == "error") return 2
    if (r.obj.contains("inconclusive")) return 3
    r("status").str match {
      case "pass" => 0
      case "error" => 2
      case _ => 1
    }
  }

  /** Serial JSONL requests. EOF is teardown. A stuck worker poisons the process. */
  def serve(o: Map[String, String], lines: Iterator[String], reply: ujson.Obj => Unit,
      capturedBatch: Boolean = false): Int = {
    if (!adapter.freshInstancePerRun) throw new Cli.UsageError("adapter does not declare a fresh instance for each run")
    val previousMode = serverMode
    serverMode = true
    try {
      for (line <- lines if line.trim.nonEmpty) {
        try {
          val request = ujson.read(line)
          if (request.obj.get("op").contains(ujson.Str("shutdown"))) {
            reply(ujson.Obj("schema" -> "rvw.sim-server/1", "shutdown" -> true))
            return 0
          }
          val job = Cli.job(o ++ Cli.fromJson(request), adapter, cwd)
          checkOutputs(Seq(job))
          val result = runJobs(Seq(job), 1, captureInputs = !capturedBatch).head
          reply(ujson.Obj("schema" -> "rvw.sim-server/1", "result" -> result))
          // The watchdog cannot kill a native simulation thread safely. Do not let
          // later requests share a process that still has this run alive.
          if (result("details").obj.get("abandoned").contains(ujson.Bool(true))) return 2
        } catch {
          case e: Exception => reply(ujson.Obj("schema" -> "rvw.sim-server/1", "error" -> e.getMessage))
        }
      }
      0
    } finally serverMode = previousMode
  }

  def cmdServe(o: Map[String, String]): Int = {
    val input = scala.io.Source.fromInputStream(System.in)
    try serve(o, input.getLines(), r => NativeOutput.writeStdout(ujson.write(r) + "\n"))
    finally input.close()
  }

  def cmdRunMany(o: Map[String, String]): Int = {
    val n = Cli.int(o, "jobs", min = 1).getOrElse(1)
    val persistent = Cli.bool(o, "persistent")
    if (persistent && n != 1) throw new Cli.UsageError("--persistent requires --jobs 1")
    if (persistent && !adapter.freshInstancePerRun)
      throw new Cli.UsageError("adapter does not declare a fresh instance for each run")
    val manifest = Cli.file(cwd, o.getOrElse("manifest", throw new Cli.UsageError("--manifest is required")))
    val defaults = o -- Seq("manifest", "jobs", "summary", "json", "persistent")
    val input = scala.io.Source.fromFile(manifest)
    val lines = try input.getLines().map(_.trim).zipWithIndex
      .filter { case (l, _) => l.nonEmpty && !l.startsWith("#") && !l.startsWith("//") }.toVector
    finally input.close()
    if (lines.isEmpty) throw new Cli.UsageError(s"--manifest must contain at least one job: $manifest")
    val jobs = lines.map { case (l, i) =>
      try Cli.job(defaults ++ Cli.fromJson(ujson.read(l)), adapter, cwd)
      catch { case e: Exception => throw new Cli.UsageError(s"$manifest line ${i + 1}: ${e.getMessage}") }
    }
    checkOutputs(jobs)
    System.err.println(s"[run-many] ${jobs.size} jobs, $n workers")
    val t0 = System.nanoTime()
    val results = if (persistent) {
      val collected = scala.collection.mutable.ArrayBuffer.empty[ujson.Obj]
      // Use the server path, including its poisoned-worker stop rule. Do not
      // submit later jobs after a native worker failed to stop.
      captureJobs(jobs)
      serve(defaults, lines.iterator.zip(jobs.iterator).map { case ((line, _), job) =>
        val request = ujson.read(line)
        request("seed") = job.seed
        ujson.write(request)
      }, reply => {
        if (reply.obj.contains("error")) throw new Cli.UsageError(reply("error").str)
        collected += ujson.Obj.from(reply("result").obj)
        System.err.println(s"[run-many] ${collected.size}/${jobs.size} ${summaryLine(collected.last)}")
      }, capturedBatch = true)
      collected.toArray
    } else runJobs(jobs, n, (k, r) => System.err.println(s"[run-many] $k/${jobs.size} ${summaryLine(r)}"))
    val wall = (System.nanoTime() - t0) / 1e9
    val counts = ujson.Obj.from(Status.all.map(s => s.name -> ujson.Num(results.count(_("status").str == s.name))))
    val summary = ujson.Obj("schema" -> "rvw.run-many/1", "core" -> adapter.core, "manifest" -> manifest.getPath,
      "jobs" -> jobs.size, "workers" -> n, "wall_s" -> math.round(wall * 10) / 10.0, "counts" -> counts,
      "runs" -> results.toSeq.zip(jobs).map { case (r, j) => ujson.Obj("elf" -> r("elf"), "out" -> j.out.getPath,
        "result" -> new File(j.out, "result.json").getPath, "status" -> r("status"),
        "seed" -> r("seed"), "cycles" -> r("cycles"), "instret" -> r("instret"), "wall_s" -> r("wall_s"),
        "message" -> r("message")) })
    o.get("summary").foreach { s =>
      val w = new PrintWriter(Cli.file(cwd, s)); try w.println(ujson.write(summary, indent = 2)) finally w.close()
    }
    emit(Cli.bool(o, "json"), summary,
      s"${jobs.size} runs in ${f"$wall%.1f"}s: " + Status.all.map(s => s"${counts(s.name).num.toInt} ${s.name}").mkString(", ") +
        results.filter(_("status").str != "pass").map(r => "\n  " + summaryLine(r)).mkString)
    if (results.length != jobs.length || results.exists(_("status").str == "error")) 2 else if (results.exists(_.obj.contains("inconclusive"))) 3 else if (results.forall(_("status").str == "pass")) 0 else 1
  }
}
