package riscvsim

import java.io.File
import org.scalatest.funsuite.AnyFunSuite

class SimThreadsSpec extends AnyFunSuite {
  private val capable = new CoreAdapter {
    type Model = ToyAdapter.Model
    def core = ToyAdapter.core
    def configs = ToyAdapter.configs
    def isa(c: String) = ToyAdapter.isa(c)
    def xlen = ToyAdapter.xlen
    def sourceDir = ToyAdapter.sourceDir
    override def supportsSimThreads = true
    def compile(k: ModelKey, w: File, c: File): Model = ToyAdapter.compile(k, w, c)
    def run(m: Model, j: RunJob, c: RunContext): RunOutcome = ToyAdapter.run(m, j, c)
  }
  private val options = Map("elf" -> "program", "out" -> "run", "sim-threads" -> "2")
  test("per-request thread choice enters model identity and replay") {
    val job = Cli.job(options, capable, new File("."))
    assert(job.simThreads.contains(2))
    assert(job.model.name.endsWith("_simt2"))
    assert(job.model.toJson("sim_threads").num == 2)
    val config = RiscvSimConfig(job.model, new File("target/thread-work"), new File("target/thread-cache"), spinal.core.SpinalConfig())
    assert(config._simulatorFlags.contains("--threads 2"))
    assert(new Driver(capable).replay(job).contains("--sim-threads 2"))
    assert(Cli.job(options - "sim-threads", capable, new File(".")).simThreads.isEmpty)
  }
  test("unsupported adapters, invalid counts and inherited overrides refuse") {
    intercept[Cli.UsageError](Cli.job(options, ToyAdapter, new File(".")))
    for (value <- Seq("0", "-1", "65", "1.5", "2147483648"))
      intercept[Cli.UsageError](Cli.job(options.updated("sim-threads", value), capable, new File(".")))
    intercept[Cli.UsageError](Cli.simThreads(options, capable, "--threads 4"))
    intercept[Cli.UsageError](Cli.simThreads(options, capable, "--threads=4"))
    assert(Cli.simThreads(options, capable, "--threads-dpi all").contains(2))
  }
  test("thread cache keys cannot alias inherited or other explicit counts") {
    val inherited = ModelKey("fixture")
    val one = inherited.copy(simThreads = Some(1))
    val two = inherited.copy(simThreads = Some(2))
    assert(Set(inherited.name, one.name, two.name).size == 3)
    intercept[IllegalArgumentException](inherited.copy(simThreads = Some(0)))
  }
}
