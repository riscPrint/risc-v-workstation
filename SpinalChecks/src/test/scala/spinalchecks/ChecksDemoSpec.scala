package spinalchecks

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._
import spinal.lib.sim.{StreamDriver, StreamReadyRandomizer}
import spinalchecks.demo.ChecksDemo

import scala.io.Source

class ChecksDemoSpec extends AnyFunSuite {
  val workspace = "simWorkspace"

  /** Elaborate `ChecksDemo(bugs)` with checks in Monitor mode, run 2000 random cycles, return the ids
    * of the checks that fired and the report. */
  def run(bugs: Set[String], checks: ChecksConfig = ChecksConfig(mode = Mode.Both,
          progress = Seq(ProgressSpec("heartbeat", "io_heartbeat", 40)))): (Set[String], ChecksResult) = {
    val name = if (bugs.isEmpty) "clean" else bugs.toSeq.sorted.mkString("_")
    val base = SpinalConfig(targetDirectory = s"generated/demo_$name")
    val located = SpinalChecks.withLocations(base)(new ChecksDemo(bugs))
    val (cfg, result) = SpinalChecks.install(located, checks.copy(reportPath = s"generated/demo_$name/ChecksDemo.checks.json"))
    var fired = Set.empty[String]
    SimConfig.withConfig(cfg).workspacePath(workspace).workspaceName(s"demo_$name").withVerilator
      .compile(new ChecksDemo(bugs)).doSim(seed = 42) { dut =>
        dut.clockDomain.forkStimulus(10)
        dut.io.sel #= 0
        StreamDriver(dut.io.in, dut.clockDomain) { p => p.randomize(); true }
        StreamReadyRandomizer(dut.io.out, dut.clockDomain)
        dut.clockDomain.onSamplings { dut.io.sel.randomize() }
        dut.clockDomain.waitSampling(3000)
        fired = ChecksSim.firings(dut).map(_.check.id).toSet
        ChecksSim.writeRunReport(dut, s"generated/demo_$name/run.json")
      }
    (fired, result)
  }

  test("clean design: every kind is inserted and nothing fires") {
    val (fired, r) = run(Set.empty)
    val kinds = r.inserted.map(_.kind).toSet
    assert(Set(Kind.StreamValidHold, Kind.StreamPayloadStable, Kind.MemIndex, Kind.VecIndex, Kind.EnumLegal,
      Kind.FsmStateLegal, Kind.Progress).subsetOf(kinds), kinds)
    assert(fired.isEmpty, fired)
    // the report exists, has source locations pointing at the demo
    val json = Source.fromFile(r.reportFile).mkString
    assert(json.contains("\"schema\": \"rvw.checks/1\""))
    assert(json.contains("Demos.scala"), "source locations missing")
  }

  for ((bug, expect) <- Seq(
    "hold" -> "stream.valid_hold:fifo.io_push",
    "stable" -> "stream.payload_stable:fifo.io_push",
    "mem" -> "mem.index:mem_port0_write",
    "vec" -> "vec.index:vidx_of3",
    "enum" -> "enum.legal:mode",
    "hang" -> "progress.watchdog:heartbeat")) test(s"planted bug '$bug' fires $expect only") {
    val (fired, _) = run(Set(bug))
    assert(fired == Set(expect), fired)
  }

  test("waivers and disables remove checks and are reported") {
    val (fired, r) = run(Set("hold"), ChecksConfig(mode = Mode.Monitor,
      waivers = Seq(Waiver("stream.*:fifo.io_push", "demo waiver")), disable = Seq("vec.*")))
    // An exact waiver at the child does not waive the parent's check of the same stream.
    assert(fired == Set("stream.valid_hold:stage"), fired)
    assert(r.records.exists(c => c.id == "stream.valid_hold:fifo.io_push" && c.status == "waived"))
    assert(r.inserted.exists(_.id == "stream.valid_hold:stage"))
    assert(r.records.filter(_.kind == Kind.VecIndex).forall(_.status == "disabled"))
  }
}
