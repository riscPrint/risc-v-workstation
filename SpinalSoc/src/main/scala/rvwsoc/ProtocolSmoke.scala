package rvwsoc

import spinal.core._
import spinal.core.sim._
import spinal.lib._

class ProtocolFixture extends Component {
  val io = new Bundle { val bus = slave(SimpleCpuBus()) }
  io.bus.ready := False
  io.bus.rdata := 0
  io.bus.error := False
  ProtocolChecks(io.bus)
}

object ProtocolSmoke extends App {
  val corrupt = args.headOption.contains("corrupt")
  SimConfig.withVerilator.addSimulatorFlag("--assert").compile(new ProtocolFixture).doSim(37) { dut =>
    dut.io.bus.valid #= false
    dut.io.bus.address #= 0
    dut.io.bus.write #= false
    dut.io.bus.wdata #= 0
    dut.io.bus.mask #= 0
    dut.clockDomain.forkStimulus(10)
    dut.clockDomain.waitSampling(10)
    dut.io.bus.valid #= true
    dut.clockDomain.waitSampling(3)
    if(corrupt) dut.io.bus.address #= 4
    dut.clockDomain.waitSampling(3)
    println("PROTOCOL_SMOKE_PASS stable held request")
  }
}

class TransactionFixture extends Component {
  import spinal.lib.bus.amba4.axi._
  val config = Axi4Config(32, 32, idWidth = 1,
    readIssuingCapability = 2, writeIssuingCapability = 2, combinedIssuingCapability = 4)
  val io = new Bundle {
    val bus = slave(Axi4(config))
    val unsolicitedResponse = in Bool()
  }
  io.bus.aw.ready := True
  io.bus.w.ready := True
  io.bus.ar.ready := True
  io.bus.r.setIdle()
  io.bus.b.valid := io.unsolicitedResponse
  io.bus.b.payload.assignFromBits(B(0, io.bus.b.payload.getBitsWidth bits))
  ProtocolChecks(io.bus)
}

object TransactionSmoke extends App {
  SimConfig.withVerilator.addSimulatorFlag("--assert").compile(new TransactionFixture).doSim(41) { dut =>
    dut.io.unsolicitedResponse #= false
    dut.io.bus.aw.valid #= false
    dut.io.bus.w.valid #= false
    dut.io.bus.ar.valid #= false
    dut.io.bus.b.ready #= true
    dut.io.bus.r.ready #= true
    dut.clockDomain.forkStimulus(10)
    dut.clockDomain.waitSampling(10)
    dut.io.unsolicitedResponse #= true
    dut.clockDomain.waitSampling(3)
    simFailure("unsolicited AXI write response was not detected")
  }
}
