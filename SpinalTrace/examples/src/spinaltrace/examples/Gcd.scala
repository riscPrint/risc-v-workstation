package spinaltrace.examples

import spinal.core._

// Port of the ChiselTrace README GCD (same registers, same when/otherwise structure).
class GCD extends Component {
  val io = new Bundle {
    val a             = in UInt (32 bits)
    val b             = in UInt (32 bits)
    val loadValues    = in Bool ()
    val result        = out UInt (32 bits)
    val resultIsValid = out Bool ()
  }

  val x = Reg(UInt(32 bits))
  val y = Reg(UInt(32 bits))

  val tmp = x + y
  when(x > y) {
    x := x - y
  } otherwise {
    y := y - x
  }

  when(io.loadValues) {
    x := io.a
    y := io.b
  }

  io.result        := x
  io.resultIsValid := y === 0
}

// Same circuit with an injected design bug: the subtraction of x is off by one.
class BuggyGCD extends Component {
  val io = new Bundle {
    val a             = in UInt (32 bits)
    val b             = in UInt (32 bits)
    val loadValues    = in Bool ()
    val result        = out UInt (32 bits)
    val resultIsValid = out Bool ()
  }

  val x = Reg(UInt(32 bits))
  val y = Reg(UInt(32 bits))

  when(x > y) {
    x := x - y - 1 // BUG: should be x - y
  } otherwise {
    y := y - x
  }

  when(io.loadValues) {
    x := io.a
    y := io.b
  }

  io.result        := x
  io.resultIsValid := y === 0
}
