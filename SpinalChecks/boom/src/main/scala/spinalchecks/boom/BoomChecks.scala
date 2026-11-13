package spinalchecks.boom

import java.io.File

import spinal.core._
import spinal.core.sim._
import spinalchecks._
import spinalchecks.Json._

import rocketchip.config.Parameters
import _root_.boom.common._
import _root_.boom.sim.BoomSim
import _root_.boom.system.BoomSimTop

/** SpinalChecks on BOOM's simulation SoC (`boom.system.BoomSimTop`), applied from the outside.
  *
  *   BoomChecks elaborate <preset> <outDir> [--formal] [--mode assert|monitor|both] [--locations]
  *       Verilog of BoomSimTop with the checks, and <outDir>/BoomSimTop.checks.json
  *   BoomChecks run <preset> <outDir> [options] <elf>...
  *       Verilator build with the checks in Monitor mode; runs each ELF through the clone's harness
  *       (boom.sim.BoomSim.run: TileLink memory agent, tohost) and reports which checks fired:
  *       <outDir>/tests/<elf>.json per test, <outDir>/summary.json and summary.txt overall.
  *       --seed N (default 1), --max-cycles N (default 300000), --mem-latency N (fixed memory latency;
  *       default randomized timing), --wave (FST of every run, for `rvw formal from-sim`), --locations,
  *       --formal (include the formal asserts/assumes in the simulated Verilog), --mode (default monitor)
  *
  * BOOM-specific settings live here: the retirement progress watchdog on `io_trace_insns_*_valid`
  * and the waiver file `boom/waivers.txt` (override with SPINALCHECKS_WAIVERS; see ChecksConfig.fromEnv).
  */
object BoomChecks {
  val presets: Map[String, () => BoomTileParams] = Map(
    "small" -> (() => BoomConfigs.small()), "medium" -> (() => BoomConfigs.medium()),
    "large" -> (() => BoomConfigs.large()), "mega" -> (() => BoomConfigs.mega()), "giga" -> (() => BoomConfigs.giga()))

  val defaultWaivers = new File("waivers.txt")

  def checksConfig(mode: Mode, report: String): ChecksConfig = {
    val base = ChecksConfig(mode = mode, reportPath = report,
      streamCancellations = Seq("tile.frontend.f3.io_deq", "tile.frontend.f3_bpd_queue.io_deq",
        "tile.frontend.f4.io_deq", "tile.frontend.f4_bpd_queue.io_deq", "tile.lsu.stq_execute_queue.io_deq")
        .map(path => StreamCancelBinding(path, "io_flush", previous = true,
          "ChiselUtil.Queue clears occupancy on the previous flush edge; retain checks otherwise")),
      progress = Seq(ProgressSpec("retire", """io_trace_insns_\d+_valid""", sys.env.getOrElse("BOOM_PROGRESS_CYCLES", "20000").toInt)))
    val withWaivers = if (defaultWaivers.exists() && !sys.env.contains("SPINALCHECKS_WAIVERS")) base.withWaiverFile(defaultWaivers.getPath) else base
    val streams = new File("streams.txt")
    val withStreams = if (streams.exists() && !sys.env.contains("SPINALCHECKS_STREAMS"))
      withWaivers.withStreamFile(streams.getPath) else withWaivers
    ChecksConfig.fromEnv(withStreams)
  }

  private def flag(args: Seq[String], f: String) = args.contains(f)
  private def opt(args: Seq[String], f: String): Option[String] = args.sliding(2).collectFirst { case Seq(`f`, v) => v }
  private val valued = Set("--mode", "--seed", "--max-cycles", "--mem-latency")
  private def positional(args: Seq[String]): Seq[String] = {
    val out = Seq.newBuilder[String]
    var i = 0
    while (i < args.length) {
      if (valued(args(i))) i += 2
      else { if (!args(i).startsWith("--")) out += args(i); i += 1 }
    }
    out.result()
  }

  def top(implicit p: Parameters) = new BoomSimTop(BoomSim.resetVector, None, false)

