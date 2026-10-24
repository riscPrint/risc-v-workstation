package spinalchecks

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._
import spinal.lib._

/** A child's valid alone does not establish coverage of the parent's stalled stream. */
class ReadyWiringSpec extends AnyFunSuite {
  class Sink(ready: Boolean) extends Component {
    val input = slave(Stream(Bits(8 bits)))
    val used = out Bits(8 bits)
    input.ready := Bool(ready)
    used := input.payload
  }

  class Top(wiring: String, guarded: Boolean = false) extends Component {
    val phase = RegInit(False)
    phase := !phase
    val beat = Stream(Bits(8 bits))
    beat.valid := (if (wiring == "payload") True else phase)
    beat.payload := phase.asBits.resize(8)
    val sink = new Sink(wiring != "payload")
    if (guarded) {
      sink.input.valid := False
      when(beat.valid) { sink.input.valid := True }
    } else sink.input.valid := beat.valid
    wiring match {
      case "ready" => beat.ready := False
      case "conditional-ready" =>
        beat.ready := False
        when(phase) { beat.ready := sink.input.ready }
      case _ => beat.ready := sink.input.ready
    }
    wiring match {
      case "payload" => sink.input.payload := 0
      case "partial-payload" =>
        sink.input.payload(3 downto 0) := beat.payload(3 downto 0)
        sink.input.payload(7 downto 4) := 0
      case _ => sink.input.payload := beat.payload
    }
    val y = out Bits(8 bits)
    y := sink.used
    beat.valid.simPublic()
    beat.ready.simPublic()
  }

  def base(path: String) = SpinalConfig(
    defaultConfigForClockDomains = ClockDomainConfig(resetKind = SYNC), targetDirectory = path)

  for (guarded <- Seq(false, true)) test(s"ready wiring fault fires with guarded valid=$guarded") {
    val dir = s"generated/ready-wiring/ready-$guarded"
    val (cfg, result) = SpinalChecks.install(base(dir), ChecksConfig(mode = Mode.Monitor))
    SimConfig.withConfig(cfg).workspacePath("simWorkspace").workspaceName(s"ready_$guarded")
      .withVerilator.compile(new Top("ready", guarded)).doSim(seed = 1) { dut =>
        dut.clockDomain.forkStimulus(10)
        dut.clockDomain.waitSampling(4)
        var previousStall = false
        var drops = 0
        for (_ <- 0 until 8) {
          dut.clockDomain.waitSampling()
          val valid = dut.beat.valid.toBoolean
          if (previousStall && !valid) drops += 1
          previousStall = valid && !dut.beat.ready.toBoolean
        }
        assert(drops > 0)
        assert(ChecksSim.firings(dut).map(_.check.id).toSet == Set("stream.valid_hold:beat"))
        assert(result.inserted.size == 4)
      }
    // Keep small RTL fixtures for the same depth-8 BMC as the review reproduction.
    val (formal, _) = SpinalChecks.install(base(s"$dir/formal").includeFormal, ChecksConfig())
    formal.generateVerilog(new Top("ready", guarded))
  }

  test("a payload wiring fault keeps the parent payload check") {
    val (cfg, _) = SpinalChecks.install(base("generated/ready-wiring/payload"), ChecksConfig(mode = Mode.Monitor))
    SimConfig.withConfig(cfg).workspacePath("simWorkspace").workspaceName("payload_wiring")
      .withVerilator.compile(new Top("payload")).doSim(seed = 1) { dut =>
        dut.clockDomain.forkStimulus(10)
        dut.clockDomain.waitSampling(12)
        assert(ChecksSim.firings(dut).map(_.check.id).toSet == Set("stream.payload_stable:beat"))
      }
  }

  for ((wiring, guarded, duplicate) <- Seq(
    ("connected", false, true), ("connected", true, false),
    ("partial-payload", false, false), ("conditional-ready", false, false))) {
    test(s"deduplication requires full direct wiring: $wiring guarded=$guarded") {
      val (cfg, result) = SpinalChecks.install(base(s"generated/ready-wiring/$wiring-$guarded"))
      cfg.generateVerilog(new Top(wiring, guarded))
      assert(result.records.exists(_.id == "stream.valid_hold:beat") != duplicate)
      assert(result.records.exists(_.id == "stream.payload_stable:beat") != duplicate)
      assert(result.records.count(_.id.startsWith("stream.")) == (if (duplicate) 2 else 4))
    }
  }

  for (selection <- Seq("disabled", "waived", "not-enabled")) test(s"a $selection child check does not cover the parent") {
    val settings = selection match {
      case "disabled" => ChecksConfig(disable = Seq("stream.payload_stable:sink.input"))
      case "waived" => ChecksConfig(waivers = Seq(Waiver("stream.valid_hold:sink.input", "test")))
      case _ => ChecksConfig(enable = Seq("stream.*:beat"))
    }
    val (cfg, result) = SpinalChecks.install(base(s"generated/ready-wiring/$selection"), settings)
    cfg.generateVerilog(new Top("connected"))
    assert(result.inserted.exists(_.id == "stream.valid_hold:beat"))
    assert(result.inserted.exists(_.id == "stream.payload_stable:beat"))
  }
}
