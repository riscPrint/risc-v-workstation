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
  test("C1 records requested coverage and probe model flags") {
    val job = RunJob(elf = new java.io.File("program"), out = new java.io.File("out"),
      config = "flags", seed = 1, seedPicked = false, maxCycles = 100, memLatency = Some(0),
      rvfiTrace = true, rvfiCheck = false, wave = false, waveFrom = None, waveTo = None,
      konata = false, coverage = true, probes = true)
    val options = job.recordedOptions
    assert(options("coverage").bool)
    assert(options("probes").bool)
    assert(options("rvfi_trace").bool)
    assert(!options("rvfi_check").bool)
  }

}
