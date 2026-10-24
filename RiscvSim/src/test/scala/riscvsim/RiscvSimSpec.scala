package riscvsim

import java.io.File
import java.nio.file.Files

import org.scalatest.funsuite.AnyFunSuite

import spinal.core._
import spinal.core.sim._

/** The tiny RISC-V test programs (tests/programs/). Built on first use with tests/programs/build.sh;
  * if that fails (no RISC-V GCC), the tests that need them fail with the reason instead of being
  * cancelled. */
object TestPrograms {
  lazy val dir: File = {
    val d = new File("tests/programs/build").getAbsoluteFile
    if (!new File(d, "fail").isFile) {
      val log = Files.createTempFile("riscvsim-programs", ".log").toFile
      val rc = new ProcessBuilder("bash", "tests/programs/build.sh").redirectErrorStream(true)
        .redirectOutput(log).start().waitFor()
      if (rc != 0 || !new File(d, "fail").isFile)
        throw new IllegalStateException(s"tests/programs/build.sh failed (exit $rc; set RISCV_GCC to a " +
          s"riscv64-unknown-elf-gcc): ${new String(Files.readAllBytes(log.toPath)).trim.takeRight(600)}")
    }
    d
  }
  def apply(name: String): File = new File(dir, name)
}

class UnitSpec extends AnyFunSuite {
  test("ToHost merges byte lanes and decodes") {
    val t = new ToHost(0x1000)
    assert(t.onStore(0x2000, 3, 7).isEmpty)
    // a 4-byte store to the upper half, data replicated across the word like StoreGen
    assert(t.onStore(0x1004, 2, BigInt("0000000500000005", 16)) == Some(ToHost.Fail(0x500000000L >> 1, BigInt("500000000", 16), false)))
    val p = new ToHost(0x1000)
    assert(p.onStore(0x1000, 3, 1) == Some(ToHost.Pass))
    assert(ToHost.decode(7) == ToHost.Fail(3, 7, true))
  }

  test("MemWords tracks two words and completeness") {
    val m = new MemWords(0x100, 2)
    m.onStore(0x100, 3, BigInt(1234))
    assert(!m.complete && m.touched)
    m.onStore(0x108, 2, BigInt(99)) // low half only
    assert(!m.complete)
    m.onStore(0x10c, 2, BigInt(0)) // data lanes 4..7 from the replicated word
    assert(m.complete && m.words.toSeq == Seq(BigInt(1234), BigInt(99)))
  }

  test("AssertIndex turns Verilog format strings into patterns") {
    val f = Files.createTempFile("assert", ".v").toFile
    Files.writeString(f.toPath,
      """      $display("FAILURE rob: head %x != tail %0d"); // rob.scala:L812
        |      $display("ERROR plain message"); // lsu.scala:L40
        |""".stripMargin)
    val idx = AssertIndex.fromVerilog(Seq(f))
    assert(idx.size == 2)
    assert(idx.locate("FAILURE rob: head 1f != tail 3") == Seq("rob.scala:L812"))
    assert(idx.locate("ERROR plain message") == Seq("lsu.scala:L40"))
    assert(idx.locate("something else").isEmpty)
    assert(AssertIndex.isFailureLine("FAILURE x") && !AssertIndex.isFailureLine("[Progress] x"))
  }

  test("Cli parses flags, options, = forms and manifest lines") {
    val m = Cli.parse(Seq("--elf", "a", "--max_cycles=10", "--rvfi-trace", "--wave-from", "5"))
    assert(m == Map("elf" -> "a", "max-cycles" -> "10", "rvfi-trace" -> "true", "wave-from" -> "5"))
    assert(Cli.fromJson(ujson.read("""{"elf": "x", "max_cycles": 100, "wave": true, "seed": null}""")) ==
      Map("elf" -> "x", "max-cycles" -> "100", "wave" -> "true"))
    intercept[Cli.UsageError](Cli.parse(Seq("--bogus")))
    intercept[Cli.UsageError](Cli.fromJson(ujson.read("""{"bogus": 1}""")))
  }

  test("Cli rejects invalid boolean values before a monitor can be skipped") {
    for (key <- Cli.flags; bad <- Seq("tru", "yes", "2", "")) {
      intercept[Cli.UsageError](Cli.parse(Seq(s"--$key=$bad")))
      intercept[Cli.UsageError](Cli.fromJson(ujson.Obj(key -> bad)))
    }
    for (key <- Cli.flags) {
      assert(Cli.bool(Cli.parse(Seq(s"--$key")), key))
      for (value <- Seq("true", "True", "TRUE", "1", "false", "False", "FALSE", "0")) {
        val expected = value == "1" || value.equalsIgnoreCase("true")
        assert(Cli.bool(Cli.parse(Seq(s"--$key=$value")), key) == expected)
        assert(Cli.bool(Cli.fromJson(ujson.Obj(key -> value)), key) == expected)
      }
      for ((value, expected) <- Seq(ujson.Bool(true) -> true, ujson.Bool(false) -> false,
                                   ujson.Num(1) -> true, ujson.Num(0) -> false))
        assert(Cli.bool(Cli.fromJson(ujson.Obj(key -> value)), key) == expected)
      for (bad <- Seq(ujson.Num(2), ujson.Num(0.5), ujson.Null, ujson.Arr(), ujson.Obj()))
        intercept[Cli.UsageError](Cli.fromJson(ujson.Obj(key -> bad)))
    }
    intercept[Cli.UsageError](cliJob(cliDefaults ++ Map("rvfi-check" -> "true", "rvfi" -> "tru")))
  }

