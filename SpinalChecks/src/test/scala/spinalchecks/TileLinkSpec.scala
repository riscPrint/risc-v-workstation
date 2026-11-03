package spinalchecks

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._
import spinal.lib._
import spinal.lib.bus.tilelink._

/** The TileLink burst rule (review 2026-10-21): a channel may change its message before the first beat
  * is accepted (rocket's TLArbiter does), but not inside a multi-beat burst. */
class TileLinkSpec extends AnyFunSuite {
  val p = BusParameter.simple(addressWidth = 32, dataWidth = 32, sizeBytes = 16, sourceWidth = 2) // up to 4 beats

  class TlTop extends Component {
    val bus = slave(Bus(p))
    val a = bus.a
    val go = in Bool()
    val sum = out Bits (32 bits)
    a.ready := go
    sum := a.payload.data ^ a.payload.address.asBits
    bus.d.valid := False
    bus.d.payload.assignDontCare()
    // the same message type outside a bus: a one-transfer notification, no bursts, no TileLink rule
    val note = slave(Stream(ChannelA(p)))
    note.ready := True
  }

  lazy val compiled = {
    val (cfg, _) = SpinalChecks.install(SpinalConfig(targetDirectory = "generated/tl"), ChecksConfig(mode = Mode.Monitor))
    SimConfig.withConfig(cfg).workspacePath("simWorkspace").workspaceName("tl").withVerilator.compile(new TlTop)
  }

  /** Each beat: (valid, opcode is PutFullData, size, source, address, data, ready). */
  def run(beats: Seq[(Boolean, Boolean, Int, Int, Long, Long, Boolean)]): Set[String] = {
    var fired = Set.empty[String]
    compiled.doSim(seed = 1) { dut =>
      dut.a.valid #= false
      dut.note.valid #= false
      dut.go #= false
      dut.clockDomain.forkStimulus(10)
      dut.clockDomain.waitSampling(4)
      for ((valid, put, size, source, address, data, ready) <- beats) {
        dut.clockDomain.waitFallingEdge()
        dut.a.valid #= valid
        dut.a.payload.opcode #= (if (put) Opcode.A.PUT_FULL_DATA else Opcode.A.GET)
        dut.a.payload.param #= 0
        dut.a.payload.size #= size
        dut.a.payload.source #= source
        dut.a.payload.address #= address
        dut.a.payload.mask #= 0xf
        dut.a.payload.data #= data
        dut.a.payload.corrupt #= false
        dut.go #= ready
      }
      dut.clockDomain.waitFallingEdge()
      dut.a.valid #= false
      dut.clockDomain.waitSampling(4)
      fired = ChecksSim.firings(dut).map(_.check.id).toSet
    }
    fired
  }

  test("only bus channels get the TileLink rule") {
    val ids = compiled.dut.getTag(classOf[ChecksTag]).get.result.records.map(_.id).toSet
    assert(ids.contains("tilelink.burst_stable:bus_a"), ids)
    assert(!ids.exists(_.startsWith("tilelink.burst_stable:note")), ids)
  }

  test("a single-beat request replaced before acceptance is legal TileLink") {
    // Get from source 1 stalled two cycles, then replaced by source 0 (another line) and accepted.
    val fired = run(Seq(
      (true, false, 2, 1, 0x80L, 0L, false), (true, false, 2, 1, 0x80L, 0L, false),
      (true, false, 2, 0, 0x40L, 0L, true), (true, false, 2, 1, 0x80L, 0L, true)))
    assert(!fired.contains("tilelink.burst_stable:bus_a"), fired)
    assert(fired.isEmpty, fired)
  }

  test("a clean burst with stalls fires nothing") {
    val fired = run(Seq(
      (true, true, 4, 2, 0x100L, 1L, true), (true, true, 4, 2, 0x100L, 2L, false), (true, true, 4, 2, 0x100L, 2L, true),
      (true, true, 4, 2, 0x100L, 3L, true), (false, true, 4, 2, 0x100L, 3L, true), (true, true, 4, 2, 0x100L, 4L, true)))
    assert(fired.isEmpty, fired)
  }

  test("a header change inside a burst fires tilelink.burst_stable") {
    val fired = run(Seq(
      (true, true, 4, 2, 0x100L, 1L, true), (true, true, 4, 2, 0x200L, 2L, true),
      (true, true, 4, 2, 0x200L, 3L, true), (true, true, 4, 2, 0x200L, 4L, true)))
    assert(fired == Set("tilelink.burst_stable:bus_a"), fired)
  }

  test("a stalled beat inside a burst must keep its data") {
    val fired = run(Seq(
      (true, true, 4, 2, 0x100L, 1L, true), (true, true, 4, 2, 0x100L, 2L, false), (true, true, 4, 2, 0x100L, 9L, true),
      (true, true, 4, 2, 0x100L, 3L, true), (true, true, 4, 2, 0x100L, 4L, true)))
    assert(fired == Set("tilelink.burst_stable:bus_a"), fired)
  }
}
