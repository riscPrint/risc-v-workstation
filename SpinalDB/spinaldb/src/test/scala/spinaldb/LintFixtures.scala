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
object LintFixtures {
  def main(args: Array[String]): Unit = {
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
