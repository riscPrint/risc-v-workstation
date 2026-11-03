package spinalchecks

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._
import spinal.lib._
import spinal.lib.bus.tilelink

/** A parent can consume a child master through fields, without a consumer Stream. */
class ChildMasterSpec extends AnyFunSuite {
  class Producer extends Component {
    val beat = master(Stream(Bits(8 bits)))
    val phase = RegInit(False)
    phase := !phase
    beat.valid := phase
    beat.payload := phase.asBits.resize(8)
  }

  class Sink extends Component {
    val beat = slave(Stream(Bits(8 bits)))
    beat.ready := False
    val seen = out Bits(8 bits)
    seen := beat.payload
  }

  class Top(wiring: String) extends Component {
    val producer = new Producer
    val seen = out Bits(8 bits)
    if (wiring == "bare") {
      producer.beat.ready := False
      seen := producer.beat.payload
    } else if (wiring == "sibling") {
      val sink = new Sink
      sink.beat << producer.beat
      seen := sink.seen
    } else {
      val beat = Stream(Bits(8 bits)).setName("beat")
      beat.valid := producer.beat.valid
      beat.payload := (if (wiring == "payload") B(0, 8 bits) else producer.beat.payload)
      if (wiring == "ready") producer.beat.ready := True
      else producer.beat.ready := beat.ready
      if (wiring == "chain") {
        val sink = new Sink
        sink.beat << beat
        seen := sink.seen
      } else {
        beat.ready := False
        seen := beat.payload
      }
    }
    producer.beat.valid.simPublic()
    producer.beat.ready.simPublic()
  }

  def base(dir: String) = SpinalConfig(targetDirectory = dir,
    defaultConfigForClockDomains = ClockDomainConfig(resetKind = SYNC))

  test("bare child master valid drops fire and emit a formal fixture") {
    val (cfg, result) = SpinalChecks.install(base("generated/child-master/bare"), ChecksConfig(mode = Mode.Monitor))
    SimConfig.withConfig(cfg).workspacePath("simWorkspace").workspaceName("child_master")
      .withVerilator.compile(new Top("bare")).doSim(seed = 1) { dut =>
        dut.clockDomain.forkStimulus(10)
        dut.clockDomain.waitSampling(4)
        dut.clockDomain.waitFallingEdge()
        var previousStall = dut.producer.beat.valid.toBoolean && !dut.producer.beat.ready.toBoolean
        var drops = 0
        for (_ <- 0 until 8) {
          dut.clockDomain.waitFallingEdge()
          val valid = dut.producer.beat.valid.toBoolean
          if (previousStall && !valid) drops += 1
          previousStall = valid && !dut.producer.beat.ready.toBoolean
        }
        assert(drops == 4)
        assert(result.inserted.map(_.id).toSet ==
          Set("stream.valid_hold:producer.beat", "stream.payload_stable:producer.beat"))
        assert(ChecksSim.firings(dut).map(_.check.id).toSet == Set("stream.valid_hold:producer.beat"))
      }
    val (formal, _) = SpinalChecks.install(base("generated/child-master/formal").includeFormal)
    formal.generateVerilog(new Top("bare"))
  }

  for (wiring <- Seq("wrapped", "sibling", "chain")) test(s"$wiring keeps exactly one enabled check set") {
    val (cfg, result) = SpinalChecks.install(base(s"generated/child-master/$wiring"))
    cfg.generateVerilog(new Top(wiring))
    assert(result.inserted.size == 2)
    assert(!result.records.exists(_.id == "stream.valid_hold:producer.beat"))
  }

  for (wiring <- Seq("ready", "payload")) test(s"$wiring mismatch keeps the child checks") {
    val (cfg, result) = SpinalChecks.install(base(s"generated/child-master/$wiring"))
    cfg.generateVerilog(new Top(wiring))
    assert(result.inserted.size == 4)
    assert(result.inserted.exists(_.id == "stream.valid_hold:producer.beat"))
    assert(result.inserted.exists(_.id == "stream.payload_stable:producer.beat"))
  }

  for (selection <- Seq("disabled", "waived", "not-enabled", "no-internal")) {
    test(s"a $selection parent check does not cover a child master") {
      val settings = selection match {
        case "disabled" => ChecksConfig(disable = Seq("stream.payload_stable:beat"))
        case "waived" => ChecksConfig(waivers = Seq(Waiver("stream.valid_hold:beat", "test")))
        case "no-internal" => ChecksConfig(internalStreams = false)
        case _ => ChecksConfig(enable = Seq("stream.*:producer.beat"))
      }
      val (cfg, result) = SpinalChecks.install(base(s"generated/child-master/$selection"), settings)
      cfg.generateVerilog(new Top("wrapped"))
      assert(result.inserted.exists(_.id == "stream.valid_hold:producer.beat"))
      assert(result.inserted.exists(_.id == "stream.payload_stable:producer.beat"))
    }
  }

  val p = tilelink.BusParameter.simple(addressWidth = 32, dataWidth = 32, sizeBytes = 16, sourceWidth = 2)
  class TlProducer extends Component {
    val bus = master(tilelink.Bus(p))
    val count = Reg(UInt(2 bits)).init(0)
    count := count + 1
    bus.a.valid := True
    bus.a.payload.assignFromBits(B(0, bus.a.payload.getBitsWidth bits))
    bus.a.opcode.allowOverride := tilelink.Opcode.A.PUT_FULL_DATA
    bus.a.size.allowOverride := 4
    bus.a.address.allowOverride := count.resize(32)
    bus.d.ready := True
  }
  class TlTop(wrapped: Boolean) extends Component {
    val producer = new TlProducer
    val seen = out UInt(32 bits)
    if (wrapped) {
      val bus = tilelink.Bus(p).setName("bus")
      bus << producer.bus
      bus.a.ready := True
      bus.d.valid := False
      bus.d.payload.assignDontCare()
      seen := bus.a.address
    } else {
      producer.bus.a.ready := True
      producer.bus.d.valid := False
      producer.bus.d.payload.assignDontCare()
      seen := producer.bus.a.address
    }
  }

  test("bare child TileLink channel checks its burst headers") {
    val (cfg, result) = SpinalChecks.install(base("generated/child-master/tilelink"), ChecksConfig(mode = Mode.Monitor))
    SimConfig.withConfig(cfg).workspacePath("simWorkspace").workspaceName("child_tilelink")
      .withVerilator.compile(new TlTop(false)).doSim(seed = 1) { dut =>
        dut.clockDomain.forkStimulus(10)
        dut.clockDomain.waitSampling(12)
        assert(result.inserted.exists(_.id == "tilelink.burst_stable:producer.bus_a"))
        assert(ChecksSim.firings(dut).map(_.check.id).toSet == Set("tilelink.burst_stable:producer.bus_a",
          "tilelink.request_legal:producer.bus_a", "tilelink.source_busy:producer.bus_a"))
      }
  }

  for (waived <- Seq(false, true)) test(s"TileLink child coverage requires an enabled parent burst check: waived=$waived") {
    val settings = if (waived) ChecksConfig(waivers = Seq(Waiver("tilelink.burst_stable:bus_a", "test")))
      else ChecksConfig()
    val (cfg, result) = SpinalChecks.install(base(s"generated/child-master/tl-wrapped-$waived"), settings)
    cfg.generateVerilog(new TlTop(true))
    assert(result.inserted.exists(_.id == "tilelink.burst_stable:producer.bus_a") == waived)
    assert(result.inserted.count(r => r.kind == Kind.TileLinkBurstStable && r.id.endsWith("bus_a")) == 1)
  }
}
