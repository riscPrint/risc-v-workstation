package rvwsoc

import spinal.core._
import spinal.core.sim._
import spinal.lib._
import spinal.lib.bus.amba3.apb._

class LegacyErrorlessFixture extends Component {
  val io = new Bundle {
    val bus = slave(Apb3(Apb3Config(8,32,useStrb=true)))
    val writes = out UInt(8 bits)
  }
  val target = Apb3(Apb3Config(8,32,useSlaveError=false))
  val writes = Reg(UInt(8 bits)) init(0)
  target.PRDATA := writes.asBits.resized
  target.PREADY := True
  when(target.PSEL.lsb && target.PENABLE && target.PWRITE) { writes := writes + 1 }
  io.writes := writes
  BusIngress.legacy(io.bus,target)
  ApbChecks(io.bus);ApbChecks(target)
}

object LegacyErrorSmoke extends App {
  SimConfig.withVerilator.addSimulatorFlag("--assert").compile(new LegacyErrorlessFixture).doSim(31) { dut =>
    dut.io.bus.PSEL #= 0;dut.io.bus.PENABLE #= false;dut.io.bus.PWRITE #= false
    dut.io.bus.PADDR #= 0;dut.io.bus.PWDATA #= 7;dut.io.bus.PSTRB #= 15
    dut.clockDomain.forkStimulus(10)
    dut.clockDomain.waitSampling(10)
    def access(write: Boolean, mask: Int, error: Boolean): Unit = {
      dut.clockDomain.waitFallingEdge()
      dut.io.bus.PSEL #= 1;dut.io.bus.PENABLE #= false
      dut.io.bus.PWRITE #= write;dut.io.bus.PSTRB #= mask
      dut.clockDomain.waitSampling()
      dut.clockDomain.waitFallingEdge();dut.io.bus.PENABLE #= true
      sleep(1)
      assert(dut.io.bus.PREADY.toBoolean)
      assert(dut.io.bus.PSLVERROR.toBoolean == error)
      dut.clockDomain.waitSampling()
      dut.clockDomain.waitFallingEdge();dut.io.bus.PSEL #= 0;dut.io.bus.PENABLE #= false
    }
    access(true,1,true)
    assert(dut.io.writes.toInt==0)
    access(true,15,false)
    assert(dut.io.writes.toInt==1)
    access(false,0,false)
    assert(dut.io.bus.PRDATA.toBigInt==1)
    println("LEGACY_ERROR_SMOKE_PASS partial rejection and errorless target")
  }
}
