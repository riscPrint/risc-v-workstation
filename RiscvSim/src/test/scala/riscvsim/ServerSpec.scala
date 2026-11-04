package riscvsim

import java.io.File
import java.nio.{ByteBuffer, ByteOrder}
import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite

class ServerSpec extends AnyFunSuite {
  class Adapter(stuck: Boolean) extends CoreAdapter {
    override def freshInstancePerRun = true
    type Model = Unit
    var compiled = 0
    var executed = 0
    def core = "fixture"
    def configs = Seq("test")
    def isa(config: String) = "rv32i"
    def xlen = 32
    def sourceDir = new File(".")
    def compile(key: ModelKey, work: File, cache: File): Unit = { compiled += 1 }
    def run(model: Unit, job: RunJob, ctx: RunContext): RunOutcome = {
      executed += 1
      if (stuck) Thread.sleep(60000)
      RunOutcome(Status.Fail, 1, 1, Some(7))
    }
  }
  def fixture(body: (File, File) => Unit): Unit = {
    val dir = Files.createTempDirectory("sim-server").toFile
    val elf = new File(dir, "test.elf")
    val header = ByteBuffer.allocate(64).order(ByteOrder.LITTLE_ENDIAN)
    header.put(Array[Byte](0x7f, 69, 76, 70, 1, 1))
    header.putShort(0x12, 243.toShort)
    Files.write(elf.toPath, header.array())
    try body(dir, elf) finally org.apache.commons.io.FileUtils.deleteDirectory(dir)
  }
  def request(dir: File, elf: File, name: String): String = ujson.write(ujson.Obj(
    "elf" -> elf.getPath, "out" -> new File(dir, name).getPath, "seed" -> 42))

  test("server refuses an adapter without a reset declaration") {
    val adapter = new Adapter(false) { override def freshInstancePerRun = false }
    val error = intercept[Cli.UsageError] {
      new Driver(adapter).serve(Map.empty, Iterator.empty, _ => ())
    }
    assert(error.getMessage.contains("fresh instance"))
    assert(adapter.compiled == 0 && adapter.executed == 0)
  }

  test("server reuses one compiled model after failure and stops on shutdown") {
    fixture { (dir, elf) =>
      val adapter = new Adapter(false)
      val driver = new Driver(adapter)
      val replies = scala.collection.mutable.ArrayBuffer.empty[ujson.Obj]
      assert(driver.serve(Map.empty, Iterator("bad json", request(dir, elf, "one"),
        request(dir, elf, "two"), "{\"op\":\"shutdown\"}", request(dir, elf, "three")), replies += _) == 0)
      assert(replies.size == 4 && replies.head.obj.contains("error"))
      assert(adapter.compiled == 1 && adapter.executed == 2)
      val sessions = replies.slice(1, 3).map(_("result")("details")("simulation_session"))
      assert(replies.slice(1, 3).forall(_("result")("execution_mode").str == "server"))
      assert(sessions(0)("id") == sessions(1)("id"))
      assert(sessions.map(_("model_run").num) == Seq(1.0, 2.0))
      assert(replies.last("shutdown").bool)
      val direct = driver.runOne(Cli.job(Map("elf" -> elf.getPath, "out" -> new File(dir, "direct").getPath), adapter, dir))
      assert(direct("execution_mode").str == "process")
      driver.cleanWorkspace()
    }
  }
  test("a crashed request reports an error before the next request runs") {
    fixture { (dir, elf) =>
      val adapter = new Adapter(false) {
        override def run(model: Unit, job: RunJob, ctx: RunContext): RunOutcome = {
          if (executed == 0) { executed += 1; throw new IllegalStateException("injected crash") }
          super.run(model, job, ctx)
        }
      }
      val driver = new Driver(adapter)
      val replies = scala.collection.mutable.ArrayBuffer.empty[ujson.Obj]
      assert(driver.serve(Map.empty, Iterator(request(dir, elf, "crash"),
        request(dir, elf, "next")), replies += _) == 0)
      assert(replies.map(_("result")("status").str) == Seq("error", "fail"))
      assert(replies.forall(_("result")("execution_mode").str == "server"))
      assert(adapter.executed == 2)
      driver.cleanWorkspace()
    }
  }

  test("server exits on abandoned worker before it reads another request") {
    fixture { (dir, elf) =>
      val adapter = new Adapter(true)
      val driver = new Driver(adapter)
      val replies = scala.collection.mutable.ArrayBuffer.empty[ujson.Obj]
      assert(driver.serve(Map("wall-timeout" -> "0.01"),
        Iterator(request(dir, elf, "one"), request(dir, elf, "two")), replies += _) == 2)
      assert(replies.size == 1)
      assert(replies.head("result")("details")("abandoned").bool)
      assert(replies.head("result")("execution_mode").str == "server")
      assert(adapter.executed == 1)
      driver.cleanWorkspace()
    }
  }
  test("each server request binds a distinct run identity to its result") {
    fixture { (dir, elf) =>
      val ids = scala.collection.mutable.ArrayBuffer.empty[String]
      val adapter = new Adapter(false) {
        override def run(model: Unit, job: RunJob, ctx: RunContext): RunOutcome = {
          ids += ctx.rvfiHeader("run_id").str
          super.run(model, job, ctx)
        }
      }
      val replies = scala.collection.mutable.ArrayBuffer.empty[ujson.Obj]
      val driver = new Driver(adapter)
      driver.serve(Map.empty, Iterator(request(dir, elf, "one"), request(dir, elf, "two")), replies += _)
      assert(ids.size == 2 && ids.distinct.size == 2)
      assert(replies.map(_("result")("details")("simulation_session")("run_id").str) == ids)
      driver.cleanWorkspace()
    }
  }

}