  private val cliDefaults = Map("elf" -> "unused.elf", "out" -> "unused-out", "config" -> "ok")
  private def cliJob(options: Map[String, String]) = Cli.job(cliDefaults ++ options, ToyAdapter, new File("."))

  for ((label, value) <- Seq("empty" -> "", "whitespace-only" -> "  ", "comma-only" -> ", ,")) {
    test(s"build rejects an empty config list ($label) before model selection") {
      val driver = new Driver(ToyAdapter)
      for (args <- Seq(Seq("--config", value), Seq(s"--config=$value"))) {
        val e = intercept[Cli.UsageError](driver.cmdBuild(Cli.parse(args)))
        assert(e.getMessage.contains("--config"), e.getMessage)
      }
    }
  }

  test("run-many rejects manifests without jobs before writing a summary") {
    val driver = new Driver(ToyAdapter)
    val dir = Files.createTempDirectory("empty-manifest")
    val manifest = dir.resolve("jobs.jsonl")
    val summary = dir.resolve("summary.json")
    for (content <- Seq("", "  \n\t\n", "# no jobs\n // no jobs\n")) {
      Files.writeString(manifest, content)
      val e = intercept[Cli.UsageError](driver.cmdRunMany(Map(
        "manifest" -> manifest.toString, "summary" -> summary.toString)))
      assert(e.getMessage.contains("manifest"), e.getMessage)
      assert(!Files.exists(summary))
    }
  }

  test("replay shell arguments round-trip every run option") {
    val driver = new Driver(ToyAdapter)
    val cwd = new File(".").getAbsoluteFile
    val all = cliDefaults ++ Map("elf" -> "ELF with 'quotes'", "out" -> "output with 'quotes'",
      "seed" -> Int.MinValue.toString, "max-cycles" -> Long.MaxValue.toString,
      "mem-latency" -> "0", "rvfi-trace" -> "true", "rvfi-check" -> "true",
      "wave" -> "true", "wave-from" -> "0", "wave-to" -> Long.MaxValue.toString,
      "konata" -> "true", "coverage" -> "true", "wall-timeout" -> "0.125")
    for (options <- Seq(all, cliDefaults + ("seed" -> "1"), all + ("wall-timeout" -> "1e300"))) {
      val original = Cli.job(options, ToyAdapter, cwd)
      // Let the shell decode the actual replay quoting. `set` does not execute the launcher.
      val shell = "set -- " + driver.replay(original) + "; printf '%s\\0' \"$@\""
      val process = new ProcessBuilder("bash", "-c", shell).start()
      val tokens = new String(process.getInputStream.readAllBytes(), java.nio.charset.StandardCharsets.UTF_8)
        .split("\u0000").toSeq
      assert(process.waitFor() == 0)
      val parsed = Cli.job(Cli.parse(tokens.drop(tokens.indexOf("run") + 1)), ToyAdapter, cwd)
      assert(parsed == original.copy(out = new File(original.out.getPath + "-replay")), driver.replay(original))
    }
  }

  test("Cli rejects non-finite and non-positive wall timeouts from CLI and manifests") {
    for (v <- Seq("NaN", "Infinity", "+Infinity", "-Infinity", "1e309", "0", "-0.5")) {
      for (options <- Seq(Cli.parse(Seq("--wall-timeout", v)), Cli.fromJson(ujson.Obj("wall_timeout" -> v)))) {
        val e = intercept[Cli.UsageError](cliJob(options))
        assert(e.getMessage.contains("wall-timeout"), s"$v: ${e.getMessage}")
      }
    }
    for (v <- Seq(Double.NaN, Double.PositiveInfinity, Double.NegativeInfinity)) {
      intercept[Cli.UsageError](cliJob(Cli.fromJson(ujson.Obj("wall_timeout" -> ujson.Num(v)))))
    }
    intercept[Cli.UsageError](cliJob(Cli.fromJson(ujson.read("""{"wall_timeout": 1e309}"""))))
    for (v <- Seq("0.001", "2.5", "1e300")) {
      assert(cliJob(Cli.parse(Seq("--wall-timeout", v))).wallTimeoutS.contains(v.toDouble))
      assert(cliJob(Cli.fromJson(ujson.Obj("wall_timeout" -> v.toDouble))).wallTimeoutS.contains(v.toDouble))
    }
  }

