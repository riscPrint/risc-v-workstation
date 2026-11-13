package spinaltrace

import java.io.File

import spinal.core._
import spinal.core.sim._
import spinalwaves.{HglNaming, SimLayout, SourceLocator, SpinalWavesSim}

import scala.sys.process._

/** What the debugger does when a simulation fails. */
object OnFailure extends Enumeration {
  /** Print the trace commands only. */
  val Print = Value
  /** Print the commands and run the CLI (writes dynpdg.json and prints its summary). */
  val RunCli = Value
  /** Ask on stdin like ChiselTrace's debugger: continue? (Y/n/t/dt). Only when a console is attached. */
  val Prompt = Value
}

/** Options of the SpinalTrace simulation helper. Environment variables override the defaults so CI and
  * tests never block: `SPINALTRACE_NONINTERACTIVE=1` (no prompt), `SPINALTRACE_ON_FAILURE=print|cli|prompt`,
  * `SPINALTRACE_CLI` / `SPINALTRACE_GUI` (binaries). */
case class SpinalTraceSimOptions(
    extract: ExtractOptions = ExtractOptions(),
    onFailure: OnFailure.Value = SpinalTraceSimOptions.defaultOnFailure,
    cliPath: String = sys.env.getOrElse("SPINALTRACE_CLI", "spinaltrace-cli"),
    guiPath: String = sys.env.getOrElse("SPINALTRACE_GUI", "spinaltrace"),
    /** Pass the SpinalWaves HGLDD to the trace so values are shown with their Spinal types. */
    typedValues: Boolean = true,
    /** Sim-time limit per doSim (None: unlimited); stops hung testbenches from writing unbounded VCDs. */
    simTimeout: Option[Long] = spinalwaves.SimGuard.defaultTimeout
)

object SpinalTraceSimOptions {
  def defaultOnFailure: OnFailure.Value = {
    val nonInteractive = sys.env.get("SPINALTRACE_NONINTERACTIVE").exists(v => v.nonEmpty && v != "0") || System.console() == null
    sys.env.get("SPINALTRACE_ON_FAILURE").map(_.toLowerCase) match {
      case Some("cli")                       => OnFailure.RunCli
      case Some("prompt") if !nonInteractive => OnFailure.Prompt
      case Some(_)                           => OnFailure.Print
      case None                              => if (nonInteractive) OnFailure.Print else OnFailure.Prompt
    }
  }
}

/** Failure raised by [[SpinalTraceSim.expect]]; carries the signal so the trace has a criterion. */
class ExpectationFailed(val signal: String, val expected: BigInt, val observed: BigInt, val time: Long)
    extends AssertionError(s"Expectation failed on $signal at t=$time: observed value $observed != $expected")

/** One prepared trace of a failure. */
case class TraceSession(pdg: File, vcd: File, hgldd: Option[File], criterion: String, atTime: Option[Long],
                        output: File, cliPath: String, guiPath: String, topModule: String, extraScopes: Seq[String]) {
  private def common: Seq[String] =
    Seq("-s", criterion, "-p", pdg.getAbsolutePath, "-v", vcd.getAbsolutePath) ++
      hgldd.toSeq.flatMap(h => Seq("--hgldd-path", h.getAbsolutePath)) ++
      Seq("--top-module", topModule) ++ (if (extraScopes.nonEmpty) "--extra-scopes" +: extraScopes else Nil) ++
      atTime.toSeq.flatMap(t => Seq("--at-time", t.toString))
  def cliCommand(dataOnly: Boolean = false): Seq[String] =
    Seq(cliPath, "dyn-pdg") ++ common ++ (if (dataOnly) Seq("--data-only") else Nil) ++
      Seq("-o", output.getAbsolutePath, "--summary")
  def guiCommand(dataOnly: Boolean = false): Seq[String] =
    Seq(guiPath) ++ common ++ (if (dataOnly) Seq("--data-only") else Nil)
  def shell(cmd: Seq[String]): String = cmd.map(a => if (a.exists(" '\"$".contains(_))) s"'$a'" else a).mkString(" ")
}

/** The simulation failed; `session` holds the prepared trace, `cliOutput` the CLI summary when it ran. */
class SpinalTraceFailure(val cause: Throwable, val session: Option[TraceSession], val cliOutput: Option[String])
    extends Exception(s"${cause.getMessage}" + session.map(s => s"\n[SpinalTrace] trace with: ${s.shell(s.cliCommand())}").getOrElse(""), cause)

