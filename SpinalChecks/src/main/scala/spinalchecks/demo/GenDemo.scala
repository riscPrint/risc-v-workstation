package spinalchecks.demo

import spinal.core._
import spinal.core.sim._
import spinal.lib.sim.{StreamDriver, StreamReadyRandomizer}
import spinalchecks._

/** Command-line generators for the demo designs.
  *
  *   GenDemo verilog <checks|deep> <outDir> [bugs,comma,separated|none] [--mode assert|monitor|both]
  *       Verilog (with `includeFormal`) and the checks report, for SymbiYosys and `rvw formal`.
  *   GenDemo sim-deep <outDir> <cycles> [seed]
  *       Runs DeepBugDemo (the same Verilog as `verilog deep`) in Verilator with random stimulus and
  *       writes an FST trace `<outDir>/wave.fst`, for `rvw formal from-sim`.
  */
object GenDemo {
  def base(out: String): SpinalConfig =
    SpinalConfig(targetDirectory = out, defaultConfigForClockDomains = ClockDomainConfig(resetKind = SYNC)).includeFormal

  def gen(design: String, bugs: Set[String]): Component = design match {
    case "checks" => new ChecksDemo(bugs)
    case "deep" => new DeepBugDemo(bug = !bugs.contains("nobug"))
  }

  def main(args: Array[String]): Unit = args.toList match {
    case "verilog" :: design :: out :: rest =>
      val bugs = rest.headOption.filter(!_.startsWith("--")).map(b => if (b == "none") Set.empty[String] else b.split(",").toSet).getOrElse(Set.empty)
      val mode = rest.sliding(2).collectFirst { case "--mode" :: m :: Nil => Mode.parse(m) }.getOrElse(Mode.Assert)
      val progress = if (design == "checks") Seq(ProgressSpec("heartbeat", "io_heartbeat", 40)) else Nil
      val (c, _) = SpinalChecks.install(base(out), ChecksConfig(mode = mode, progress = progress))
      SpinalChecks.withLocations(c)(gen(design, bugs)).generateVerilog(gen(design, bugs))
    case "sim-deep" :: out :: cycles :: rest =>
      val seed = rest.headOption.map(_.toInt).getOrElse(1)
      val (cfg0, _) = SpinalChecks.install(base(out), ChecksConfig(mode = Mode.Assert, reportPath = s"$out/DeepBugDemo.checks.json"))
      val cfg = SpinalChecks.withLocations(cfg0)(new DeepBugDemo(bug = true))
      SimConfig.withConfig(cfg).withFstWave.workspacePath(s"$out/sim").workspaceName("deep").withVerilator
        .compile(new DeepBugDemo(bug = true)).doSim(seed = seed) { dut =>
          dut.clockDomain.forkStimulus(10)
          StreamDriver(dut.io.in, dut.clockDomain) { p => p.randomize(); true }
          StreamReadyRandomizer(dut.io.out, dut.clockDomain)
          dut.clockDomain.waitSampling(cycles.toInt)
          println(s"served ${dut.io.served.toInt} packets in $cycles cycles")
        }
    case _ =>
      System.err.println("usage: GenDemo verilog <checks|deep> <outDir> [bugs|none] [--mode m] | sim-deep <outDir> <cycles> [seed]")
      sys.exit(2)
  }
}