  test("Cli rejects integer overflow and invalid cycle and memory bounds") {
    val invalid = Seq(
      "seed" -> Seq("2147483648", "-2147483649", "4294967297", "9223372036854775808", "1.5"),
      "mem-latency" -> Seq("-1", "2147483648", "4294967297", "1.5"),
      "max-cycles" -> Seq("0", "-1", "9223372036854775808", "1.5"),
      "wave-from" -> Seq("-1", "9223372036854775808", "1.5"),
      "wave-to" -> Seq("0", "-1", "9223372036854775808", "1.5"))
    for ((key, values) <- invalid; v <- values) {
      for (options <- Seq(Cli.parse(Seq(s"--$key", v)), Cli.fromJson(ujson.Obj(key -> v)))) {
        val e = intercept[Cli.UsageError](cliJob(options))
        assert(e.getMessage.contains(key), s"$key=$v: ${e.getMessage}")
      }
      intercept[Cli.UsageError](cliJob(Cli.fromJson(ujson.Obj(key -> v.toDouble))))
    }
    for (seed <- Seq(Int.MinValue, -1, 0, Int.MaxValue)) assert(cliJob(Map("seed" -> seed.toString)).seed == seed)
    for (latency <- Seq(0, Int.MaxValue)) assert(cliJob(Map("mem-latency" -> latency.toString)).memLatency.contains(latency))
    val limits = cliJob(Map("max-cycles" -> Long.MaxValue.toString, "wave-from" -> "0", "wave-to" -> Long.MaxValue.toString))
    assert(limits.maxCycles == Long.MaxValue && limits.waveFrom.contains(0L) && limits.waveTo.contains(Long.MaxValue))
    intercept[Cli.UsageError](cliJob(Map("wave-from" -> "5", "wave-to" -> "5")))
  }

  test("Cli rejects manifest integer numbers that can lose precision or saturate") {
    for (key <- Seq("seed", "mem_latency", "max_cycles", "wave_from", "wave_to", "jobs");
         number <- Seq("9007199254740993", "9223372036854775807", "9223372036854775808", "-9223372036854775809", "1e309", "1.5")) {
      val e = intercept[Cli.UsageError](Cli.fromJson(ujson.read(s"""{"$key": $number}""")))
      assert(e.getMessage.contains(key), s"$key=$number: ${e.getMessage}")
    }
    val exact = Cli.fromJson(ujson.read("""{"max_cycles": 9007199254740991, "wave_from": 0, "wave_to": "9223372036854775807"}"""))
    val job = cliJob(exact)
    assert(job.maxCycles == 9007199254740991L && job.waveTo.contains(Long.MaxValue))
    val quoted = cliJob(Cli.fromJson(ujson.read("""{"max_cycles": "9007199254740993"}""")))
    assert(quoted.maxCycles == 9007199254740993L)
  }

  test("Cli validates every manifest job and worker count before starting a model") {
    val driver = new Driver(ToyAdapter)
    val dir = Files.createTempDirectory("invalid-cli")
    val manifest = dir.resolve("jobs.jsonl")
    val output = dir.resolve("out")
    val valid = ujson.Obj("elf" -> "unused.elf", "out" -> output.toString, "config" -> "ok")
    for ((key, bad) <- Seq("mem_latency" -> "-1", "mem_latency" -> "4294967297", "seed" -> "4294967297",
                           "max_cycles" -> "0", "wall_timeout" -> "NaN", "rvfi_check" -> "tru")) {
      val invalid = ujson.read(ujson.write(valid)).obj
      invalid(key) = ujson.Str(bad)
      Files.writeString(manifest, ujson.write(valid) + "\n" + ujson.write(ujson.Obj.from(invalid)) + "\n")
      val e = intercept[Cli.UsageError](driver.cmdRunMany(Map("manifest" -> manifest.toString)))
      assert(e.getMessage.contains("line 2"), e.getMessage)
      assert(!Files.exists(output))
    }
    Files.writeString(manifest, ujson.write(valid) + "\n")
    for (workers <- Seq("0", "-1", "2147483648", "4294967297", "1.5")) {
      val e = intercept[Cli.UsageError](driver.cmdRunMany(Map("manifest" -> manifest.toString, "jobs" -> workers)))
      assert(e.getMessage.contains("--jobs"), e.getMessage)
      assert(!Files.exists(output))
    }
  }

