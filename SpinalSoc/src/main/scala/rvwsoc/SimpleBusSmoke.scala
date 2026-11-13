package rvwsoc
import spinal.core._
import spinal.core.sim._

/** Native unit checks: wait states, strobes, read data and error propagation. */
object SimpleBusSmoke extends App {
  SimConfig.withVerilator.compile(new SimpleToApb).doSim { dut =>
    val c = dut.io.cpu
    val b = dut.io.apb
    c.valid #= false; c.write #= false; c.address #= 0; c.wdata #= 0; c.mask #= 0
    b.PREADY #= false; b.PRDATA #= 0; b.PSLVERROR #= false
    dut.clockDomain.forkStimulus(10)
    dut.clockDomain.waitSampling(5)
    for(write <- Seq(true, false)) {
      dut.clockDomain.waitFallingEdge()
      c.valid #= true; c.write #= write; c.address #= 0x1004; c.wdata #= 0x12345678L; c.mask #= 5
      dut.clockDomain.waitSampling(3)
      sleep(1)
      for(_ <- 0 until 3) {
        assert(b.PSEL.toInt == 1 && b.PENABLE.toBoolean && !c.ready.toBoolean)
        assert(b.PADDR.toLong == 0x1004 && b.PWRITE.toBoolean == write)
        assert(b.PWDATA.toLong == 0x12345678L && b.PSTRB.toInt == 5)
        dut.clockDomain.waitSampling()
      }
      dut.clockDomain.waitFallingEdge()
      b.PREADY #= true; b.PRDATA #= 0x55667788L; b.PSLVERROR #= !write
      dut.clockDomain.waitSampling(); sleep(1)
      assert(c.ready.toBoolean && c.rdata.toLong == 0x55667788L && c.error.toBoolean == !write)
      dut.clockDomain.waitSampling()
      dut.clockDomain.waitFallingEdge()
      c.valid #= false; b.PREADY #= false
      dut.clockDomain.waitSampling(2)
    }
  }
}
