package rvwsoc

import spinal.core._
import spinal.lib._
import spinal.lib.bus.amba3.apb._

/** Single-hart CLINT: msip, mtimecmp and mtime, standard byte offsets.
  * io.irq is MTIP; io.softwareIrq is MSIP. mtime counts input clock edges.
  */
class Clint extends Component {
  val io = new Bundle {
    val bus = slave(Apb3(Apb3Config(16, 32)))
    val irq = out Bool()
    val softwareIrq = out Bool()
  }
  val bus = Apb3SlaveFactory(io.bus)
  val msip = Reg(Bits(32 bits)) init(0)
  val mtime = Reg(UInt(64 bits)) init(0)
  val compare = Reg(UInt(64 bits)) init(U(BigInt("ffffffffffffffff",16),64 bits))
  mtime := mtime + 1
  bus.readAndWrite(msip, 0)
  bus.readAndWrite(compare(31 downto 0), 0x4000)
  bus.readAndWrite(compare(63 downto 32), 0x4004)
  bus.readAndWrite(mtime(31 downto 0), 0xbff8)
  bus.readAndWrite(mtime(63 downto 32), 0xbffc)
  io.irq := mtime >= compare
  io.softwareIrq := msip(0)
}

/** Small level-sensitive PLIC profile: seven sources, one machine context.
  * Priorities are 0 or 1. Claim chooses the lowest eligible source ID.
  * A claimed source cannot pend again until completion.
  */
class Plic extends Component {
  val io = new Bundle {
    val bus = slave(Apb3(Apb3Config(22, 32)))
    val sources = in Bits(7 bits)
    val irq = out Bool()
  }
  val bus = Apb3SlaveFactory(io.bus)
  val enabled = Reg(Bits(32 bits)) init(0)
  val threshold = Reg(Bits(32 bits)) init(0)
  val priority = Vec.fill(7)(Reg(Bits(32 bits)) init(0))
  val pending = Reg(Bits(7 bits)) init(0)
  val active = Reg(Bits(7 bits)) init(0)
  val selected = UInt(3 bits)
  selected := 0
  for (i <- 6 to 0 by -1) {
    when(pending(i) && enabled(i+1) && priority(i)(0)) {
      selected := i+1
    }
  }
  for (i <- 0 until 7) {
    when(io.sources(i) && !active(i)) { pending(i) := True }
    bus.readAndWrite(priority(i), (i+1)*4)
  }
  val pendingWord = B(0,24 bits) ## pending ## False
  bus.read(pendingWord, 0x1000)
  bus.readAndWrite(enabled, 0x2000)
  bus.readAndWrite(threshold, 0x200000)
  bus.read(selected, 0x200004)
  bus.onRead(0x200004) {
    for (i <- 0 until 7) {
      when(selected === i+1) { pending(i) := False; active(i) := True }
    }
  }
  bus.onWrite(0x200004) {
    for (i <- 0 until 7) {
      when(io.bus.PWDATA === i+1 && enabled(i+1)) { active(i) := False }
    }
  }
  // Claim polling ignores the notification threshold.
  io.irq := selected =/= 0 && !threshold(0)
}

class Gpio extends Component {
  val io = new Bundle {
    val bus = slave(Apb3(Apb3Config(8,32)))
    val input = in Bits(32 bits)
    val output = out Bits(32 bits)
    val outputEnable = out Bits(32 bits)
    val irq = out Bool()
  }
  val bus = Apb3SlaveFactory(io.bus)
  val input = BufferCC(io.input, init=B(0,32 bits))
  val output = Reg(Bits(32 bits)) init(0)
  val enable = Reg(Bits(32 bits)) init(0)
  val irqEnable = Reg(Bits(32 bits)) init(0)
  bus.read(input, 0)
  bus.readAndWrite(output, 4)
  bus.readAndWrite(enable, 8)
  bus.readAndWrite(irqEnable, 12)
  io.output := output
  io.outputEnable := enable
  io.irq := (input & irqEnable).orR
}

/** Counter and watchdog. A write to count services the watchdog. */
class Timer extends Component {
  val io = new Bundle {
    val bus = slave(Apb3(Apb3Config(8,32)))
    val irq = out Bool()
    val watchdog = out Bool()
  }
  val bus = Apb3SlaveFactory(io.bus)
  val control = Reg(Bits(32 bits)) init(0)
  val count = Reg(UInt(32 bits)) init(0)
  val compare = Reg(UInt(32 bits)) init(U(0xffffffffL,32 bits))
  when(control(0)) { count := count + 1 }
  bus.readAndWrite(control, 0)
  bus.readAndWrite(count, 4)
  bus.readAndWrite(compare, 8)
  io.irq := control(0) && count >= compare
  io.watchdog := io.irq && control(1)
}

/** A nonzero full-word store is a completion event. Software defines the code. */
class Finisher extends Component {
  val io = new Bundle {
    val bus = slave(Apb3(Apb3Config(8,32)))
    val done = out Bool()
    val code = out Bits(32 bits)
    val irq = out Bool()
  }
  val bus = Apb3SlaveFactory(io.bus)
  val code = Reg(Bits(32 bits)) init(0)
  bus.readAndWrite(code, 0)
  io.code := code
  io.done := code =/= 0
  io.irq := False
}
