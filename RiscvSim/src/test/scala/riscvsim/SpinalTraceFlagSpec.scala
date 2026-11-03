package riscvsim

import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite
import spinal.core._

class SpinalTraceFlagSpec extends AnyFunSuite {
  class Counter extends Component {
    val value = out UInt(8 bits)
    val count = Reg(UInt(8 bits)) init(0)
    count := count + 1
    value := count
  }

  test("the trace flag separates model identity and manifest jobs") {
    val plain = ModelKey("test")
    val traced = plain.copy(spinaltrace = true)
    assert(plain != traced && plain.name != traced.name)
    assert(traced.toJson("spinaltrace").bool)
    val args = Cli.parse(Seq("--spinaltrace"))
    assert(Cli.bool(args, "spinaltrace"))
    assert(Cli.bool(Cli.fromJson(ujson.Obj("spinaltrace" -> true)), "spinaltrace"))
  }

  test("an adapter without a trace model cannot build one") {
    val adapter = new CoreAdapter {
      type Model = Unit
      def core = "missing-trace-model"
      def configs = Seq("test")
      def xlen = 32
      def isa(config: String) = "rv32i"
      def sourceDir = new java.io.File(".")
      def compile(key: ModelKey, work: java.io.File, cache: java.io.File): Unit = ()
      def run(model: Unit, job: RunJob, ctx: RunContext): RunOutcome =
        throw new UnsupportedOperationException("must not run")
    }
    val driver = new Driver(adapter)
    try {
      val err = intercept[IllegalArgumentException] {
        driver.model(ModelKey("test", spinaltrace = true), _ => ())
      }
      assert(err.getMessage.contains("SpinalTrace model"))
      val job = Cli.job(Cli.parse(Seq("--elf", "x", "--out", "y", "--spinaltrace")),
        adapter, new java.io.File("."))
      assert(job.spinaltrace && job.model.spinaltrace)
      assert(driver.replay(job).contains("--spinaltrace"))
    } finally driver.cleanWorkspace()
  }

  test("only traced elaboration emits a dependency graph") {
    val work = Files.createTempDirectory("riscvsim-trace-flag").toFile
    try {
      val plain = ModelKey("counter")
      RiscvSimConfig.elaborate(plain, work, SpinalConfig())(new Counter)
      assert(!RiscvSimConfig.dependencyGraph(plain, work).exists())
      val traced = plain.copy(spinaltrace = true)
      RiscvSimConfig.elaborate(traced, work, SpinalConfig())(new Counter)
      val graph = RiscvSimConfig.dependencyGraph(traced, work)
      assert(graph.isFile)
      assert(ujson.read(Files.readString(graph.toPath))("vertices").arr.nonEmpty)
    } finally org.apache.commons.io.FileUtils.deleteDirectory(work)
  }
}
