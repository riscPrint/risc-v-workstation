package spinalwaves.examples

import spinal.core._
import spinal.lib._
import spinal.lib.fsm._

/** Subtraction GCD, matching the register-level example used by Tywaves. */
class Gcd(val width: Int = 16) extends Component {
  val io = new Bundle {
    val a = in UInt(width bits)
    val b = in UInt(width bits)
    val load = in Bool()
    val result = out UInt(width bits)
    val valid = out Bool()
  }
  val x = Reg(UInt(width bits)) init 0
  val y = Reg(UInt(width bits)) init 0
  when(io.load) {
    x := io.a
    y := io.b
  } otherwise {
    when(x === 0 && y =/= 0) { x := y; y := 0 }
      .elsewhen(x > y) { x := x - y }
      .elsewhen(y =/= 0) { y := y - x }
  }
  io.result := x
  io.valid := y === 0
}

case class Sample() extends Bundle {
  val signed = SInt(9 bits)
  val flags = Bits(3 bits)
  val valid = Bool()
}

case class Samples() extends Bundle {
  val lanes = Vec(Sample(), 2)
  val matrix = Vec(Vec(UInt(7 bits), 2), 2)
}

/** Nested products, nested vectors, vectors of products and fixed-point wrappers. */
class Structured extends Component {
  val io = new Bundle {
    val input = in(Samples())
    val output = out(Samples())
    val signedFixed = out(SFix(4 exp, 12 bits))
    val unsignedFixed = out(UFix(4 exp, 12 bits))
  }
  io.output := io.input
  io.signedFixed.raw := io.input.lanes(0).signed.resize(12)
  io.unsignedFixed.raw := io.input.matrix(0)(0).resize(12)
}

object TrafficState extends SpinalEnum(native) {
  val Idle, Busy, Done = newElement()
  val custom = SpinalEnumEncoding("trafficCustom")(Idle -> BigInt(5), Busy -> BigInt(1), Done -> BigInt(6))
}

/** One enum definition has explicit, inferred and custom-encoded representations. */
class Encodings extends Component {
  val states = TrafficState
  import states._
  val io = new Bundle {
    val advance = in Bool()
    val oneHot = out(states(binaryOneHot))
    val inferredState = out(states(inferred))
    val customState = out(states(custom))
  }
  val state = Reg(states(binaryOneHot)) init Idle
  val customState = Reg(states(custom)) init Idle
  when(io.advance) {
    switch(state) {
      is(Idle) { state := Busy }
      is(Busy) { state := Done }
      is(Done) { state := Idle }
    }
    switch(customState) {
      is(Idle) { customState := Busy }
      is(Busy) { customState := Done }
      is(Done) { customState := Idle }
    }
  }
  io.oneHot := state
  io.inferredState := state
  io.customState := customState
}

class Incrementer(val width: Int = 8) extends Component {
  val io = new Bundle {
    val input = in UInt(width bits)
    val output = out UInt(width bits)
  }
  io.output := io.input + 1
}

class Hierarchy extends Component {
  val io = new Bundle {
    val input = in UInt(8 bits)
    val first = out UInt(8 bits)
    val second = out UInt(8 bits)
    val count = out UInt(8 bits)
  }
  val left = new Incrementer()
  val right = new Incrementer()
  left.io.input := io.input
  right.io.input := left.io.output
  val work = new Area {
    val count = Reg(UInt(8 bits)) init 0
    val inner = new Area {
      val wrapped = count + 1
    }
    count := inner.wrapped
  }
  io.first := left.io.output
  io.second := right.io.output
  io.count := work.count
}

/** A Stream's ready direction differs from its valid and payload directions. */
class Protocols extends Component {
  val io = new Bundle {
    val input = slave(Stream(Sample()))
    val output = master(Stream(Sample()))
    val monitor = master(Flow(Sample()))
  }
  io.output << io.input
  io.monitor.valid := io.input.fire
  io.monitor.payload := io.input.payload
}

/** Exercises the inferred enum generated internally by spinal.lib.fsm. */
class LibraryFsm extends Component {
  val io = new Bundle {
    val advance = in Bool()
    val busy = out Bool()
  }
  io.busy := False
  val controller = new StateMachine {
    val idle = new State with EntryPoint
    val active = new State
    idle.whenIsActive { when(io.advance) { goto(active) } }
    active.whenIsActive {
      io.busy := True
      when(io.advance) { goto(idle) }
    }
  }
}