  def main(argv: Array[String]): Unit = argv.toSeq match {
    case Seq("elaborate", preset, out, rest @ _*) =>
      implicit val p: Parameters = BoomSim.params(presets(preset)(), rvfi = false)
      val mode = opt(rest, "--mode").map(Mode.parse).getOrElse(Mode.Assert)
      val base0 = SpinalBoomConfig(out)
      val base = if (flag(rest, "--formal")) base0.includeFormal else base0
      val (cfg0, result) = SpinalChecks.install(base, checksConfig(mode, s"$out/BoomSimTop.checks.json"))
      val cfg = if (flag(rest, "--locations")) SpinalChecks.withLocations(cfg0)(top) else cfg0
      val t0 = System.nanoTime()
      cfg.generateVerilog(top)
      println(f"elaborated in ${(System.nanoTime() - t0) / 1e9}%.0f s: ${summaryLine(result)}")

    case Seq("run", preset, out, rest @ _*) =>
      val elfs = positional(rest)
      require(elfs.nonEmpty, "no ELF given")
      run(preset, out, elfs, rest)

    case _ =>
      System.err.println("usage: BoomChecks elaborate <preset> <out> [--formal] [--mode m] [--locations]\n" +
        "       BoomChecks run <preset> <out> [--seed N] [--max-cycles N] [--mem-latency N] [--wave] [--locations] [--mode m] <elf>...")
      sys.exit(2)
  }

  def summaryLine(r: ChecksResult): String = {
    val byKind = r.records.groupBy(_.kind).toSeq.sortBy(_._1).map { case (k, v) =>
      s"$k ${v.count(_.inserted)}" + (if (v.exists(!_.inserted)) s" (+${v.count(!_.inserted)} off)" else "")
    }
    s"${r.inserted.size} checks inserted, ${r.records.count(!_.inserted)} waived/disabled: ${byKind.mkString(", ")}"
  }

