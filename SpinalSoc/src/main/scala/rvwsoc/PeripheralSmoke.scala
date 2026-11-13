package rvwsoc
import spinal.core._
import spinal.core.sim._
import spinal.lib.bus.amba3.apb._

/** Bounded RTL behavior checks, separate from any CPU acceptance claim. */
object PeripheralSmoke extends App {
  SimConfig.withVerilator.compile(new Clint).doSim(17) { dut =>
    dut.io.bus.PSEL #= 0; dut.io.bus.PENABLE #= false
    dut.io.bus.PADDR #= 0; dut.io.bus.PWRITE #= false; dut.io.bus.PWDATA #= 0
    dut.clockDomain.forkStimulus(10)
    dut.clockDomain.waitSampling(5)
    def write(addr: Int, data: Long): Unit = {
      dut.io.bus.PADDR #= addr; dut.io.bus.PWDATA #= data
      dut.io.bus.PWRITE #= true; dut.io.bus.PSEL #= 1
      dut.clockDomain.waitSampling()
      dut.io.bus.PENABLE #= true
      dut.clockDomain.waitSampling()
      dut.io.bus.PSEL #= 0; dut.io.bus.PENABLE #= false
      dut.clockDomain.waitSampling()
    }
    assert(!dut.io.irq.toBoolean)
    write(0,1); assert(dut.io.softwareIrq.toBoolean)
    write(0,0); assert(!dut.io.softwareIrq.toBoolean)
    write(0x4004,0); write(0x4000,0)
    assert(dut.io.irq.toBoolean)
    write(0x4004,0xffffffffL)
    assert(!dut.io.irq.toBoolean)
  }
  SimConfig.withVerilator.compile(new Plic).doSim(17) { dut =>
    dut.io.sources #= 0
    dut.io.bus.PSEL #= 0; dut.io.bus.PENABLE #= false
    dut.io.bus.PADDR #= 0; dut.io.bus.PWRITE #= false; dut.io.bus.PWDATA #= 0
    dut.clockDomain.forkStimulus(10)
    dut.clockDomain.waitSampling(5)
    def access(addr: Int, write: Boolean, data: Long=0): BigInt = {
      dut.io.bus.PADDR #= addr; dut.io.bus.PWDATA #= data
      dut.io.bus.PWRITE #= write; dut.io.bus.PSEL #= 1
      dut.clockDomain.waitSampling()
      dut.io.bus.PENABLE #= true
      sleep(1)
      val value = dut.io.bus.PRDATA.toBigInt
      dut.clockDomain.waitSampling()
      dut.io.bus.PSEL #= 0; dut.io.bus.PENABLE #= false
      dut.clockDomain.waitSampling()
      value
    }
    access(4,true,1); access(0x2000,true,2)
    dut.io.sources #= 1
    dut.clockDomain.waitSampling(3)
    assert(dut.io.irq.toBoolean)
    assert(access(0x200004,false)==1)
    assert(!dut.io.irq.toBoolean)
    dut.clockDomain.waitSampling(3)
    assert(!dut.io.irq.toBoolean)
    access(0x200004,true,1)
    dut.clockDomain.waitSampling(3)
    assert(dut.io.irq.toBoolean)
    dut.io.sources #= 0
    access(0x200004,false)
    access(0x200004,true,1)
    dut.clockDomain.waitSampling(3)
    assert(!dut.io.irq.toBoolean)
  }
  println("PERIPHERAL_SMOKE_PASS seed=17 clint=4 plic=6")
}
