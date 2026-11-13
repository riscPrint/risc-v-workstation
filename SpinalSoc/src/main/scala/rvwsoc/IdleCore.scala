package rvwsoc
import spinal.core._
import spinal.lib._
import spinal.lib.bus.amba3.apb._

/** Elaboration fixture only. Does not execute instructions. */
class IdleCore extends Component with CoreWrapper {
  val io = new Bundle {
    val bus = master(Apb3(Apb3Config(32, 32)))
    val interrupts = in Bits(32 bits)
    val debugReset = in Bool()
  }
  def bus = io.bus
  def interrupts = io.interrupts
  def debugReset = io.debugReset
  io.bus.PADDR := 0
  io.bus.PSEL := 0
  io.bus.PENABLE := False
  io.bus.PWRITE := False
  io.bus.PWDATA := 0
}