  test("RvfiRecord JSON has the C2 fields") {
    val r = RvfiRecord(order = 3, cycle = 52, insn = 0x297, trap = false, halt = false, intr = false, mode = 3, ixl = 2,
      rs1 = 0, rs1Rdata = 0, rs2 = 0, rs2Rdata = 0, rd = 5, rdWdata = BigInt("80000000", 16), pc = BigInt("80000000", 16),
      pcNext = BigInt("80000004", 16), memAddr = 0, memRmask = 0, memWmask = 0, memRdata = 0, memWdata = 0, memFault = false)
    val j = ujson.read(r.toJson)
    assert(j("order").num == 3 && j("pc").str == "0x80000000" && j("rd_wdata").str == "0x80000000" && j("insn").str == "0x297")
    assert(j.obj.keySet == Set("order", "cycle", "pc", "pc_next", "insn", "mode", "trap", "intr", "halt", "rs1", "rs1_rdata",
      "rs2", "rs2_rdata", "rd", "rd_wdata", "mem_addr", "mem_rmask", "mem_wmask", "mem_rdata", "mem_wdata", "mem_fault"))
  }

  test("RvfiTraceWriter writes a late-tval trap before the next cycle's records; cycles never decrease") {
    def rec(order: Int, cycle: Long, trap: Boolean = false) = RvfiRecord(order = order, cycle = cycle, insn = 0x13,
      trap = trap, halt = false, intr = false, mode = 3, ixl = 2, rs1 = 0, rs1Rdata = 0, rs2 = 0, rs2Rdata = 0, rd = 0,
      rdWdata = 0, pc = 0x80000000L + 4 * order, pcNext = 0x80000004L + 4 * order, memAddr = 0, memRmask = 0, memWmask = 0,
      memRdata = 0, memWdata = 0, memFault = false)
    val f = Files.createTempFile("rvfi", ".jsonl").toFile
    val w = new RvfiTraceWriter(f, ujson.Obj("xlen" -> 64))
    w.cycle(Seq(rec(0, 10, trap = true)), sys.error("no trap is waiting"))
    w.trapNextCycle(10, 2, intr = false)
    w.cycle(Seq(rec(1, 11)), BigInt(0x1234))   // an instruction retires the cycle after the trap
    w.trapNextCycle(12, 5, intr = false)
    w.end(13, "pass")                          // ended before the tval arrived
    w.close()
    val lines = scala.io.Source.fromFile(f).getLines().drop(1).map(ujson.read(_)).toSeq
    assert(lines.map(_("cycle").num.toLong) == Seq(10, 10, 11, 12, 13))
    assert(lines(1)("event").str == "trap" && lines(1)("tval").str == "0x1234" && lines(2)("order").num == 1)
    assert(lines(3)("event").str == "trap" && lines(3)("cause").str == "0x5" && lines(4)("event").str == "end")
    val g = new RvfiTraceWriter(Files.createTempFile("rvfi", ".jsonl").toFile, ujson.Obj("xlen" -> 64))
    g.write(rec(0, 11))
    intercept[IllegalStateException](g.trap(10, 2, 0, intr = false))
    g.close()
  }

  test("RvfiTraceWriter writes irq level events in cycle order") {
    val f = Files.createTempFile("rvfi", ".jsonl").toFile
    val w = new RvfiTraceWriter(f, ujson.Obj("xlen" -> 64))
    w.irq(1, 0)
    w.irq(5, 0x880)
    intercept[IllegalStateException](w.irq(4, 0))
    w.end(6, "pass")
    w.close()
    val lines = scala.io.Source.fromFile(f).getLines().drop(1).map(ujson.read(_)).toSeq
    assert(lines.map(l => (l("event").str, l("cycle").num.toLong)) == Seq(("irq", 1L), ("irq", 5L), ("end", 6L)))
    assert(lines(1)("levels").str == "0x880")
  }

  test("ELF snapshot resists caller mutations and cleans temporary files on exceptions") {
    val elf = new ElfFile(TestPrograms("fail"))
    val original = elf.bytes
    val hash = elf.sha256
    java.util.Arrays.fill(elf.bytes, 0.toByte)
    elf.segments.foreach(s => java.util.Arrays.fill(s.data, 0.toByte))
    elf.load((_, data) => java.util.Arrays.fill(data, 0.toByte))
    assert(elf.bytes.sameElements(original) && elf.sha256 == hash)
    val expected = new ElfFile(TestPrograms("fail"))
    assert(elf.segments.zip(expected.segments).forall { case (a, b) => a.data.sameElements(b.data) })
    val dir = Files.createTempDirectory("snapshot-cleanup")
    try {
      intercept[IllegalStateException] {
        elf.withSnapshotFile(dir.toFile) { f =>
          assert(Files.readAllBytes(f.toPath).sameElements(original))
          throw new IllegalStateException("consumer failed")
        }
      }
      assert(dir.toFile.list().isEmpty)
    } finally Files.delete(dir)
  }

