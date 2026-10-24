package spinalchecks.demo

import spinal.core._
import spinal.lib._
import spinal.lib.fsm._

/** One planted bug per check kind, each switched on by name:
  *  - `hold`:   an internal stream drops `valid` while stalled
  *  - `stable`: the same stream changes its payload while stalled
  *  - `mem`:    a write pointer into a 5-word memory wraps at 6 instead of 5
  *  - `vec`:    an index into a 3-element Vec wraps at 4 instead of 3
  *  - `enum`:   an enum register is loaded with an undefined encoding
  *  - `hang`:   the heartbeat (progress signal) stops after 200 cycles
  *  - `xvalid`: the internal stream's valid is gated by a register without reset (X until io.sel is 3;
  *              invisible in 2-state simulation, found by `rvw formal xprop`)
  * With no bugs, no check fires for any input that respects the input stream's rules. */
object DemoEnum extends SpinalEnum(binarySequential) { val A, B, C = newElement() }

class ChecksDemo(bugs: Set[String] = Set.empty) extends Component {
  val io = new Bundle {
    val in = slave(Stream(UInt(8 bits)))
    val out = master(Stream(UInt(8 bits)))
    val sel = spinal.core.in UInt(2 bits)
    val vecOut = spinal.core.out UInt(8 bits)
    val memOut = spinal.core.out UInt(8 bits)
    val heartbeat = spinal.core.out Bool()
    val state = spinal.core.out Bits(2 bits)
    val aux = spinal.core.out Bits(10 bits)
  }

  // in -> stage (internal stream) -> fifo -> out
  val stage = Stream(UInt(8 bits))
  val tick = CounterFreeRun(8)
  val dropNow = if (bugs("hold")) tick.value === 5 else False
  val armed = if (bugs("xvalid")) { val r = Reg(Bool()); when(io.sel === 3) { r := True }; r } else True
  stage.valid := io.in.valid && !dropNow && armed
  stage.payload := (if (bugs("stable")) io.in.payload + tick.value.resize(8) else io.in.payload)
  io.in.ready := stage.ready
  val fifo = StreamFifo(UInt(8 bits), 4)
  fifo.io.push << stage
  io.out << fifo.io.pop

  // A 5-word memory written round-robin on every input transfer
  val mem = Mem(UInt(8 bits), 5)
  val wptr = Reg(UInt(3 bits)) init 0
  when(io.in.fire) {
    wptr := wptr + 1
    when(wptr === (if (bugs("mem")) 5 else 4)) { wptr := 0 }
  }
  mem.write(wptr, io.in.payload, enable = io.in.fire)
  io.memOut := mem.readSync(io.sel.resize(3) % 5)

  // A 3-element Vec read with a wrapping index
  val table = Vec(U(10, 8 bits), U(20, 8 bits), U(30, 8 bits))
  val vidx = Reg(UInt(2 bits)) init 0
  vidx := vidx + 1
  when(vidx === (if (bugs("vec")) 3 else 2)) { vidx := 0 }
  io.vecOut := table(vidx)

  // An enum register and a state machine
  val mode = Reg(DemoEnum()) init DemoEnum.A
  switch(mode) {
    is(DemoEnum.A) { when(io.sel === 1) { mode := DemoEnum.B } }
    is(DemoEnum.B) { when(io.sel === 2) { mode := DemoEnum.C } }
    is(DemoEnum.C) { mode := DemoEnum.A }
  }
  if (bugs("enum")) when(io.sel === 3 && tick.value === 7) { mode.assignFromBits(B"11") }

  val fsm = new StateMachine {
    val idle, busy, drain, done = new State
    setEntry(idle)
    idle.whenIsActive { when(io.in.fire) { goto(busy) } }
    busy.whenIsActive { goto(drain) }
    drain.whenIsActive { goto(done) }
    done.whenIsActive { goto(idle) }
  }
  io.state := fsm.isActive(fsm.busy) ## fsm.isActive(fsm.done)

  // Registers without a reset value, written legally later: their checks arm once they change, so the
  // random power-up value (X in hardware) does not fire them.
  val phase = Reg(DemoEnum())
  when(io.sel === 2) { phase := DemoEnum.C }
  val slot = Reg(UInt(2 bits))
  when(io.in.fire) { slot := (slot === 2) ? U(0, 2 bits) | (slot + 1) }
  val table2 = Vec(U(1, 8 bits), U(2, 8 bits), U(3, 8 bits))
  io.aux := phase.asBits ## table2(slot)

  // Heartbeat: high every 16 cycles (or stops after 200 cycles with the `hang` bug)
  val age = Reg(UInt(16 bits)) init 0
  age := age + 1
  io.heartbeat := age(3 downto 0) === 0 && (if (bugs("hang")) age < 200 else True)
}

/** A packet queue: a 6-entry ring buffer in a memory between two streams, and a count of packets
  * served. The planted bug withdraws `out.valid` while stalled, but only when exactly 2000 packets
  * have been served and the head packet is 0x5A: far too deep for a BMC from reset, and unlikely to
  * be hit by random stimulus. */
class DeepBugDemo(bug: Boolean = true) extends Component {
  val io = new Bundle {
    val in = slave(Stream(Bits(8 bits)))
    val out = master(Stream(Bits(8 bits)))
    val served = spinal.core.out UInt(16 bits)
  }
  val depth = 6
  val ram = Mem(Bits(8 bits), depth)
  val wr = Reg(UInt(3 bits)) init 0
  val rd = Reg(UInt(3 bits)) init 0
  val count = Reg(UInt(3 bits)) init 0
  val served = Reg(UInt(16 bits)) init 0
  io.served := served

  def bump(p: UInt): UInt = (p === depth - 1) ? U(0, 3 bits) | (p + 1)

  io.in.ready := count =/= depth
  ram.write(wr, io.in.payload, enable = io.in.fire)
  when(io.in.fire) { wr := bump(wr) }

  val head = ram.readAsync(rd)
  val stalledPrev = RegNext(io.out.valid && !io.out.ready) init False
  val glitch = if (bug) stalledPrev && served === 2000 && head === 0x5A else False
  io.out.valid := count =/= 0 && !glitch
  io.out.payload := head
  when(io.out.fire) { rd := bump(rd); served := served + 1 }

  count := count + U(io.in.fire).resized - U(io.out.fire).resized
}
