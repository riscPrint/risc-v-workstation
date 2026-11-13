package blockexample

import spinal.core._
import spinal.core.sim._

/** Directed accesses through composer-generated simple ingress and APB fabric. */
object Smoke extends App {
  SimConfig.withVerilator.addSimulatorFlag("--assert").withConfig(SpinalConfig(defaultClockDomainFrequency = FixedFrequency(50000000 Hz)))
    .compile {
      val top = new blockgenerated.ComposedSoc
      top.core.io.interrupts.simPublic()
      top
    }.doSim(47) { dut =>
      val c = dut.core_stimulus
      c.valid #= false; c.write #= false; c.address #= 0; c.wdata #= 0; c.mask #= 15
      dut.clockDomain.forkStimulus(10)
      dut.clockDomain.waitSampling(5)
      def access(offset: Int, write: Boolean = false, data: Long = 0, expectError: Boolean = false): BigInt = {
        dut.clockDomain.waitFallingEdge()
        c.address #= 0x10000000L + offset; c.write #= write; c.wdata #= data; c.valid #= true
        var cycles = 0
        while (!c.ready.toBoolean && cycles < 30) { dut.clockDomain.waitSampling(); sleep(1); cycles += 1 }
        assert(cycles < 30 && c.error.toBoolean == expectError)
        val result = c.rdata.toBigInt
        dut.clockDomain.waitSampling()
        dut.clockDomain.waitFallingEdge(); c.valid #= false
        dut.clockDomain.waitSampling(2)
        result
      }
      def write(offset: Int, value: Long): Unit = { access(offset,true,value); () }
      assert(access(0) == 0 && access(12) == 8 && access(8) == 0)
      write(0,3); write(4,2)
      access(16,expectError=true)
      assert(access(20) == 0)
      access(0,true,4,expectError=true)
      assert(access(0) == 3)
      access(4,true,1,expectError=true)
      assert(access(8) == 3)
      write(8,2); assert(access(8) == 1)
      for(i <- 0 until 128) write(16,0x5a000000L + i)
      assert(access(8) == 4)
      assert((dut.core.io.interrupts.toBigInt & (BigInt(1) << 11)) != 0)
      write(8,4); assert(access(8) == 0)
      write(4,1)
      for(i <- 0 until 128) assert(access(16) == 0x5a000000L + i)
      assert(access(8) == 4)
      write(0,4); write(4,1)
      for(i <- 0 until 128) assert(access(16) == 0)
      write(0,3); write(4,1)
      assert(access(16) == 0x5a000000L)
      write(4,0); write(8,6)
      assert(access(8) == 0)
      access(16, expectError=true)
      write(0,8); access(4,true,1,expectError=true)
      assert(access(8) == 2)
      write(8,2); assert(access(8) == 0)
      println("BLOCK_COMPOSED_PASS seed=47 words=257")
    }
}
