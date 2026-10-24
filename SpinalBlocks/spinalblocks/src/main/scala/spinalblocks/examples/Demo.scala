package spinalblocks.examples

import java.io.File

import spinal.core._
import spinal.lib._
import spinal.lib.fsm._

/** Subtraction GCD. */
class Gcd(width: Int = 16) extends Component {
  val io = new Bundle {
    val a, b   = in UInt (width bits)
    val load   = in Bool ()
    val result = out UInt (width bits)
    val valid  = out Bool ()
  }
  val x = Reg(UInt(width bits)) init 0
  val y = Reg(UInt(width bits)) init 0
  when(io.load) {
    x := io.a; y := io.b
  } elsewhen (x > y) {
    x := x - y
  } elsewhen (y =/= 0) {
    y := y - x
  }
  io.result := x
  io.valid := y === 0
}

object ResultPhase extends SpinalEnum {
  val Empty, Filling, Full, Spare = newElement()
}

/** A FIFO in front of two GCD units, with a controller FSM and a small result memory. */
class GcdCluster extends Component {
  val io = new Bundle {
    val cmd    = slave Stream (Vec(UInt(16 bits), 2))
    val rsp    = master Flow (UInt(16 bits))
    val rdAddr = in UInt (3 bits)
    val rdData = out UInt (16 bits)
  }

  val fifo  = StreamFifo(Vec(UInt(16 bits), 2), 4)
  fifo.io.push << io.cmd

  val units = Seq.fill(2)(new Gcd)

  val ctrl = new Area {
    val sel     = Reg(UInt(1 bits)) init 0
    val started = Reg(Bool()) init False
    val fsm = new StateMachine {
      val idle, run, done = new State
      setEntry(idle)
      fifo.io.pop.ready := False
      idle.whenIsActive {
        when(fifo.io.pop.valid) { goto(run) }
      }
      run.whenIsActive {
        when(units.map(_.io.valid).reduce(_ && _)) { goto(done) }
      }
      done.whenIsActive {
        fifo.io.pop.ready := True
        sel := sel + 1
        goto(idle) // ready for the next command
      }
    }
    val load = fsm.isEntering(fsm.run)
  }

  for ((u, i) <- units.zipWithIndex) {
    u.io.a := fifo.io.pop.payload(0) + i
    u.io.b := fifo.io.pop.payload(1)
    u.io.load := ctrl.load
  }

  val results = new Area {
    val mem   = Mem(UInt(16 bits), 8)
    val wrPtr = Reg(UInt(3 bits)) init 0
    val sum   = units.map(_.io.result).reduce(_ + _)
    val write = ctrl.fsm.isActive(ctrl.fsm.done)
    mem.write(wrPtr, sum, write)
    when(write) { wrPtr := wrPtr + 1 }

    // A plain enum state machine (no StateMachine library).
    val phase = Reg(ResultPhase()) init ResultPhase.Empty
    switch(phase) {
      is(ResultPhase.Empty) { when(write) { phase := ResultPhase.Filling } }
      is(ResultPhase.Filling) { when(write && wrPtr === 7) { phase := ResultPhase.Full } }
      is(ResultPhase.Full) { when(io.rdAddr === 7) { phase := ResultPhase.Empty } }
    }
  }

  io.rsp.valid := results.write
  io.rsp.payload := results.sum
  io.rdData := results.mem.readAsync(io.rdAddr)
}

object Demo {
  def main(args: Array[String]): Unit = {
    val out = new File(if (args.nonEmpty) args(0) else "demo.json")
    spinalblocks.SpinalBlocks.generate(SpinalConfig(targetDirectory = "target/demo-rtl"), out)(new GcdCluster)
  }
}
