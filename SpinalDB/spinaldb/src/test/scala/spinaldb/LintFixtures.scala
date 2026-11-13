package spinaldb

import java.nio.file.{Files, Paths}
import spinal.core._

/** Deliberate structural faults. crossClockDomain permits their RTL emission. */
class LintReference(width: Int, withSync: Boolean, sharedClock: Boolean) extends Component {
  val clkA, clkB = in Bool()
  val data = in Bits(width bits)
  val result = out Bits(width bits)
  val a = new ClockingArea(ClockDomain(clkA, config=ClockDomainConfig(resetKind=BOOT))) {
    val source = RegNext(data) init(0)
  }
  val b = new ClockingArea(ClockDomain(if(sharedClock) clkA else clkB,
      config=ClockDomainConfig(resetKind=BOOT))) {
    val sample = RegNext(a.source) init(0)
    sample.addTag(crossClockDomain)
    val last = if(withSync) RegNext(sample) init(0) else sample
    result := last
  }
}
class ResetReference(independent: Boolean, asynchronous: Boolean) extends Component {
  val clk, resetA, resetB = in Bool()
  val data = in Bool()
  val result = out Bool()
  val config = ClockDomainConfig(resetKind=if(asynchronous) ASYNC else SYNC)
  val a = new ClockingArea(ClockDomain(clk, resetA, config=config)) {
    val source = RegNext(data) init(False)
  }
  val b = new ClockingArea(ClockDomain(clk, if(independent) resetB else resetA, config=config)) {
    val sample = RegNext(a.source) init(False)
    sample.addTag(crossClockDomain)
    result := sample
  }
}
/** Small topology cases. Protocol behavior is deliberately outside this fixture. */
class PairedReference(fifo: Boolean, broken: Boolean, merge: Boolean) extends Component {
  val clkA, clkB = in Bool()
  val data = in Bits(8 bits)
  val result = out Bits(8 bits)
  val width = if(fifo) 3 else 1
  val cdA = ClockDomain(clkA, config=ClockDomainConfig(resetKind=BOOT))
  val cdB = ClockDomain(clkB, config=ClockDomainConfig(resetKind=BOOT))
  val a = new ClockingArea(cdA) {
    val binary = Reg(UInt(width bits)) init(0)
    binary := binary + 1
    val source = RegNext((binary ^ (binary |>> 1)).asBits) init(0)
  }
  val b = new ClockingArea(cdB) {
    val binary = Reg(UInt(width bits)) init(0)
    binary := binary + 1
    val source = RegNext((binary ^ (binary |>> 1)).asBits) init(0)
    val first = RegNext(a.source) init(0)
    first.addTag(crossClockDomain)
    val last = RegNext(first) init(0)
    val merged = RegNext(if(merge) last ^ source else last) init(0)
  }
  val reverse = new ClockingArea(cdA) {
    val first = RegNext(if(broken) b.source ^ a.source else b.source) init(0)
    first.addTag(crossClockDomain)
    val last = RegNext(first) init(0)
  }
  if(fifo) {
    val storage = Mem(Bits(8 bits), 4).setName("storage")
    val write = new ClockingArea(cdA) {
      storage.write(a.binary(1 downto 0), data)
    }
    val read = new ClockingArea(cdB) {
      val value = storage.readSync(b.binary(1 downto 0), clockCrossing=true)
    }
    result := read.value ^ b.last.resize(8) ^ reverse.last.resize(8)
  } else {
    result := b.merged.resize(8) ^ reverse.last.resize(8)
  }
}
class ReconvergeReference(merge: Boolean) extends Component {
  val clkA, clkB = in Bool()
  val dataA, dataB = in Bool()
  val result = out Bits(2 bits)
  val a = new ClockingArea(ClockDomain(clkA, config=ClockDomainConfig(resetKind=BOOT))) {
    val x = RegNext(dataA) init(False)
    val y = RegNext(dataB) init(False)
  }
  val b = new ClockingArea(ClockDomain(clkB, config=ClockDomainConfig(resetKind=BOOT))) {
    val x1 = RegNext(a.x) init(False); x1.addTag(crossClockDomain)
    val x2 = RegNext(x1) init(False)
    val y1 = RegNext(a.y) init(False); y1.addTag(crossClockDomain)
    val y2 = RegNext(y1) init(False)
    val sink = RegNext(if(merge) x2 ^ y2 else x2) init(False)
    result := y2.asBits ## sink.asBits
  }
}
/** Complete conditional assignments, including a nested elsewhen and enum mux. */
class CompleteMuxReference extends Component {
  val a, b, data = in Bool()
  val result, selected, localResult = out Bool()
  localResult := False
  when(a) {
    val conditionalLocal = data ^ b
    localResult := conditionalLocal
  }
  when(a) { result := data }.elsewhen(b) { result := !data }.otherwise { result := False }
  val maskResult = out Bits(2 bits)
  for (i <- 0 until 2) {
    when(a) { maskResult(i) := data }.otherwise { maskResult(i) := b }
  }
  val sel = in UInt(2 bits)
  switch(sel) {
    is(0) { selected := a }
    is(1) { selected := b }
    default { selected := data }
  }
}

