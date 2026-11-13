package ooomini

import spinal.core._
import spinal.core.sim._

/** Direct boundary, priority and lock-permission checks for the PMP matcher. */
object PmpSmoke extends App {
  class Matcher extends Component {
    val io = new Bundle {
      val config = in Vec(Bits(8 bits),4)
      val bounds = in Vec(UInt(32 bits),4)
      val address = in UInt(32 bits)
      val bytes = in UInt(3 bits)
      val machine = in Bool()
      val read, write, execute = out Bool()
    }
    io.read := Pmp.allowed(io.config,io.bounds,io.address,io.bytes,io.machine,0)
    io.write := Pmp.allowed(io.config,io.bounds,io.address,io.bytes,io.machine,1)
    io.execute := Pmp.allowed(io.config,io.bounds,io.address,io.bytes,io.machine,2)
  }
  val sim = SimConfig.withVerilator.workspacePath("rvw/out/pmp-unit").compile(new Matcher)
  sim.doSim { dut =>
    for(i <- 0 until 4) { dut.io.config(i) #= 0; dut.io.bounds(i) #= 0 }
    def check(address: Long, bytes: Int, machine: Boolean, read: Boolean, write: Boolean, execute: Boolean): Unit = {
      dut.io.address #= address; dut.io.bytes #= bytes; dut.io.machine #= machine
      sleep(1)
      assert(dut.io.read.toBoolean == read,s"read at $address")
      assert(dut.io.write.toBoolean == write,s"write at $address")
      assert(dut.io.execute.toBoolean == execute,s"execute at $address")
    }
    check(0x80000000L,4,false,false,false,false)
    check(0x80000000L,4,true,true,true,true)
    dut.io.bounds(0) #= 0x20000400L; dut.io.config(0) #= 0x0d // TOR R/X
    check(0x80000000L,4,false,true,false,true)
    check(0x80000ffcL,4,false,true,false,true)
    check(0x80000ffeL,4,false,false,false,false)
    check(0x80001000L,4,false,false,false,false)
    check(0x80000000L,4,true,true,true,true)
    dut.io.config(0) #= 0x8d // locked TOR checks M permissions too
    check(0x80000000L,4,true,true,false,true)
    dut.io.config(0) #= 0x11 // NA4 R
    dut.io.bounds(0) #= 0x20000000L
    dut.io.config(1) #= 0x1f // NAPOT RWX, lower priority
    dut.io.bounds(1) #= 0x200001ffL
    check(0x80000000L,4,false,true,false,false)
    check(0x80000002L,4,false,false,false,false)
    check(0x80000004L,4,false,true,true,true)
    check(0x80000fffL,1,false,true,true,true)
    check(0x80001000L,1,false,false,false,false)
    for(i <- 0 until 4) dut.io.config(i) #= 0
    for(i <- 0 until 4) {
      dut.io.config(i) #= 0x99 // locked NAPOT R, eight bytes
      dut.io.bounds(i) #= (0x20000000L+i*4)
      check(0x80000000L+i*16,4,false,true,false,false)
      check(0x80000004L+i*16,4,true,true,false,false)
      check(0x80000006L+i*16,4,false,false,false,false)
    }
    for(i <- 0 until 4) dut.io.config(i) #= 0
    dut.io.bounds(0) #= 0x20000000L
    dut.io.bounds(1) #= 0x20000000L
    dut.io.config(1) #= 0x88 // Empty locked TOR must not match a crossing access.
    check(0x7fffffffL,4,true,true,true,true)
    println("PMP_MATCHER_CASES=26")
  }
}
