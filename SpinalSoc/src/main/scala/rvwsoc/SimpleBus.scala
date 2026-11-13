package rvwsoc

import spinal.core._
import spinal.lib._
import spinal.lib.bus.amba3.apb._

/** One outstanding word transfer. The CPU holds valid and payload until ready.
  * ready means completion, not request acceptance. Byte masks are write strobes.
  */
case class SimpleCpuBus(addressWidth: Int = 32) extends Bundle with IMasterSlave {
  val valid, ready, write, error = Bool()
  val address = UInt(addressWidth bits)
  val wdata, rdata = Bits(32 bits)
  val mask = Bits(4 bits)
  override def asMaster(): Unit = {
    out(valid, write, address, wdata, mask)
    in(ready, error, rdata)
  }
}

trait SimpleCoreWrapper { this: Component =>
  def bus: SimpleCpuBus
  def interrupts: Bits
  def debugReset: Bool
}

class SimpleToApb(addressWidth: Int = 32) extends Component {
  val io = new Bundle {
    val cpu = slave(SimpleCpuBus(addressWidth))
    val apb = master(Apb3(Apb3Config(addressWidth, 32, useStrb = true)))
  }
  val state = Reg(UInt(2 bits)) init(0) // idle, setup, access, response
  val address = Reg(UInt(addressWidth bits))
  val write = Reg(Bool())
  val data, response = Reg(Bits(32 bits))
  val mask = Reg(Bits(4 bits))
  val error = Reg(Bool())
  io.apb.PSEL := B(0, 1 bits)
  when(state === 1 || state === 2) { io.apb.PSEL := 1 }
  io.apb.PENABLE := state === 2
  io.apb.PADDR := address
  io.apb.PWRITE := write
  io.apb.PWDATA := data
  io.apb.PSTRB := mask
  io.cpu.ready := state === 3
  io.cpu.rdata := response
  io.cpu.error := error
  when(state === 0 && io.cpu.valid) {
    address := io.cpu.address
    write := io.cpu.write
    data := io.cpu.wdata
    mask := io.cpu.mask
    state := 1
  }
  when(state === 1) { state := 2 }
  when(state === 2 && io.apb.PREADY) {
    response := io.apb.PRDATA
    error := io.apb.PSLVERROR
    state := 3
  }
  when(state === 3 && io.cpu.valid) { state := 0 }
}
