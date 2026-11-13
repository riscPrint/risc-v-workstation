package rvwsoc

import spinal.core._
import spinal.core.sim._
import spinal.lib._
import spinal.lib.bus.amba3.apb._
import spinal.lib.bus.amba4.axi._
import spinal.lib.bus.amba4.axilite._
import spinal.lib.bus.misc.SizeMapping
import spinal.lib.bus.tilelink

class LiteSmokeTop(crossing: Boolean = false) extends Component {
  val io = new Bundle { val bus = slave(AxiLite4(AxiLite4Config(32, 32))) }
  val slowClock = if(crossing) in(Bool()).setName("slow_clk") else null
  val ingress = BusIngress(io.bus)
  val memory = new WordMemory(12, 1024, false, Seq(), byteWrites = true)
  val legacy = new WordMemory(12, 1024, false, Seq())
  val port = Apb3(Apb3Config(12, 32, useStrb = true))
  BusIngress.legacy(port, legacy.io.bus)
  if(crossing) {
    // Separate clock domain at the same rate for this bounded smoke.
    val other = ClockDomain.current.copy(clock = slowClock)
    val area = new ClockingArea(other) {
      val ram = new WordMemory(12, 1024, false, Seq(), byteWrites = true)
    }
    // Keep the unused local memory idle.
    memory.io.bus.PADDR := 0; memory.io.bus.PSEL := 0
    memory.io.bus.PENABLE := False; memory.io.bus.PWRITE := False
    memory.io.bus.PWDATA := 0; memory.io.bus.PSTRB := 0
    val endpoint = Apb3(area.ram.io.bus.config)
    area.ram.io.bus << BusClockCrossing(endpoint, other)
    Fabric.connect(ingress, Seq((endpoint, SizeMapping(0x1000, 4096)), (port, SizeMapping(0x2000, 4096))))
  } else {
    Fabric.connect(ingress, Seq((memory.io.bus, SizeMapping(0x1000, 4096)), (port, SizeMapping(0x2000, 4096))))
  }
}

/** Elaboration fixtures for the library AXI and TileLink adapters. */
class AxiSmokeTop extends Component {
  val io = new Bundle { val bus = slave(Axi4(Axi4Config(32, 32, 2))) }
  val ram = new WordMemory(12, 1024, false, Seq(), byteWrites = true)
  Fabric.connect(BusIngress(io.bus), Seq((ram.io.bus, SizeMapping(0x1000, 4096))))
}
class TileLinkSmokeTop extends Component {
  val params = tilelink.M2sParameters(32, 32, List(tilelink.M2sAgent(null,
    tilelink.M2sSource(SizeMapping(0, 4), tilelink.M2sTransfers(
      get = tilelink.SizeRange.upTo(4), putFull = tilelink.SizeRange.upTo(4),
      putPartial = tilelink.SizeRange.upTo(4)))))).toNodeParameters()
  val io = new Bundle { val bus = slave(tilelink.Bus(params)) }
  val ram = new WordMemory(12, 1024, false, Seq(), byteWrites = true)
  Fabric.connect(BusIngress(io.bus), Seq((ram.io.bus, SizeMapping(0x1000, 4096))))
}
object BusElaborate extends App {
  SpinalConfig(targetDirectory = "rtl/axi-smoke").generateVerilog(new AxiSmokeTop)
  SpinalConfig(targetDirectory = "rtl/tl-smoke").generateVerilog(new TileLinkSmokeTop)
  SpinalConfig(targetDirectory = "rtl/cc-smoke").generateVerilog(new LiteSmokeTop(true))
}
object BusSmoke extends App {
  for(crossing <- Seq(false, true)) SimConfig.withVerilator.addSimulatorFlag("--assert").compile(new LiteSmokeTop(crossing)).doSim(31) { dut =>
    SimTimeout(100000)
    val b = dut.io.bus
    b.aw.valid #= false; b.w.valid #= false; b.ar.valid #= false
    b.b.ready #= false; b.r.ready #= false
    b.aw.addr #= 0; b.aw.prot #= 0; b.ar.addr #= 0; b.ar.prot #= 0
    b.w.data #= 0; b.w.strb #= 0
    if(crossing) fork {
      dut.slowClock #= false
      while(true) { sleep(7); dut.slowClock #= !dut.slowClock.toBoolean }
    }
    dut.clockDomain.forkStimulus(10)
    dut.clockDomain.waitSampling(5)
    def write(addr: Long, data: Long, mask: Int, expected: Int = 0): Unit = {
      // Send W before AW to exercise independent channel buffering.
      b.w.data #= data; b.w.strb #= mask; b.w.valid #= true
      dut.clockDomain.waitSamplingWhere(b.w.ready.toBoolean)
      b.w.valid #= false
      dut.clockDomain.waitSampling(2)
      b.aw.addr #= addr; b.aw.valid #= true
      dut.clockDomain.waitSamplingWhere(b.aw.ready.toBoolean)
      b.aw.valid #= false
      dut.clockDomain.waitSamplingWhere(b.b.valid.toBoolean)
      for (_ <- 0 until 3) {
        assert(b.b.valid.toBoolean && b.b.resp.toInt == expected)
        dut.clockDomain.waitSampling()
      }
      b.b.ready #= true; dut.clockDomain.waitSampling(); b.b.ready #= false
      dut.clockDomain.waitSampling()
    }
    def read(addr: Long, expected: Long, error: Int = 0): Unit = {
      b.ar.addr #= addr; b.ar.valid #= true
      dut.clockDomain.waitSamplingWhere(b.ar.ready.toBoolean)
      b.ar.valid #= false
      dut.clockDomain.waitSamplingWhere(b.r.valid.toBoolean)
      for (_ <- 0 until 3) {
        assert(b.r.valid.toBoolean && b.r.resp.toInt == error)
        if(error == 0) assert(b.r.data.toLong == expected)
        dut.clockDomain.waitSampling()
      }
      b.r.ready #= true; dut.clockDomain.waitSampling(); b.r.ready #= false
      dut.clockDomain.waitSampling()
    }
    write(0x1000, 0x11223344L, 15)
    write(0x1001, 0x0000aa00L, 2)
    read(0x1000, 0x1122aa44L)
    write(0x1002, 0xbbcc0000L, 12)
    read(0x1002, 0xbbccaa44L)
    write(0x1000, 0, 0)
    read(0x1000, 0xbbccaa44L)
    write(0x2000, 0x12345678, 15)
    write(0x2001, 0, 2, 2)
    read(0x2000, 0x12345678)
    write(0x3000, 0, 15, 2)
    read(0x3000, 0, 2)
    println(s"BUS_SMOKE_PASS crossing=$crossing seed=31 byte_halfword_zero_strobe legacy_guard decode_error response_backpressure")
  }
}