/** Compiled design with SpinalTrace instrumentation, HGLDD (when available) and VCD tracing. */
class TracedSim[T <: Component](val compiled: SimCompiled[T], val pdg: File, val hgldd: Option[File], opts: SpinalTraceSimOptions) {
  def workspace: File = compiled.compiledPath

  /** Run a simulation; on failure prepare (and depending on the options run) a SpinalTrace session. */
  def doSim(name: String = "test", seed: Int = 42)(body: T => Unit): Unit = {
    val allocated = compiled.testNameMap.get(name) match {
      case Some(n) if n > 0 => s"${name}_$n"
      case _                => name
    }
    @volatile var lastTime = 0L
    try {
      compiled.doSim(name, seed) { dut =>
        onSimEnd { lastTime = simTime() }
        spinalwaves.SimGuard.arm(opts.simTimeout)
        try body(dut)
        catch { case e: Throwable => lastTime = simTime(); throw e }
      }
    } catch {
      case e: Throwable => handleFailure(e, allocated, lastTime)
    }
  }

  /** VCD of a test, at SpinalSim's configured path (as SpinalWaves computes it). */
  def waveFile(test: String): Option[File] = {
    val prefix = spinalwaves.SpinalCompat.waveFilePrefix(compiled.simConfig).map(_.replace("$TEST", test) + "_").getOrElse("")
    Some(new File(compiled.simConfig.getTestPath(test), prefix + "wave.vcd")).filter(_.isFile)
  }

  private def criterionFor(e: Throwable): Option[String] = e match {
    case x: ExpectationFailed => Some(s"signal:${x.signal}")
    case _ if isHdlAssertion(e) =>
      // A Verilog assertion: point at the design's assert statement when there is exactly one.
      val asserts = PdgFile.statementNames(pdg).filter(_.startsWith("assert_"))
      if (asserts.size == 1) Some(s"statement:${asserts.head}") else None
    case _ => None
  }

  private def isHdlAssertion(e: Throwable): Boolean =
    e.getClass.getName == "spinal.sim.SimFailure" && Option(e.getMessage).exists(_.toLowerCase.contains("assertion"))

  /** Run a helper binary without letting a missing binary hide the simulation failure. */
  private def run(cmd: Seq[String], log: ProcessLogger): Option[Int] =
    scala.util.Try(Process(cmd).!(log)).recover { case ex: Throwable =>
      println(s"[SpinalTrace] could not run ${cmd.head}: ${ex.getMessage}"); -1
    }.toOption

  private def handleFailure(e: Throwable, test: String, lastTime: Long): Unit = {
    val failTime = e match {
      case x: ExpectationFailed => x.time
      case _                    => lastTime
    }
    // A testbench read right after waitSampling() and an HDL assertion both see the values from *before*
    // the clock edge at `failTime`, i.e. the cycle that ends at that edge: trace the cycle containing t-1.
    val time = SpinalTraceSim.traceTime(failTime)
    val session = for {
      vcd  <- waveFile(test)
      crit <- criterionFor(e)
    } yield {
      val top    = compiled.report.toplevelName
      val scopes = scala.util.Try(SimLayout.extraScopes(vcd, top)).getOrElse(Seq("TOP", top))
      TraceSession(pdg, vcd, if (opts.typedValues) hgldd else None, crit, Some(time),
        new File(new File(new File(workspace, "spinaltrace"), test), "dynpdg.json"), opts.cliPath, opts.guiPath, top, scopes)
    }

    println(s"[SpinalTrace] Simulation '$test' failed at t=$failTime: ${e.getMessage}")
    session match {
      case None =>
        println(s"[SpinalTrace] No trace criterion known for this failure; trace manually with e.g.\n" +
          s"[SpinalTrace]   ${opts.cliPath} dyn-pdg -s signal:<rtl path> -p ${pdg.getAbsolutePath} -v ${waveFile(test).map(_.getAbsolutePath).getOrElse("<vcd>")} --at-time $time --summary")
        throw new SpinalTraceFailure(e, None, None)
      case Some(s) =>
        println(s"[SpinalTrace] CLI: ${s.shell(s.cliCommand())}")
        println(s"[SpinalTrace] GUI: ${s.shell(s.guiCommand())}")
        opts.onFailure match {
          case OnFailure.Print => throw new SpinalTraceFailure(e, Some(s), None)
          case OnFailure.RunCli =>
            s.output.getParentFile.mkdirs()
            val out = new StringBuilder
            val code = run(s.cliCommand(), ProcessLogger(l => out.append(l).append('\n'), l => out.append(l).append('\n'))).getOrElse(-1)
            println(out.toString.linesIterator.map("[SpinalTrace] " + _).mkString("\n"))
            if (code != 0) println(s"[SpinalTrace] CLI exited with $code")
            throw new SpinalTraceFailure(e, Some(s), Some(out.toString))
          case OnFailure.Prompt if System.console() == null => throw new SpinalTraceFailure(e, Some(s), None)
          case OnFailure.Prompt =>
            print(s"> Assertion failed. Context: ${e.getMessage}\n> continue? (Y/n/t/dt) ")
            Console.flush()
            val answer = Option(scala.io.StdIn.readLine()).map(_.trim.toLowerCase).getOrElse("n")
            answer match {
              case "" | "y" => println("[SpinalTrace] continuing")
              case "t" | "dt" =>
                run(s.guiCommand(dataOnly = answer == "dt"), ProcessLogger(println(_), println(_)))
                throw new SpinalTraceFailure(e, Some(s), None)
              case _ => throw new SpinalTraceFailure(e, Some(s), None)
            }
        }
    }
  }
}

