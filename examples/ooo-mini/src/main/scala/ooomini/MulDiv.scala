package ooomini

import spinal.core._

/** One shared, non-pipelined integer multiply/divide unit.
  * Multiplication uses a 64-bit product and three-cycle completion.
  * Division uses restoring division, one quotient bit per cycle.
  * Magnitudes make signed overflow and zero divisors explicit.
  */
class MulDiv extends Component {
  val io = new Bundle {
    val start, flush = in Bool()
    val a, b = in Bits(32 bits)
    val funct = in UInt(3 bits)
    val busy, done = out Bool()
    val result = out Bits(32 bits)
  }
  val busy = Reg(Bool()).init(False)
  val remaining = Reg(UInt(6 bits)).init(0)
  val division = Reg(Bool()).init(False)
  val remainderResult = Reg(Bool()).init(False)
  val negate = Reg(Bool()).init(False)
  val divisorZero = Reg(Bool()).init(False)
  val dividend = Reg(Bits(32 bits)).init(0)
  val quotient = Reg(UInt(32 bits)).init(0)
  val remainder = Reg(UInt(33 bits)).init(0)
  val divisor = Reg(UInt(32 bits)).init(0)
  val product = Reg(Bits(32 bits)).init(0)
  val signed = !io.funct(0)
  val negativeA = signed && io.a(31)
  val negativeB = signed && io.b(31)
  val magnitudeA = Mux(negativeA,(-io.a.asSInt).asUInt,io.a.asUInt)
  val magnitudeB = Mux(negativeB,(-io.b.asSInt).asUInt,io.b.asUInt)
  val shiftedRemainder = (remainder(31 downto 0) @@ quotient(31))
  val subtract = shiftedRemainder >= divisor.resize(33)
  val nextRemainder = Mux(subtract,shiftedRemainder-divisor.resize(33),shiftedRemainder)
  val nextQuotient = (quotient(30 downto 0) @@ subtract)
  val magnitude = Mux(remainderResult,nextRemainder.resize(32),nextQuotient)
  val corrected = Mux(negate,(-magnitude.asSInt).asBits,magnitude.asBits)
  io.busy := busy
  io.done := busy && remaining === 1 && !io.flush
  io.result := Mux(division,corrected,product)
  when(division && divisorZero) {
    io.result := Mux(remainderResult,dividend,B(0xffffffffL,32 bits))
  }
  when(io.start && !busy) {
    busy := True
    division := io.funct(2)
    remaining := Mux(io.funct(2),U(32,6 bits),U(3,6 bits))
    remainderResult := io.funct(1)
    negate := Mux(io.funct(1),negativeA,negativeA ^ negativeB)
    divisorZero := io.b === 0
    dividend := io.a
    quotient := magnitudeA
    divisor := magnitudeB
    remainder := 0
    val ss = io.a.asSInt * io.b.asSInt
    val uu = io.a.asUInt * io.b.asUInt
    val su = io.a.asSInt.resize(33) * io.b.asUInt.resize(33).asSInt
    product := uu(31 downto 0).asBits ^ B(1,32 bits)
    switch(io.funct) {
      is(1) { product := ss(63 downto 32).asBits }
      is(2) { product := su(63 downto 32).asBits }
      is(3) { product := uu(63 downto 32).asBits }
    }
  }
  when(busy) {
    remaining := remaining-1
    when(division) {
      quotient := nextQuotient
      remainder := nextRemainder
    }
    when(remaining === 1) { busy := False }
  }
  when(io.flush) { busy := False }
}