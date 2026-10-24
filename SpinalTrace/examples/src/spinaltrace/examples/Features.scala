package spinaltrace.examples

import spinal.core._

// when / elsewhen / otherwise chain driving a combinational wire.
class WhenChain extends Component {
  val io = new Bundle {
    val sel        = in UInt (2 bits)
    val a, b, c, d = in UInt (8 bits)
    val result     = out UInt (8 bits)
  }

  val picked = UInt(8 bits)
  when(io.sel === 0) {
    picked := io.a
  } elsewhen (io.sel === 1) {
    picked := io.b
  } elsewhen (io.sel === 2) {
    picked := io.c
  } otherwise {
    picked := io.d
  }

  io.result := picked
}

object AluOp extends SpinalEnum {
  val ADD, SUB, AND, PASS = newElement()
}

// switch on a SpinalEnum with a default case; result is registered.
class SwitchEnum extends Component {
  val io = new Bundle {
    val op     = in (AluOp())
    val a, b   = in UInt (8 bits)
    val result = out UInt (8 bits)
  }

  val acc = Reg(UInt(8 bits)) init (0)
  switch(io.op) {
    is(AluOp.ADD) {
      acc := io.a + io.b
    }
    is(AluOp.SUB) {
      acc := io.a - io.b
    }
    default {
      acc := io.a
    }
  }

  io.result := acc
}

// Vec of registers with a dynamic write index and a dynamic read index.
class VecDynamic extends Component {
  val io = new Bundle {
    val wrEn   = in Bool ()
    val wrIdx  = in UInt (2 bits)
    val wrData = in UInt (8 bits)
    val rdIdx  = in UInt (2 bits)
    val rdData = out UInt (8 bits)
  }

  val regs = Vec.fill(4)(Reg(UInt(8 bits)) init (0))
  when(io.wrEn) {
    regs(io.wrIdx) := io.wrData
  }

  io.rdData := regs(io.rdIdx)
}

// Mux with a plain select and Mux with an expression select (named by the SpinalTrace phase).
class MuxExample extends Component {
  val io = new Bundle {
    val sel       = in Bool ()
    val a, b, c   = in UInt (8 bits)
    val picked    = out UInt (8 bits)
    val maxOfAB   = out UInt (8 bits)
  }

  io.picked  := Mux(io.sel, io.a, io.b)
  io.maxOfAB := Mux(io.a > io.b, io.a, io.b)
}

// Two-level hierarchy; the bug lives in the leaf and is observed at the toplevel output.
class HierLeaf extends Component {
  val io = new Bundle {
    val x = in UInt (8 bits)
    val y = out UInt (8 bits)
  }
  io.y := io.x + 3 // BUG: the specification says + 2
}

class HierMid extends Component {
  val io = new Bundle {
    val x = in UInt (8 bits)
    val y = out UInt (8 bits)
  }
  val leaf = new HierLeaf
  leaf.io.x := io.x
  val stage = Reg(UInt(8 bits)) init (0)
  stage := leaf.io.y
  io.y := stage
}

class HierTop extends Component {
  val io = new Bundle {
    val a      = in UInt (8 bits)
    val result = out UInt (8 bits)
  }
  val mid = new HierMid
  mid.io.x  := io.a
  io.result := mid.io.y |<< 1
}

// Register with an init value; the testbench pulses reset in the middle of the simulation.
class ResetCounter extends Component {
  val io = new Bundle {
    val enable = in Bool ()
    val count  = out UInt (8 bits)
  }
  val counter = Reg(UInt(8 bits)) init (5)
  when(io.enable) {
    counter := counter + 1
  }
  io.count := counter
}

// Memory with a synchronous read port and a conditional write port.
class SyncMem extends Component {
  val io = new Bundle {
    val wrEn   = in Bool ()
    val wrAddr = in UInt (3 bits)
    val wrData = in UInt (8 bits)
    val rdAddr = in UInt (3 bits)
    val rdData = out UInt (8 bits)
  }
  val mem = Mem(UInt(8 bits), 8)
  when(io.wrEn) {
    mem.write(io.wrAddr, io.wrData)
  }
  io.rdData := mem.readSync(io.rdAddr)
}

// A design with an `assert` that fails once the counter wraps past 10.
class AssertCounter extends Component {
  val io = new Bundle {
    val count = out UInt (4 bits)
  }
  val counter = Reg(UInt(4 bits)) init (0)
  counter := counter + 1
  assert(counter =/= 11, "counter reached 11", FAILURE)
  io.count := counter
}

// Two clock domains: SpinalTrace (like ChiselTrace) steps everything on one clock and warns.
class TwoClockDomains extends Component {
  val io = new Bundle {
    val clkB       = in Bool ()
    val a          = in UInt (8 bits)
    val outA, outB = out UInt (8 bits)
  }
  val regA = RegNext(io.a) init (0)
  val cdB  = ClockDomain(io.clkB, config = ClockDomainConfig(resetKind = BOOT))
  val areaB = new ClockingArea(cdB) {
    val regB = RegNext(io.a)
  }
  io.outA := regA
  io.outB := areaB.regB
}

// Partial assignments: fixed bits of a wire and dynamic bits of a register.
class BitFlags extends Component {
  val io = new Bundle {
    val set, clear = in Bool ()
    val idx        = in UInt (2 bits)
    val flags      = out Bits (4 bits)
    val status     = out Bits (2 bits)
  }
  val flags = Reg(Bits(4 bits)) init (0)
  when(io.set) {
    flags(io.idx) := True
  }
  when(io.clear) {
    flags := 0
  }
  io.flags := flags

  val status = Bits(2 bits)
  status(0) := io.set
  status(1) := io.clear
  io.status := status
}

// A BlackBox is opaque: its output depends on all of its inputs.
class AdderBox extends BlackBox {
  val io = new Bundle {
    val a, b = in UInt (8 bits)
    val sum  = out UInt (8 bits)
  }
  noIoPrefix()
  setInlineVerilog("module AdderBox(input [7:0] a, input [7:0] b, output [7:0] sum); assign sum = a + b; endmodule")
}

class WithBlackBox extends Component {
  val io = new Bundle {
    val x, y = in UInt (8 bits)
    val z    = out UInt (8 bits)
  }
  val adder = new AdderBox
  adder.io.a := io.x
  adder.io.b := io.y
  io.z := adder.io.sum
}