object LintMuxFixture {
  def main(args: Array[String]): Unit = {
    val dir = Paths.get(args(0)); Files.createDirectories(dir)
    SpinalDB.generate(SpinalConfig(targetDirectory=dir.resolve("rtl").toString),
      dir.resolve("design.db").toFile, DbOptions(pdg=false, blocks=false, hgldd=false))(
      new CompleteMuxReference)
  }
}

object LintFixtures {
  def main(args: Array[String]): Unit = {
    for ((name, fifo, broken) <- Seq(("handshake", false, false),
        ("handshake-broken", false, true), ("fifo", true, false), ("fifo-broken", true, true))) {
      val dir = Paths.get(args(0)).resolve(name); Files.createDirectories(dir)
      SpinalDB.generate(SpinalConfig(targetDirectory=dir.resolve("rtl").toString),
        dir.resolve("design.db").toFile, DbOptions(pdg=false, blocks=false, hgldd=false, sourceRoots=Nil))(
        new PairedReference(fifo, broken, false))
    }
    for (merge <- Seq(false, true)) {
      val dir = Paths.get(args(0)).resolve(if(merge) "reconverge" else "separate"); Files.createDirectories(dir)
      SpinalDB.generate(SpinalConfig(targetDirectory=dir.resolve("rtl").toString),
        dir.resolve("design.db").toFile, DbOptions(pdg=false, blocks=false, hgldd=false, sourceRoots=Nil))(
        new ReconvergeReference(merge))
    }
    for ((name, width, sync, same) <- Seq(
      ("single", 8, false, true), ("unsafe", 1, false, false),
      ("sync", 1, true, false), ("bus", 8, false, false))) {
      val dir = Paths.get(args(0)).resolve(name); Files.createDirectories(dir)
      SpinalDB.generate(SpinalConfig(targetDirectory=dir.resolve("rtl").toString),
        dir.resolve("design.db").toFile, DbOptions(pdg=false, blocks=false, hgldd=false, sourceRoots=Nil))(
        new LintReference(width, sync, same))
    }
    for ((name, independent, async) <- Seq(("reset-shared", false, false),
        ("reset-independent", true, false), ("reset-async", true, true))) {
      val dir = Paths.get(args(0)).resolve(name); Files.createDirectories(dir)
      SpinalDB.generate(SpinalConfig(targetDirectory=dir.resolve("rtl").toString),
        dir.resolve("design.db").toFile, DbOptions(pdg=false, blocks=false, hgldd=false, sourceRoots=Nil))(
        new ResetReference(independent, async))
    }
  }
}

/** A bank has four paths but one reset-domain review item. */
class ResetBankReference extends Component {
  val data = in Bits(4 bits)
  val result = out Bits(4 bits)
  val sources = Vec.fill(4)(Reg(Bool()) init(False))
  val samples = Vec.fill(4)(Reg(Bool()))
  for (i <- 0 until 4) { sources(i) := data(i); samples(i) := sources(i) }
  result := samples.asBits
}
object LintBankFixture {
  def main(args: Array[String]): Unit = {
    val dir = Paths.get(args(0)); Files.createDirectories(dir)
    SpinalDB.generate(SpinalConfig(targetDirectory=dir.resolve("rtl").toString),
      dir.resolve("design.db").toFile, DbOptions(pdg=false, blocks=false, hgldd=false))(
      new ResetBankReference)
  }
}