/** ChiselTrace's `ChiselTraceDebugger`, for SpinalHDL simulations. */
object SpinalTraceSim {

  /** Compile with SpinalTrace (two-pass locations + naming phase), VCD tracing and HGLDD (if an emitter is
    * given), and write `W/spinaltrace/pdg.json`. */
  def compile[T <: Component](simConfig: SpinalSimConfig = SimConfig, opts: SpinalTraceSimOptions = SpinalTraceSimOptions())(gen: => T): TracedSim[T] = {
    val cfg = simConfig.copy()
    cfg._spinalConfig = SpinalTrace.instrument(cfg._spinalConfig)
    val roots = opts.extract.sourceRoots.map(_.toPath) ++ SourceLocator.defaultRoots
    // SpinalWaves does the two-pass (located) elaboration, the Verilator/VCD compile and the HGLDD.
    val waves    = SpinalWavesSim(config = cfg, sourceRoots = roots, launchViewer = false).compile(gen)
    val compiled = waves.compiled
    val pdg      = PdgExtractor.extractTo(compiled.report, new File(new File(compiled.compiledPath, "spinaltrace"), "pdg.json"), opts.extract)
    println(s"[SpinalTrace] PDG written to ${pdg.getAbsolutePath}")
    new TracedSim(compiled, pdg, Some(waves.hglddDir.toFile), opts)
  }

  /** VCD time to trace for a check done at simulation time `t`: SpinalSim reads (and HDL assertions)
    * right at a clock edge observe the pre-edge values, which belong to the cycle ending at that edge. */
  def traceTime(t: Long): Long = math.max(0L, t - 1)

  /** Like ChiselSim's `expect`: compares a signal and fails with the signal as trace criterion. */
  def expect(signal: BaseType, value: BigInt): Unit = {
    val observed = signal match {
      case b: Bool => if (b.toBoolean) BigInt(1) else BigInt(0)
      case b: BitVector => b.toBigInt
      case e: SpinalEnumCraft[_] => BigInt(e.toEnum.position)
      case other => throw new IllegalArgumentException(s"expect: unsupported signal type ${other.getClass.getSimpleName}")
    }
    if (observed != value) throw new ExpectationFailed(HglNaming.rtlPath(signal), value, observed, simTime())
  }
  def expect(signal: BaseType, value: Boolean): Unit = expect(signal, if (value) BigInt(1) else BigInt(0))
  def expect(signal: BaseType, value: Int): Unit = expect(signal, BigInt(value))
}

/** Minimal reader for statement names in a pdg.json (used to pick assertion criteria). */
object PdgFile {
  def statementNames(pdg: File): Seq[String] = {
    val json = ujson.read(scala.io.Source.fromFile(pdg, "UTF-8").mkString)
    json("vertices").arr.map(_("name").str).toSeq.distinct
  }
}
