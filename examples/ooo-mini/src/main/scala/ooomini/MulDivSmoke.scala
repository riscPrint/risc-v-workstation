package ooomini

import spinal.core._
import spinal.core.sim._

/** Directed overflow/zero cases and deterministic random arithmetic vectors. */
object MulDivSmoke extends App {
  val mask = (BigInt(1) << 32)-1
  def signed(x: BigInt): BigInt = if(x.testBit(31)) x-(BigInt(1)<<32) else x
  def expected(a: BigInt,b: BigInt,f: Int): BigInt = (f match {
    case 0 => a*b
    case 1 => (signed(a)*signed(b)) >> 32
    case 2 => (signed(a)*b) >> 32
    case 3 => (a*b) >> 32
    case 4 => if(b==0) mask else signed(a)/signed(b)
    case 5 => if(b==0) mask else a/b
    case 6 => if(b==0) a else signed(a)%signed(b)
    case 7 => if(b==0) a else a%b
  }) & mask
  val sim = SimConfig.withVerilator.workspacePath("rvw/out/unit").compile(new MulDiv)
  sim.doSim { dut =>
    dut.io.start #= false
    dut.io.flush #= false
    dut.io.a #= 0
    dut.io.b #= 0
    dut.io.funct #= 0
    dut.clockDomain.forkStimulus(10)
    dut.clockDomain.waitSampling(4)
    val random = new scala.util.Random(17)
    val corners = Seq(BigInt(0),BigInt(1),mask,BigInt(1)<<31,(BigInt(1)<<31)-1)
    val pairs = for(a <- corners;b <- corners) yield (a,b)
    val vectors = pairs ++ (0 until 32).map(_ => (BigInt(32,random),BigInt(32,random)))
    var count = 0
    for((a,b) <- vectors;f <- 0 until 8) {
      dut.clockDomain.waitFallingEdge()
      dut.io.a #= a
      dut.io.b #= b
      dut.io.funct #= f
      dut.io.start #= true
      dut.clockDomain.waitFallingEdge()
      dut.io.start #= false
      var cycles = 0
      while(!dut.io.done.toBoolean && cycles < 34) {
        dut.clockDomain.waitFallingEdge()
        cycles += 1
      }
      assert(dut.io.done.toBoolean,s"unit did not finish f=$f")
      assert(dut.io.result.toBigInt == expected(a,b,f),s"a=$a b=$b f=$f actual=${dut.io.result.toBigInt} expected=${expected(a,b,f)}")
      dut.clockDomain.waitFallingEdge()
      count += 1
    }
    println(s"MULDIV_VECTORS=$count")
  }
}
