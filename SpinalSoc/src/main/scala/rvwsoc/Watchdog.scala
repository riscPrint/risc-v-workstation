package rvwsoc

import spinal.core._
import spinal.lib._
import spinal.lib.bus.amba3.apb._

/** Saturating watchdog with a keyed service write and sticky expiry status.
  * resetRequest is an output request. A project owns the actual reset tree.
  */
class Watchdog extends Component {
  val io = new Bundle {
    val bus = slave(Apb3(Apb3Config(8, 32)))
    val irq = out Bool()
    val resetRequest = out Bool()
  }
  val bus = Apb3SlaveFactory(io.bus)
  val control = Reg(Bits(32 bits)) init(0)
  val reload = Reg(UInt(32 bits)) init(U(0xffffffffL, 32 bits))
  val count = Reg(UInt(32 bits)) init(0)
  val expired = Reg(Bool()) init(False)
  bus.readAndWrite(control, 0)
  bus.readAndWrite(reload, 4)
  bus.read(count, 8)
  bus.read(expired, 16)
  // Expiry wins over a simultaneous W1C operation.
  bus.onWrite(16) { when(io.bus.PWDATA(0)) { expired := False } }
  when(control(0)) {
    when(count =/= 0) { count := count - 1 }
      .otherwise { expired := True }
  }
  // Service wins over expiry. Incorrect keys have no effect.
  bus.onWrite(12) {
    when(io.bus.PWDATA === B(0x51f15eL, 32 bits)) {
      count := reload
      expired := False
    }
  }
  io.irq := expired && control(0)
  io.resetRequest := expired && control(1)
}
