package rvwsoc

import spinal.core._
import spinal.lib._
import spinal.lib.bus.amba3.apb._
import spinal.lib.bus.misc.SizeMapping

/** A project supplies the core and any protocol bridges in this wrapper.
  * The first profile has one unified APB3 master, one domain and 32-bit words.
  */
trait CoreWrapper { this: Component =>
  def bus: Apb3
  def interrupts: Bits // mip bit positions
  def debugReset: Bool
}

/** Word accesses only. APB3 has no byte strobes. ROM writes return an error. */
class WordMemory(addressBits: Int, words: Int, readOnly: Boolean,
                 image: Seq[BigInt]) extends Component {
  val io = new Bundle { val bus = slave(Apb3(Apb3Config(addressBits, 32))) }
  val mem = Mem(Bits(32 bits), words)
  require(image.size <= words)
  mem.initBigInt(image ++ Seq.fill(words - image.size)(BigInt(0)))
  val index = (io.bus.PADDR >> 2).resized
  val aligned = io.bus.PADDR(1 downto 0) === 0
  io.bus.PRDATA := mem.readAsync(index)
  io.bus.PREADY := True
  io.bus.PSLVERROR := !aligned || (io.bus.PWRITE && Bool(readOnly))
  if (!readOnly) {
    when(io.bus.PSEL.lsb && io.bus.PENABLE && io.bus.PWRITE && aligned) {
      mem.write(index, io.bus.PWDATA)
    }
  }
}

object Fabric {
  def connect(master: Apb3, targets: Seq[(Apb3, SizeMapping)]): Unit = {
    val decoder = Apb3Decoder(master, targets)
    ApbChecks(master)
    targets.foreach(t => ApbChecks(t._1))
    val selected = decoder.io.output.PSEL
    assert(CountOne(selected) <= 1, "SoC decode windows must be disjoint")
    for (((_, mapping), index) <- targets.zipWithIndex) {
      assert(selected(index) === (master.PSEL.lsb && mapping.hit(master.PADDR)), "SoC decode must match the map")
    }
    when(master.PSEL.lsb && selected === 0) {
      assert(master.PREADY && master.PSLVERROR, "Unmapped SoC accesses must return an error")
    }
  }
}

/** Protocol obligations on each APB3 endpoint. Assertions are not proof results. */
object ApbChecks {
  def apply(bus: Apb3): Unit = {
    val selected = bus.PSEL.lsb
    val hold = selected && (!bus.PENABLE || !bus.PREADY)
    val previousHold = RegNext(hold) init(False)
    val previousAddress = RegNext(bus.PADDR)
    val previousWrite = RegNext(bus.PWRITE)
    val previousData = RegNext(bus.PWDATA)
    val previousCompleted = RegNext(selected && bus.PENABLE && bus.PREADY) init(False)
    when(previousHold) {
      assert(selected && bus.PENABLE, "APB setup/wait must advance to access")
      assert(bus.PADDR === previousAddress && bus.PWRITE === previousWrite, "APB control must remain stable")
      when(previousWrite) { assert(bus.PWDATA === previousData, "APB write data must remain stable") }
    }
    when(previousCompleted) { assert(!selected || !bus.PENABLE, "APB completion requires setup or idle") }
  }
}
