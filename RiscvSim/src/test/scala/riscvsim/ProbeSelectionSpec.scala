package riscvsim

import org.scalatest.funsuite.AnyFunSuite
import spinalprobes.ProbeSite

class ProbeSelectionSpec extends AnyFunSuite {
  private val names = Seq("topdown_slots", "topdown_retiring", "topdown_bad_speculation", "topdown_frontend_bound", "topdown_backend_bound")
  private def site(index: Int, kind: String, name: String) = ProbeSite(index, kind, name, null, Nil, Map.empty)
  test("top-down mode selects only five counters and gives consecutive ids") {
    val sites = Seq(site(0, "stage", "stage")) ++ names.zipWithIndex.map { case (n,i) => site(i+1,"counter",n) }
    val selected = ProbeCollector.select(sites, "topdown")
    assert(selected.map(_.name) == names)
    assert(selected.map(_.index) == (0 until 5))
    assert(ProbeCollector.select(sites, "all") == sites)
  }
  test("top-down mode refuses partial bindings and unknown modes") {
    intercept[IllegalArgumentException] { ProbeCollector.select(Nil,"topdown") }
    intercept[IllegalArgumentException] { ProbeCollector.select(Nil,"missing") }
  }
  test("CLI and replay record the summary mode and reject unsupported choices") {
    val capable = new CoreAdapter {
      type Model = ToyAdapter.Model
      def core = ToyAdapter.core
      def configs = ToyAdapter.configs
      def isa(c: String) = ToyAdapter.isa(c)
      def xlen = ToyAdapter.xlen
      def sourceDir = ToyAdapter.sourceDir
      override def supportsProbes = true
      def compile(k: ModelKey, w: java.io.File, c: java.io.File): Model = ToyAdapter.compile(k,w,c)
      def run(m: Model, j: RunJob, c: RunContext): RunOutcome = ToyAdapter.run(m,j,c)
    }
    val options = Cli.parse(Seq("--elf","program","--out","run","--probes","--probe-mode","topdown"))
    val job = Cli.job(options,capable,new java.io.File("."))
    assert(job.probeMode == "topdown")
    assert(job.recordedOptions("probe_mode").str == "topdown")
    assert(new Driver(capable).replay(job).contains("--probe-mode topdown"))
    intercept[Cli.UsageError] { Cli.job(options - "probes",capable,new java.io.File(".")) }
    intercept[Cli.UsageError] { Cli.job(options.updated("probe-mode","missing"),capable,new java.io.File(".")) }
  }

}
