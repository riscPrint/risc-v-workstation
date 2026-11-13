package watchdogexample

import spinal.core._
import spinal.core.sim._

/** Directed accesses through composer-generated simple ingress and APB fabric. */
object Smoke extends App {
  SimConfig.withVerilator.addSimulatorFlag("--assert").withConfig(SpinalConfig(defaultClockDomainFrequency = FixedFrequency(50000000 Hz)))
    .compile {
      val top = new watchdoggenerated.ComposedSoc
      top.core.io.interrupts.simPublic()
      top
    }.doSim(43) { dut =>
      val c = dut.core_stimulus
      c.valid #= false; c.write #= false; c.address #= 0; c.wdata #= 0; c.mask #= 15
      dut.clockDomain.forkStimulus(10)
      dut.clockDomain.waitSampling(5)
      def access(offset: Int, write: Boolean = false, data: Long = 0): BigInt = {
        dut.clockDomain.waitFallingEdge()
        c.address #= 0x10000000L + offset; c.write #= write; c.wdata #= data; c.valid #= true
        var cycles = 0
        while (!c.ready.toBoolean && cycles < 30) { dut.clockDomain.waitSampling(); sleep(1); cycles += 1 }
        assert(cycles < 30 && !c.error.toBoolean)
        val result = c.rdata.toBigInt
        dut.clockDomain.waitSampling()
        dut.clockDomain.waitFallingEdge(); c.valid #= false
        dut.clockDomain.waitSampling(2)
        result
      }
      def write(offset: Int, value: Long): Unit = { access(offset,true,value); () }
      assert(access(0) == 0 && access(16) == 0)
      assert(!dut.wdt_resetRequest.toBoolean)
      write(4,100); write(12,0x51f15eL); write(0,3)
      val first = access(8)
      assert(first > 0 && first < 100)
      write(12,0) // Wrong key must not reload.
      assert(access(8) < first)
      write(12,0x51f15eL)
      assert(access(8) > first - 20)
      dut.clockDomain.waitSampling(110)
      assert(access(8) == 0 && access(16) == 1)
      assert(dut.wdt_resetRequest.toBoolean)
      assert((dut.core.io.interrupts.toBigInt & (BigInt(1) << 11)) != 0)
      write(0,0); write(16,1)
      assert(access(16) == 0 && !dut.wdt_resetRequest.toBoolean)
      write(4,0); write(12,0x51f15eL); write(0,3)
      dut.clockDomain.waitSampling(3)
      assert(access(16) == 1) // Zero reload expires without wrapping.
      write(0,0); write(12,0x51f15eL)
      assert(access(16) == 0)
      println("WATCHDOG_COMPOSED_PASS seed=43")
    }
}
