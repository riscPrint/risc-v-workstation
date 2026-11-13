package riscvsim

import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite
import spinal.core._

class CoverageLocationsSpec extends AnyFunSuite {
  class LocationTop extends Component {
    val a = in Bool()
    val b = out Bool()
    b := !a
  }

  test("coverage RTL retains Scala source navigation comments") {
    val work = Files.createTempDirectory("coverage-locations-").toFile
    val key = ModelKey("locations", coverage = true)
    val report = RiscvSimConfig.elaborate(key, work, SpinalConfig())(new LocationTop)
    val rtl = Files.readString(new java.io.File(report.generatedSourcesPaths.head).toPath)
    assert(rtl.contains("CoverageLocationsSpec.scala"))
  }
}