  test("ElfFile reads the test programs") {
    val f = TestPrograms("fail")
    val e = new ElfFile(f)
    assert(e.xlen == 64 && e.entry == 0x80000000L && e.symbol("tohost").contains(0x80001000L))
    assert(e.segments.nonEmpty && e.sha256.length == 64)
  }
}

/** A toy "core" to test the driver end to end: counts cycles, asserts at `assertAt` (if >= 0). */
class Toy(assertAt: Int) extends Component {
  val io = new Bundle { val count = out UInt (16 bits) }
  val counter = Reg(UInt(16 bits)) init (0)
  counter := counter + 1
  io.count := counter
  if (assertAt >= 0) assert(counter =/= assertAt, "toy counter reached the forbidden value")
}

object ToyAdapter extends CoreAdapter {
  type Model = SimCompiled[Toy]
  def core = "toy"
  // ok: passes at cycle 100; bad: HDL assertion at 30; noisy: passes at 20000 and prints a
  // FAILURE-looking line every 10 cycles; slow: 2 ms per cycle; stuck: stops advancing at cycle 10;
  // flaky: the first run in the process fails (status assert at cycle 50), later runs pass at 100;
  // hangrerun: the first run in the process fails (status assert at cycle 50), later runs get stuck at 10
  val configs = Seq("ok", "bad", "noisy", "slow", "stuck", "flaky", "hangrerun")
  val flakyRuns = new java.util.concurrent.atomic.AtomicInteger(0)
  val hangRuns = new java.util.concurrent.atomic.AtomicInteger(0)
  def isa(config: String) = "rv64i"
  def xlen = 64
  def sourceDir = new File(".")
  def compile(key: ModelKey, work: File, cache: File): Model =
    RiscvSimConfig(key, work, cache, SpinalConfig()).compile(new Toy(key.config match {
      case "bad" => 30
      case "ok" => 1000
      case _ => -1
    }))
  override def generatedVerilog(m: Model): Seq[File] = new File(m.compiledPath, "rtl").listFiles().toSeq
  def run(model: Model, job: RunJob, ctx: RunContext): RunOutcome = {
    if (job.config == "flaky") flakyRuns.incrementAndGet()
    val hangRun = if (job.config == "hangrerun") hangRuns.incrementAndGet() else 0
    val (s, c, m, cycles) = SimSession.run(model, job, ctx) { (dut, ctl) =>
      dut.clockDomain.forkStimulus(10)
      dut.clockDomain.onSamplings {
        ctl.tick()
        val n = dut.io.count.toInt
        job.config match {
          case "noisy" =>
            if (n % 10 == 0) println("FAILURE unrelated assertion in another run")
            if (ctl.cycle == 20000) ctl.finish(Status.Pass)
          case "slow" => Thread.sleep(2)
          case "stuck" => if (n == 10) while (true) Thread.sleep(100)
          case "flaky" =>
            if (n == 50 && flakyRuns.get == 1) ctl.finish(Status.Assert, message = Some("flaky first run"))
            if (n == 100) ctl.finish(Status.Pass)
          case "hangrerun" =>
            if (n == 50 && hangRun == 1) ctl.finish(Status.Assert, message = Some("hangrerun first run"))
            if (n == 10 && hangRun > 1) while (true) Thread.sleep(100)
          case _ => if (n == 100) ctl.finish(Status.Pass)
        }
      }
      while (true) dut.clockDomain.waitSampling(1000)
    }
    RunOutcome(s, cycles, 0, c, m)
  }
}

class DriverSpec extends AnyFunSuite {
  lazy val elf = TestPrograms("fail")
  lazy val driver = {
    NativeOutput.start()
    new Driver(ToyAdapter)
  }
  def job(config: String, out: String, maxCycles: Long = 1000, wall: Option[Double] = None) = RunJob(elf, Files.createTempDirectory(out).toFile,
    config, seed = 1, seedPicked = false, maxCycles = maxCycles, memLatency = None, rvfiTrace = false,
    rvfiCheck = false, wave = false, waveFrom = None, waveTo = None, konata = false, coverage = false, wallTimeoutS = wall)
  def read(f: File): String = new String(Files.readAllBytes(f.toPath))

  test("pass, with result.json fields") {
    val r = driver.runOne(job("ok", "pass"))
    assert(r("status").str == "pass", r)
    assert(r("rtl_sha256").str.matches("[0-9a-f]{64}"))
    assert(r("schema").str == "rvw.run/1" && r("cycles").num > 90 && r("replay").str.contains("--seed 1"))
  }

  test("a direct launch cannot claim a clean source revision without its launcher record") {
    val j = job("ok", "uncaptured-source")
    val r = driver.runOne(j)
    assert(r("source")("core_rev") == ujson.Null)
    assert(r("source")("core_dirty") == ujson.Null)
    assert(r("source")("tools_rev") == ujson.Null)
    // A direct JVM has no pinned native lookups. It must refuse the result.
    assert(r("inconclusive").str == "input_not_captured:native_lookup", r)
    assert(ujson.read(read(new File(j.out, "result.json")))("inconclusive") == r("inconclusive"))
  }

