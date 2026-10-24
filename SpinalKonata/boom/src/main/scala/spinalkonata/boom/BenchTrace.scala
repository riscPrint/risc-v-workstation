package spinalkonata.boom

import java.io.File
import java.nio.file.{Files, StandardCopyOption}
import _root_.boom.sim.BoomSim
import _root_.boom.common.BoomConfigs

/** Bounded evidence runner: compile once, reuse the model for all supplied ELFs. */
object BenchTrace {
  def main(args: Array[String]): Unit = {
    require(args.length >= 2, "BenchTrace OUT_DIRECTORY ELF [ELF ...]")
    val out = new File(args(0)).getAbsoluteFile
    val env = Seq("KONATA_CONFIG", "KONATA_MAX_CYCLES", "RISCV_OBJDUMP", "KONATA_PYTHON", "PATH")
      .map(name => name -> sys.env.get(name)).toMap
    val environment = ujson.Obj.from(env.toSeq.map { case (name, value) =>
      name -> value.map(ujson.Str(_)).getOrElse(ujson.Null) })
    val config = env("KONATA_CONFIG").getOrElse("large")
    val params = config match {
      case "small" => BoomConfigs.small()
      case "large" => BoomConfigs.large()
      case other => sys.error(s"unsupported evidence config $other")
    }
    val maxCycles = env("KONATA_MAX_CYCLES").getOrElse("300000").toLong
    require(maxCycles > 0 && maxCycles <= (1L << 53), "max cycles must be a positive exact JSON integer")
    val seed = 1
    out.mkdirs()
    val captureDir = Files.createTempDirectory(out.toPath, ".inputs-").toFile
    // Capture the whole batch before compilation. Later ELF changes do not enter any run.
    val inputs = args.drop(1).map(path => ElfInput.capture(new File(path), captureDir))
    val objdumpName = env("RISCV_OBJDUMP").getOrElse(
      "riscv64-unknown-elf-objdump")
    val objdump = ToolInput.capture(objdumpName, captureDir)
    val assemblies = inputs.map(input => CapturedDisasm(input.elf, objdump, captureDir))
    val repo = new File(sys.props("spinalkonata.repo"))
    val reporter = FileInput.capture(new File(repo, "SpinalKonata/scripts/trace_report.py"), captureDir)
    val python = ToolInput.capture(env("KONATA_PYTHON").getOrElse("python3"), captureDir)
    val compiled = BoomSim.compile(params, config, konata = true)
    for ((input, assembly) <- inputs.zip(assemblies)) {
      val elf = input.record("resolved").str
      val destination = new File(out, new File(input.record("source").str).getName.stripSuffix(".riscv"))
      require(!destination.exists(), s"refusing to overwrite evidence directory $destination")
      val dir = Files.createTempDirectory(out.toPath, ".building-").toFile
      var cycles, instret = 0L
      val start = System.nanoTime()
      val result = ProbeRun.run(compiled, input.elf, assembly, maxCycles = maxCycles, seed = seed,
        konata = Some(new File(dir, "konata.log")), memLatency = Some(20),
        onFinish = (c, i) => { cycles = c; instret = i })
      val status = result match {
        case BoomSim.Pass => "pass"
        case BoomSim.Fail(_) => "fail"
        case BoomSim.Timeout => "timeout"
        case BoomSim.RvfiError(_) => "rvfi_error"
      }
      val json = ujson.Obj("schema" -> "rvw.run/1", "core" -> "boom", "config" -> config,
        "elf" -> elf, "elf_sha256" -> input.record("sha256"), "seed" -> seed, "max_cycles" -> ujson.Num(maxCycles.toDouble),
        "mem_latency" -> 20, "status" -> "error", "observed_status" -> status,
        "inconclusive" -> "input_not_captured:compiled_model: standalone harness does not capture the compiler, classpath, RTL dependencies and build environment",
        "capture" -> ujson.Obj("elf" -> input.record, "objdump" -> objdump.record,
          "python" -> python.record, "reporter" -> reporter.record, "env" -> environment), "cache_key" -> ujson.Null, "cycles" -> ujson.Num(cycles.toDouble),
        "instret" -> ujson.Num(instret.toDouble), "wall_s" -> (System.nanoTime() - start).toDouble / 1e9,
        "artifacts" -> ujson.Obj("konata" -> "konata.log",
          "perf" -> "report.json", "perf_text" -> "report.txt"),
        "counter_scope" -> "BoomSim.onFinish: cycles in 100-cycle polling units after 10-sample warmup; retirement callback samples start earlier. Kanata R ends one cycle after commit.",
        "replay" -> s"cd SpinalKonata/boom && ../../scripts/with-lock.sh boom sbt 'runMain spinalkonata.boom.BenchTrace OUT $elf'")
      Files.writeString(new File(dir, "result.json").toPath, ujson.write(json, indent = 2) + "\n")
      // Measurement is useful even when C8 cannot establish a C1 verdict. Do not
      // give the analyzer C1 counters or ask it to promote the observed outcome.
      python.run(reporter.path.toString, dir.toString, new File(repo, "rvw/src").toString)
      val entries = Files.walk(dir.toPath)
      try entries.forEach(path => require(path.toFile.setReadOnly(), s"cannot seal $path"))
      finally entries.close()
      objdump.verify()
      python.verify()
      Files.move(dir.toPath, destination.toPath, StandardCopyOption.ATOMIC_MOVE)
      println(s"EVIDENCE ${new File(elf).getName}: inconclusive observed=$status cycles=$cycles instret=$instret dir=$destination")
      require(status == "pass", s"bounded run did not pass: $result")
    }
    Console.err.println("BenchTrace: input_not_captured:compiled_model: C1 results are inconclusive and uncached. " +
      "Trace-only measurements are in report.json and report.txt; see result.json for the cause.")
  }
}