  def run(preset: String, out: String, elfs: Seq[String], args: Seq[String]): Unit = {
    implicit val p: Parameters = BoomSim.params(presets(preset)(), rvfi = false)
    val mode = opt(args, "--mode").map(Mode.parse).getOrElse(Mode.Monitor)
    val seed = opt(args, "--seed").map(_.toInt).getOrElse(1)
    val maxCycles = opt(args, "--max-cycles").map(_.toLong).getOrElse(300000L)
    val memLatency = opt(args, "--mem-latency").map(_.toInt)
    val wave = flag(args, "--wave")
    // --formal: the simulated Verilog also carries the formal asserts/assumes, so the same file can be
    // loaded by `rvw formal from-sim` (Verilator only sees the `$display` emulation).
    val base = if (flag(args, "--formal")) SpinalBoomConfig(s"$out/rtl").includeFormal else SpinalBoomConfig(s"$out/rtl")
    val checks = checksConfig(mode, s"$out/BoomSimTop.checks.json")
    require(checks.mode != Mode.Assert,
      "BoomChecks run needs monitor or both mode; check --mode and SPINALCHECKS_MODE")
    val (cfg0, result) = SpinalChecks.install(base, checks)
    val cfg = if (flag(args, "--locations")) SpinalChecks.withLocations(cfg0)(top) else cfg0
    val sc = SimConfig.withConfig(cfg).workspacePath(s"$out/sim").workspaceName(preset + (if (wave) "_wave" else ""))
    // Verilator traces arrays up to 32 words and signals up to 256 bits by default; a state for
    // `rvw formal from-sim` needs all memories and wide registers.
    // Verilator also skips signals starting with "_" unless --trace-underscore, and Spinal names its unnamed
    // registers and memories _zz_*.
    if (wave) sc.withFstWave.addSimulatorFlag("--trace-max-array 1048576").addSimulatorFlag("--trace-max-width 65536")
      .addSimulatorFlag("--trace-underscore")
    val t0 = System.nanoTime()
    val compiled = sc.withVerilator.allOptimisation.compile(top)
    println(f"built in ${(System.nanoTime() - t0) / 1e9}%.0f s: ${summaryLine(result)}")

    case class TestResult(name: String, elf: String, status: String, cycles: Long, retired: Long, wall: Double,
                          firings: Seq[ChecksSim.Firing], message: String)
    val results = elfs.map { elf =>
      val name = new File(elf).getName
      var firings: Seq[ChecksSim.Firing] = Nil
      var cycles, retired = 0L
      val t = System.nanoTime()
      val (status, message) = try {
        val r = BoomSim.run(compiled, elf, maxCycles = maxCycles, seed = seed, memLatency = memLatency,
          onFinish = (c, n) => { cycles = c; retired = n; firings = ChecksSim.firings(compiled.dut) })
        r match {
          case BoomSim.Pass => (ChecksSim.checkedStatus("pass", firings),
            if (firings.nonEmpty) s"${firings.size} generated checks fired" else null)
          case BoomSim.Fail(code) => ("fail", s"tohost fail code $code")
          case BoomSim.Timeout => ("timeout", null)
          case BoomSim.RvfiError(code) => ("rvfi_error", s"code $code")
        }
      } catch { case e: Throwable => ("error", e.toString) }
      val tr = TestResult(name, new File(elf).getAbsolutePath, status, cycles, retired, (System.nanoTime() - t) / 1e9, firings, message)
      ChecksSim.writeFile(s"$out/tests/$name.json", ChecksSim.runReport(result, firings, Seq(
        "test" -> name, "elf" -> tr.elf, "status" -> status, "message" -> message, "seed" -> seed,
        "cycles" -> cycles, "instret" -> retired, "mem_latency" -> memLatency.map(x => x: V).getOrElse(Null),
        "wall_s" -> Num(BigDecimal(tr.wall).setScale(1, BigDecimal.RoundingMode.HALF_UP)),
        "wave" -> (if (wave) s"$out/sim/${preset}_wave/$name" else null))))
      println(f"$name%-28s $status%-8s cycles=$cycles%-8d checks fired=${firings.size}" +
        firings.take(3).map(f => s" ${f.check.id}@${f.firstCycle}").mkString)
      tr
    }

    // Aggregate: which checks fired, in how many tests, first occurrence.
    val byCheck = results.flatMap(r => r.firings.map(f => (f.check.id, r, f))).groupBy(_._1).toSeq
      .sortBy { case (_, hits) => -hits.size }
    val summary = obj(
      "schema" -> "rvw.checks-summary/1",
      "core" -> "boom", "config" -> preset, "seed" -> seed, "mem_latency" -> memLatency.map(x => x: V).getOrElse(Null),
      "checks_report" -> result.reportFile,
      "inserted" -> result.inserted.size,
      "tests" -> arr(results.map(r => obj("test" -> r.name, "status" -> r.status, "cycles" -> r.cycles,
        "instret" -> r.retired, "fired" -> arr(r.firings.map(f => f.check.id: V)), "message" -> r.message): V)),
      "fired_checks" -> arr(byCheck.map { case (id, hits) =>
        val c = hits.head._3.check
        val first = hits.minBy(h => (h._3.firstCycle, h._2.name))
        obj("id" -> id, "kind" -> c.kind, "tests" -> hits.size, "total_count" -> hits.map(_._3.count.toLong).sum,
          "first" -> obj("test" -> first._2.name, "cycle" -> first._3.firstCycle),
          "source" -> c.location.map(_.toString), "detail" -> c.detail): V
      }))
    ChecksSim.writeFile(s"$out/summary.json", Json.write(summary) + "\n")
    val txt = new StringBuilder
    txt ++= s"BOOM $preset, seed $seed, ${results.size} tests: " +
      results.groupBy(_.status).toSeq.sortBy(_._1).map { case (s, v) => s"${v.size} $s" }.mkString(", ") + "\n"
    txt ++= s"${result.inserted.size} checks inserted; ${byCheck.size} fired\n"
    for ((id, hits) <- byCheck) {
      val c = hits.head._3.check
      txt ++= f"  $id%-90s tests=${hits.size}%3d  ${c.location.map(_.toString).getOrElse("")}\n"
    }
    ChecksSim.writeFile(s"$out/summary.txt", txt.toString)
    print(txt)
    if (results.exists(_.status != "pass")) sys.exit(1)
  }
}
