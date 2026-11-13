package spinalchecks

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._
import spinalchecks.demo.CheckedGpio

class GpioDeviceSpec extends AnyFunSuite {
  test("actual Apb3Gpio direction accesses and independent observation fault") {
    val (cfg, _) = SpinalChecks.install(SpinalConfig(targetDirectory = "generated/GpioDevice"),
      ChecksConfig(enable = Seq("register.bus*"), mode = Mode.Monitor))
    val sim = SimConfig.withConfig(cfg).withVerilator.workspacePath("simWorkspace").workspaceName("GpioDevice").compile(new CheckedGpio)
    for (broken <- Seq(false, true)) sim.doSim(seed = 1) { dut =>
      dut.io.apb.PSEL #= 0; dut.io.apb.PENABLE #= false; dut.io.apb.PWRITE #= false
      dut.io.apb.PADDR #= 8; dut.io.apb.PWDATA #= 0
      dut.io.pins #= 0; dut.io.corruptObservation #= false
      dut.clockDomain.forkStimulus(10); dut.clockDomain.waitSampling(5)
      def access(write: Boolean, data: Int): BigInt = {
        dut.clockDomain.waitFallingEdge()
        dut.io.apb.PSEL #= 1; dut.io.apb.PENABLE #= false
        dut.io.apb.PWRITE #= write; dut.io.apb.PWDATA #= data
        dut.clockDomain.waitSampling(); dut.clockDomain.waitFallingEdge()
        dut.io.apb.PENABLE #= true
        sleep(1)
        assert(dut.io.apb.PREADY.toBoolean)
        val value = dut.io.apb.PRDATA.toBigInt
        dut.clockDomain.waitSampling(); dut.clockDomain.waitFallingEdge()
        dut.io.apb.PSEL #= 0; dut.io.apb.PENABLE #= false
        value
      }
      assert(access(false, 0) == 0)
      access(true, 0x5a); assert(access(false, 0) == 0x5a)
      access(true, 0x123); assert(access(false, 0) == 0x23)
      assert(dut.io.enables.toBigInt == 0x23)
      dut.io.corruptObservation #= broken
      access(false, 0)
      dut.clockDomain.waitSampling(2); dut.clockDomain.waitFallingEdge()
      val fired = ChecksSim.firings(dut).map(_.check.kind).toSet
      assert(fired == (if (broken) Set("register.bus_data") else Set.empty[String]), fired)
    }
  }
}