  test("separate direct runs capture the ELF again") {
    val path = Files.createTempFile("riscvsim-direct-elf", ".elf")
    Files.copy(elf.toPath, path, java.nio.file.StandardCopyOption.REPLACE_EXISTING)
    val first = driver.runOne(job("ok", "direct-elf-first").copy(elf = path.toFile))
    Files.write(path, Files.readAllBytes(path) ++ Array[Byte](0))
    val second = driver.runOne(job("ok", "direct-elf-second").copy(elf = path.toFile))
    assert(first("elf_sha256") != second("elf_sha256"))
    assert(first("status").str == "pass" && second("status").str == "pass")
  }

  test("HDL assertion becomes status assert with its text and Scala location") {
    val r = driver.runOne(job("bad", "assert"))
    assert(r("status").str == "assert", r)
    val msg = r("message").str
    assert(msg.contains("toy counter reached the forbidden value"), msg)
    assert(msg.contains("RiscvSimSpec.scala:L"), msg)
  }

  test("timeout") {
    val r = driver.runOne(job("ok", "timeout", maxCycles = 50))
    assert(r("status").str == "timeout" && r("cycles").num == 50, r)
  }

  test("result.json is written atomically and replay is relative to the tools checkout") {
    val j = job("ok", "atomic")
    val r = driver.runOne(j)
    assert(j.out.list().forall(n => !n.startsWith(".result.json")), j.out.list().toSeq)
    assert(ujson.read(read(new File(j.out, "result.json")))("status").str == "pass")
    // The launcher is given as an absolute path inside the tools checkout (riscvsim.tools); the
    // build sets both for tests (Test / javaOptions), as boom/run.sh does for real runs.
    assert(sys.props.get("riscvsim.script").exists(_.endsWith("RiscvSim/boom/run.sh")), sys.props.get("riscvsim.script"))
    assert(r("replay").str.contains(" RiscvSim/boom/run.sh run "), r("replay"))
    assert(r("tools")("native_build") == NativeBuild.current.obj.getOrElse("provenance", ujson.Null))
  }

  test("concurrent runs: a failure keeps its own message, and run.log holds only its own lines") {
    for (c <- Seq("bad", "noisy")) driver.model(ModelKey(c), _ => ())
    val noisy = job("noisy", "noisy", maxCycles = 100000)
    val bad = job("bad", "bad")
    val rs = driver.runJobs(Seq(noisy, bad), 2)
    assert(rs(0)("status").str == "pass", rs(0))
    val rb = rs(1)
    assert(rb("status").str == "assert", rb)
    assert(rb("message").str.contains("toy counter reached the forbidden value"), rb)
    assert(!rb("message").str.contains("unrelated"), rb)
    assert(rb("details")("serial_rerun")("attributed").bool, rb)
    assert(rb("inconclusive").str == "input_not_captured:native_lookup", rb)
    assert(ujson.read(read(new File(bad.out, "result.json")))("message") == rb("message"))
    for (j <- Seq(noisy, bad)) {
      val log = read(new File(j.out, "run.log"))
      val other = if (j eq noisy) bad else noisy
      assert(!log.contains(s"run ${other.elf} config=${other.config}"), log)
    }
    assert(!read(new File(bad.out, "run.log")).contains("unrelated"))
  }

  test("an overlapped failure is written as attribution pending until the serial rerun") {
    // Review 2 N4: if the serial rerun never finishes, this first result stays final.
    val j = job("bad", "pending")
    val st = driver.newState(j)
    st.overlapped = true
    val r = driver.runOne(j, st)
    assert(r("status").str == "assert" && r("inconclusive").str.contains("attribution pending"), r)
    assert(ujson.read(read(new File(j.out, "result.json")))("inconclusive").str.contains("attribution pending"))
  }

  test("an overlapped failure that the serial rerun does not reproduce stays a failure, marked inconclusive") {
    // Review 2 N3: two such results of one test have the same message; without the mark rvw counted
    // them as the same failure ("still failing") and the gate accepted.
    for (c <- Seq("flaky", "noisy")) driver.model(ModelKey(c), _ => ())
    val noisy = job("noisy", "noisy2", maxCycles = 100000)
    val flaky = job("flaky", "flaky")
    val rs = driver.runJobs(Seq(noisy, flaky), 2)
    val rf = rs(1)
    assert(rf("status").str == "assert", rf)
    assert(!rf("details")("serial_rerun")("attributed").bool, rf)
    assert(rf("details")("serial_rerun")("rerun_status").str == "pass", rf)
    assert(rf("inconclusive").str.contains("could not attribute"), rf)
    assert(ujson.read(read(new File(flaky.out, "result.json")))("inconclusive") == rf("inconclusive"))
  }

