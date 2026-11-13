package rvwsoc

import spinal.core._
import spinal.lib._

/** Test-only external master. Uses the same SimpleToApb ingress as a core.
  * This wrapper does not execute instructions. It permits independent VIP/RAL
  * access to the complete composed peripheral fabric.
  */
class VerificationCore extends Component with SimpleCoreWrapper {
  val io = new Bundle {
    val stimulus = slave(SimpleCpuBus())
    val bus = master(SimpleCpuBus())
    val interrupts = in Bits(32 bits)
    val debugReset = in Bool()
  }
  def bus = io.bus
  def interrupts = io.interrupts
  def debugReset = io.debugReset
  io.bus <> io.stimulus
}
