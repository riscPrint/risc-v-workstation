package rvwvexii

import spinal.core._
import spinal.core.sim._
import vexiiriscv.execute.fpu.FpuSqrt

/** Isolated real mantissa unit with an explicit positive-normal IEEE adapter.
  * This harness does not contain the core's unpacker or packer plugins.
  * The sign bit is discarded. Zero, subnormal, infinity and NaN are outside scope.
  */
class FpuSqrtHarness(width: Int) extends Component {
  require(width == 32 || width == 64)
  val fraction = if(width == 32) 23 else 52
  val exponent = if(width == 32) 8 else 11
  val bias = (1 << (exponent - 1)) - 1
  val io = new Bundle {
    val a = in Bits(width bits)
    val rm = in UInt(3 bits)
    val start = in Bool()
    val y = out Bits(width bits)
    val flags = out Bits(5 bits)
    val done = out Bool()
  }
  val root = FpuSqrt(fraction)
  val exp = io.a(width-2 downto fraction).asUInt.resize(exponent+1).asSInt - S(bias, exponent+1 bits)
  root.io.input.a := Mux(exp.lsb, (B"1" ## io.a(fraction-1 downto 0) ## B"0"),
                                      (B"01" ## io.a(fraction-1 downto 0))).asUInt
  root.io.input.valid := io.start
  root.io.output.ready := False
  root.io.flush := False
  val truncated = root.io.output.result(fraction downto 1)
  val guard = root.io.output.result(0)
  val sticky = root.io.output.remain =/= 0
  val inexact = guard || sticky
  val increment = Bool()
  increment := False
  switch(io.rm) {
    is(0) { increment := guard && (sticky || truncated.lsb) }
    is(3) { increment := inexact }
    is(4) { increment := guard }
  }
  val rounded = truncated +^ increment.asUInt
  val resultExponent = ((exp >> 1) + S(bias, exponent+1 bits) + rounded.msb.asUInt.resize(exponent+1).asSInt).asUInt
  io.y := False ## resultExponent.resize(exponent).asBits ## rounded.resize(fraction).asBits
  io.flags := B(0, 4 bits) ## inexact
  io.done := root.io.output.valid
}

object FpuSqrtHarnessMain extends App {
  require(args.length == 2, "width output-directory")
  SpinalConfig(targetDirectory=args(1)).generateVerilog(new FpuSqrtHarness(args(0).toInt))
}