  test("a serial rerun that hangs keeps the pending failure on disk, is abandoned, and the failure stays") {
    // Review 4 blocker: the rerun deleted the pending result.json and had no watchdog; when it hung,
    // the failure was lost and rvw's one-at-a-time retry of the "missing" test could pass.
    import scala.concurrent.{Await, Future, ExecutionContext}
    import scala.concurrent.duration._
    for (c <- Seq("hangrerun", "noisy")) driver.model(ModelKey(c), _ => ())
    val noisy = job("noisy", "noisy3", maxCycles = 100000)
    val hang = job("hangrerun", "hangrerun", maxCycles = 100000000L, wall = Some(1.0))
    val f = Future(driver.runJobs(Seq(noisy, hang), 2))(ExecutionContext.global)
    // while the rerun is stuck, the first attempt's result is on disk, failed and pending
    val deadline = System.nanoTime() + 30e9.toLong
    while (!new File(hang.out, "run.concurrent.log").isFile && System.nanoTime() < deadline) Thread.sleep(50)
    Thread.sleep(500)
    assert(!f.isCompleted)
    val during = ujson.read(read(new File(hang.out, "result.json")))
    assert(during("status").str == "assert" && during("inconclusive").str.contains("attribution pending"), during)
    assert(during("artifacts") == ujson.Obj("log" -> "run.concurrent.log"), during)
    val rs = Await.result(f, 60.seconds)
    val r = rs(1)
    assert(r("status").str == "assert" && r("inconclusive").str.contains("abandoned"), r)
    assert(r("details")("serial_rerun")("rerun_status").str == "abandoned" && !r("details")("serial_rerun")("attributed").bool, r)
    val disk = ujson.read(read(new File(hang.out, "result.json")))
    assert(disk("status").str == "assert" && disk("inconclusive") == r("inconclusive"), disk)
  }

  test("a slow run stops at its wall-clock limit") {
    val r = driver.runJobs(Seq(job("slow", "slow", maxCycles = 100000000L, wall = Some(1.0))), 1).head
    assert(r("status").str == "timeout" && r("wall_clock_timeout").bool, r)
    assert(r("message").str.contains("wall-clock"), r)
  }

  test("an output setup error ends the batch with an error result (review 11)") {
    // An --out that is a file made runOne throw before its catch; the worker's Future swallowed the
    // exception, the latch never completed and the batch hung despite --wall-timeout.
    import scala.concurrent.{Await, Future, ExecutionContext}
    import scala.concurrent.duration._
    val file = Files.createTempFile("riscvsim-out", ".file").toFile
    val bad = job("ok", "badout", wall = Some(0.1)).copy(out = file)
    val e = intercept[Cli.UsageError](driver.checkOutputs(Seq(bad)))
    assert(e.getMessage.contains("not a directory"), e)
    // runJobs without the check (an API caller): the worker's exception still ends the job.
    val rs = Await.result(Future(driver.runJobs(Seq(bad, job("ok", "afterbad")), 1))(ExecutionContext.global), 60.seconds)
    assert(rs(0)("status").str == "error" && rs(0)("details")("harness_error").bool, rs(0))
    assert(rs(0)("message").str.contains("harness error"), rs(0))
    assert(rs(1)("status").str == "pass", rs(1))
  }

  test("outputs that are one directory under two names are duplicates (review 11)") {
    val d = Files.createTempDirectory("riscvsim-alias").toFile
    val link = new File(d.getParentFile, d.getName + "-link")
    Files.createSymbolicLink(link.toPath, d.toPath)
    try {
      val a = job("ok", "a").copy(out = d)
      val e = intercept[Cli.UsageError](driver.checkOutputs(Seq(a, job("ok", "b").copy(out = link))))
      assert(e.getMessage.contains("same directory"), e)
      // A lexical alias of a directory that does not exist yet: created first, then compared.
      val x = new File(d, "x")
      new File(d, "y").mkdirs()                            // so that y/../x resolves to x
      val e2 = intercept[Cli.UsageError](driver.checkOutputs(Seq(job("ok", "c").copy(out = x),
        job("ok", "d").copy(out = new File(d, "y/../x")))))
      assert(e2.getMessage.contains("same directory"), e2)
      // Distinct directories pass; missing ones are created.
      val fresh = new File(d, "new/deeper")
      driver.checkOutputs(Seq(a, job("ok", "e").copy(out = fresh)))
      assert(fresh.isDirectory)
      // A dangling link cannot become a directory.
      val dangling = new File(d, "dangling")
      Files.createSymbolicLink(dangling.toPath, new File(d, "nowhere").toPath)
      intercept[Cli.UsageError](driver.checkOutputs(Seq(job("ok", "f").copy(out = dangling))))
    } finally link.delete()
  }

