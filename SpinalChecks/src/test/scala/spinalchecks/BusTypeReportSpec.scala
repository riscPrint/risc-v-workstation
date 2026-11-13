package spinalchecks

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.lib.bus.tilelink._
import scala.io.Source

class BusTypeReportSpec extends AnyFunSuite {
  class Top extends Component {
    val bus = in(Bus(BusParameter.simple(32, 32, 16, 2)))
  }
  test("report retains exact TileLink type and library options") {
    val (cfg, result) = SpinalChecks.install(
      SpinalConfig(targetDirectory = "generated/bus-types"),
      ChecksConfig(mode = Mode.Monitor, reportPath = "generated/bus-types/types.json"))
    cfg.generateVerilog(new Top)
    val src = Source.fromFile(result.reportFile)
    val json = try src.mkString finally src.close()
    assert(result.buses.size == 1)
    assert(json.contains("spinal.lib.bus.tilelink.Bus"))
    assert(json.contains("\"size_max\": 4"))
    assert(json.contains("bus_a_valid"))
    assert(result.buses.head.options("with_bce") == 0)
  }
}
