package spinalchecks

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._

class DeviceBusChecksSpec extends AnyFunSuite {
  val localRegisters = Seq(DeviceRegister(16, RegisterModel(1, 4, 9, 3, 4, 8)),
                      DeviceRegister(32, RegisterModel(1, 4, 2, 15, 0, 0)))
  class Ref(registers: Seq[DeviceRegister]) extends Component {
    val width = registers.head.model.width
    val accepted, write, response, error = in Bool()
    val address = in UInt(8 bits)
    val data, strobes, responseData = in Bits(width bits)
    DeviceBusChecks.bind("bus", registers, accepted, address, write, data, strobes, response, responseData, error, 3)
  }
  for ((name, registers) <- Seq(
    "local" -> localRegisters,
    "ipxact" -> DeviceRegister.load(new java.io.File("src/test/maps/status.properties")),
    "systemrdl" -> DeviceRegister.load(new java.io.File("src/test/maps/status-rdl.properties")))) {
  test(s"register.bus $name independent observations: legal traffic and injected faults") {
    val (cfg, _) = SpinalChecks.install(SpinalConfig(targetDirectory = s"generated/DeviceBus_$name"), ChecksConfig(mode = Mode.Monitor))
    val sim = SimConfig.withConfig(cfg).withVerilator.workspacePath("simWorkspace").workspaceName(s"DeviceBus_$name").compile(new Ref(registers))
    for (fault <- Seq("none", "register.bus_data", "register.bus_decode", "register.bus_latency", "register.bus_order", "register.bus_overlap")) sim.doSim(seed = 1) { d =>
      d.accepted #= false; d.write #= false; d.response #= false; d.error #= false
      d.address #= 16; d.data #= 0; d.strobes #= 15; d.responseData #= 0
      d.clockDomain.forkStimulus(10); d.clockDomain.waitSampling(5); d.clockDomain.waitFallingEdge()
      def tick(): Unit = { d.clockDomain.waitSampling(); d.clockDomain.waitFallingEdge() }
      var state = registers.map(r => r.address -> r.model.reset).toMap
      for (((addr, wr, value, mask), i) <- DeviceBusChecks.accesses(registers).zipWithIndex) {
        val before = state(addr)
        d.address #= addr; d.write #= wr; d.data #= value; d.strobes #= mask; d.accepted #= true
        val delay = i % 4
        d.response #= (delay == 0); d.responseData #= before
        tick(); d.accepted #= false; d.response #= false
        if (delay != 0) {
          for (_ <- 1 until delay) tick()
          d.response #= true; tick(); d.response #= false
        }
        val m = registers.find(_.address == addr).get.model
        state += addr -> (if (wr) (((before & ~(m.writeMask & mask)) | (value & m.writeMask & mask)) & ~(value & mask & m.w1cMask)) else before & ~m.readClearMask)
        tick()
      }
      // A legal unmapped request must return an error.
      d.address #= 99; d.write #= false; d.accepted #= true; tick(); d.accepted #= false
      d.error #= true; d.response #= true; tick(); d.response #= false; d.error #= false; tick()
      fault match {
        case "register.bus_overlap" =>
          d.address #= registers.last.address; d.accepted #= true; tick()
          d.response #= true; d.responseData #= state(registers.last.address)
        case "register.bus_order" => d.response #= true
        case f if f.startsWith("register.bus_") =>
          d.address #= (if (f.endsWith("decode")) BigInt(99) else registers.last.address); d.accepted #= true; tick(); d.accepted #= false
          if (!f.endsWith("latency")) { d.response #= true; d.responseData #= 7 }
        case _ =>
      }
      // Response faults need a single response, not repeated unsolicited ones.
      tick(); d.response #= false; d.accepted #= false
      for (_ <- 0 until 4) tick()
      val fired = ChecksSim.firings(d).map(_.check.kind).toSet
      assert(fired == (if (fault == "none") Set.empty[String] else Set(if (fault.endsWith("overlap")) "register.bus_order" else fault)), fired)
    }
  }
  }
}