  test("a stuck run is abandoned by the watchdog and the batch goes on") {
    driver.model(ModelKey("stuck"), _ => ())
    val t0 = System.nanoTime()
    val stuck = job("stuck", "stuck", maxCycles = 100000000L, wall = Some(1.0))
    val rs = driver.runJobs(Seq(stuck, job("ok", "after")), 1)
    assert((System.nanoTime() - t0) / 1e9 < 30)
    assert(rs(0)("status").str == "timeout" && rs(0)("wall_clock_timeout").bool && rs(0)("details")("abandoned").bool, rs(0))
    assert(ujson.read(read(new File(stuck.out, "result.json")))("wall_clock_timeout").bool)
    assert(rs(1)("status").str == "pass", rs(1))
  }
}

/** No RTL build: replace the input while a fake compiler waits. */
class ElfSnapshotSpec extends AnyFunSuite {
  test("stable RTL publication copies the bytes used for its content hash") {
    val dir = Files.createTempDirectory("rtl-snapshot")
    val path = dir.resolve("input.v")
    val original = "module snapshot_before; endmodule".getBytes(java.nio.charset.StandardCharsets.UTF_8)
    Files.write(path, original)
    var reads = 0
    // Inject a source edit exactly when the old copy step reopened the input.
    val input = new File(path.toString) {
      override def toPath: java.nio.file.Path = {
        reads += 1
        if (reads == 2) Files.write(path, "module snapshot_after; endmodule".getBytes(java.nio.charset.StandardCharsets.UTF_8))
        path
      }
    }
    try {
      val published = new Driver(ToyAdapter).stableRtl(Seq(input)).get
      assert(Files.readAllBytes(new File(published, "input.v").toPath).sameElements(original))
      assert(reads == 1)
    } finally org.apache.commons.io.FileUtils.deleteDirectory(dir.toFile)
  }

  test("driver hashes the ELF bytes loaded after compilation even if the user path changes") {
    NativeOutput.start()
    for (remove <- Seq(false, true)) {
      val dir = Files.createTempDirectory("elf-race")
      val path = dir.resolve("input.elf")
      val original = Files.readAllBytes(TestPrograms("fail").toPath)
      Files.write(path, original)
      val started = new java.util.concurrent.CountDownLatch(1)
      val replaced = new java.util.concurrent.CountDownLatch(1)
      val adapter = new CoreAdapter {
        type Model = Unit
        def core = "snapshot-test"
        def configs = Seq("test")
        def xlen = 64
        def isa(config: String) = "rv64i"
        def sourceDir = dir.toFile
        def compile(key: ModelKey, work: File, cache: File): Unit = {
          started.countDown()
          require(replaced.await(10, java.util.concurrent.TimeUnit.SECONDS), "replacement timed out")
        }
        def run(model: Unit, job: RunJob, ctx: RunContext): RunOutcome = {
          val loaded = ctx.elf
          val memory = scala.collection.mutable.Map[Long, Byte]()
          loaded.load((a, data) => data.indices.foreach(i => memory(a + i) = data(i)))
          val expected = new ElfFile(TestPrograms("fail"))
          expected.load((a, data) => data.indices.foreach(i => assert(memory(a + i) == data(i))))
          assert(loaded.symbols == expected.symbols)
          assert(ToHost.find(loaded) == ToHost.find(expected))
          assert(loaded.bytes.sameElements(original))
          loaded.withSnapshotFile(job.out) { f =>
            assert(Files.readAllBytes(f.toPath).sameElements(original))
          }
          assert(!job.out.list().exists(_.startsWith(".elf-snapshot-")))
          RunOutcome(Status.Fail, 1, 1, failCode = Some(3),
            details = ujson.Obj("loaded_sha256" -> loaded.sha256))
        }
      }
      val writer = new Thread(() => {
        if (started.await(10, java.util.concurrent.TimeUnit.SECONDS)) {
          if (remove) Files.delete(path)
          else {
            val next = dir.resolve("rebuilt.elf")
            Files.copy(TestPrograms("bench").toPath, next)
            Files.move(next, path, java.nio.file.StandardCopyOption.REPLACE_EXISTING,
              java.nio.file.StandardCopyOption.ATOMIC_MOVE)
          }
          replaced.countDown()
        }
      })
      writer.start()
      try {
        val job = RunJob(path.toFile, dir.resolve("out").toFile, "test", 1, false, 100, None,
          false, false, false, None, None, false, false)
        val result = new Driver(adapter).runOne(job)
        assert(result("status").str == "fail", result)
        assert(result("fail_code").num == 3)
        assert(result("elf_sha256").str == ElfFile.sha256(original))
        assert(result("elf_sha256") == result("details")("loaded_sha256"))
      } finally {
        replaced.countDown()
        writer.join(11000)
        org.apache.commons.io.FileUtils.deleteDirectory(dir.toFile)
      }
    }
  }
}
