import java.io.File
import spinal.core._
import spinal.lib.bus.amba3.apb._
import spinal.lib.bus.amba4.axi._
import spinal.lib.bus.amba4.axilite._
import spinal.lib.bus.tilelink.{Bus, BusParameter}
import spinalchecks._
import spinaldb.{SpinalDB, DbOptions}

class NativeBusChild extends Component {
  val bus = in(AxiLite4(AxiLite4Config(32, 32)))
  val signature = out(RegNext(bus.flatten.map(_.asBits.xorR).reduce(_ ^ _)) init(False))
}
class NativeBusTop extends Component {
  val axi = in(Axi4(Axi4Config(32, 32, idWidth = 2,
    readIssuingCapability = 2, writeIssuingCapability = 2, combinedIssuingCapability = 4)))
  val lite = in(AxiLite4(AxiLite4Config(32, 32)))
  val apb = in(Apb3(Apb3Config(8, 32)))
  val tl = in(Bus(BusParameter.simple(32, 32, 16, 2).copy(withBCE = true, sinkWidth = 2)))
  val child = new NativeBusChild
  child.bus := lite
  val signature = out(Bool())
  signature := child.signature
}
object NativeBusCapture {
  def main(args: Array[String]): Unit = {
    require(args.length == 1, "usage: NativeBusCapture output-directory")
    val out = new File(args(0)).getCanonicalFile
    val (config, _) = SpinalChecks.install(SpinalConfig(targetDirectory = new File(out, "rtl").getPath,
      defaultConfigForClockDomains = ClockDomainConfig(resetKind = SYNC)),
      ChecksConfig(mode = Mode.Monitor, reportPath = new File(out, "checks.json").getPath))
    SpinalDB.generate(config, new File(out, "design.db"), DbOptions(pdg = false, blocks = false, hgldd = false))(new NativeBusTop)
  }
}
