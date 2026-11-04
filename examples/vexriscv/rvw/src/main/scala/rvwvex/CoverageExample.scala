package rvwvex
import spinal.core._
import riscvsim.RtlCoverage
import java.io.File
/** Fetch events are speculative interface evidence. */
object CoverageExample {
  def main(args: Array[String]): Unit = {
    require(args.length == 2, "CoverageExample RTL_DIR PLAN.json")
    val report = VexTop.spinalConfig.copy(targetDirectory = args(0)).generateVerilog {
      val top = new VexTop
      top.rework {
        val accepted = Bool().setName("coverage_fetch_accepted")
        accepted := top.ibus.cmd.valid && top.ibus.cmd.ready
        RtlCoverage.tag(accepted, RtlCoverage.Bin("fetch-accepted", "event", "speculative", Seq(BigInt(1)),
          RtlCoverage.Source("CoverageExample.scala", 13), "Bool"))
      }
      top
    }
    RtlCoverage.write(RtlCoverage.plan(report, java.security.MessageDigest.getInstance("SHA-256")
      .digest(java.nio.file.Files.readAllBytes(new File(report.generatedSourcesPaths.head).toPath))
      .map(b => f"${b & 0xff}%02x").mkString, report.toplevel.clockDomain.clock,
      report.toplevel.clockDomain.reset), new File(args(1)))
  }
}
