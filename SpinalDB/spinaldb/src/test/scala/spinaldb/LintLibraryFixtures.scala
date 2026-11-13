package spinaldb

import java.nio.file.{Files, Paths}
import spinal.core._
import spinal.lib._

/** Spinal library CDC structures for `rvw lint`: BufferCC, StreamFifoCC, PulseCCByToggle,
  * a reset synchronizer from ResetCtrl, and a divided clock. Structure only, not protocol. */
class LibraryReference extends Component {
  val clkA, clkB, rawReset = in Bool()
  val flag = in Bool()
  val push = slave Stream(Bits(8 bits))
  val pop = master Stream(Bits(8 bits))
  val pulseIn = in Bool()
  val pulseOut, flagOut, slowOut = out Bool()
  val cdA = ClockDomain(clkA, config = ClockDomainConfig(resetKind = BOOT), frequency = FixedFrequency(100 MHz))
  val cdB = ClockDomain(clkB, config = ClockDomainConfig(resetKind = BOOT))
  val resetB = ResetCtrl.asyncAssertSyncDeassert(rawReset, cdB)
  val cdBReset = ClockDomain(clkB, resetB, config = ClockDomainConfig(resetKind = ASYNC))
  val a = new ClockingArea(cdA) {
    val flagReg = RegNext(flag) init(False)
    val toggle = Reg(Bool()) init(False)
    toggle := !toggle
  }
  val b = new ClockingArea(cdBReset) {
    flagOut := RegNext(BufferCC(a.flagReg, init = False)) init(False)
  }
  val fifo = StreamFifoCC(Bits(8 bits), 8, cdA, cdB)
  fifo.io.push << push
  fifo.io.pop >> pop
  val pulse = PulseCCByToggle(pulseIn, cdA, cdB)
  pulseOut := pulse
  val cdSlow = ClockDomain(a.toggle, config = ClockDomainConfig(resetKind = BOOT))
  cdSlow.setSynchronousWith(cdA)
  val slow = new ClockingArea(cdSlow) {
    val x = RegNext(a.flagReg) init(False)
    slowOut := x
  }
}

object LintLibraryFixtures {
  def main(args: Array[String]): Unit = {
    val dir = Paths.get(args(0)).resolve("library"); Files.createDirectories(dir)
    SpinalDB.generate(SpinalConfig(targetDirectory = dir.resolve("rtl").toString),
      dir.resolve("design.db").toFile, DbOptions(pdg = false, blocks = false, hgldd = false, sourceRoots = Nil))(
      new LibraryReference)
  }
}
