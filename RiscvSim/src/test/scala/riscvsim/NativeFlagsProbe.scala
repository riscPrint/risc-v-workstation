package riscvsim

import java.io.File
import spinal.core._
import spinal.core.sim._

/** Small native regression fixture. Python launches it in separate JVMs with one shared cache. */
object NativeFlagsProbe {
  class FlagBox(path: String) extends BlackBox {
    val io = new Bundle { val bad = out Bool() }
    noIoPrefix()
    setDefinitionName("FlagBox")
    addRTLPath(path)
  }
  class Top(path: String) extends Component {
    val io = new Bundle { val bad = out Bool() }
    io.bad := new FlagBox(path).io.bad
  }
  def main(args: Array[String]): Unit = {
    val root = new File(args(0))
    val adapter = new CoreAdapter {
      type Model = SimCompiled[Top]
      def core = "native-flags-fixture"
      def configs = Seq("flag")
      def xlen = 64
      def isa(config: String) = "rv64i"
      def sourceDir = root
      def compile(key: ModelKey, work: File, cache: File): Model = {
        val config = RiscvSimConfig(key, work, cache, SpinalConfig())
        require(config._disableCache == !NativeBuild.current("cache_enabled").bool)
        config.compile(RiscvSimConfig.elaborate(key, work, SpinalConfig()) {
          new Top(new File(root, "FlagBox.v").getPath)
        })
      }
      override def generatedVerilog(model: Model): Seq[File] =
        Option(model.compiledPath).toSeq.flatMap(d => Option(new File(d, "rtl").listFiles()).toSeq.flatten)
          .filter(f => f.isFile && f.getName.endsWith(".v"))
      def run(model: Model, job: RunJob, ctx: RunContext): RunOutcome = {
        val (status, code, message, cycles) = SimSession.run(model, job, ctx) { (dut, ctl) =>
          sleep(1)
          ctl.tick()
          ctl.finish(if (dut.io.bad.toBoolean) Status.Fail else Status.Pass)
        }
        RunOutcome(status, cycles, 1, code, message)
      }
    }
    val driver = new Driver(adapter) {
      override val workRoot: File = new File(root, "work")
      override val cacheDir: File = new File(root, args(1))
    }
    val job = RunJob(TestPrograms("fail"), new File(root, args(2)), "flag", 1, false, 100, None,
      false, false, false, None, None, false, false)
    val result = driver.runOne(job)
    require(Set("pass", "fail").contains(result("status").str), result.toString)
  }
}
