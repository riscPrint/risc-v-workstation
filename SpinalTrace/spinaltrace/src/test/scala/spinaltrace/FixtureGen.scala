package spinaltrace

import java.io.File
import java.nio.file.{Files, StandardCopyOption}

import spinal.core._
import spinal.core.sim._
import spinaltrace.examples._

/** Regenerates the checked-in Rust fixtures (spinaltrace-rs/tests/fixtures/<design>/):
  * pdg.json, wave.vcd, hgldd/<Top>.dd and meta.json (check times used by the Rust tests).
  * Run: sbt "Test/runMain spinaltrace.FixtureGen ../spinaltrace-rs/tests/fixtures" */
object FixtureGen extends App {
  val out  = new File(if (args.nonEmpty) args(0) else "../spinaltrace-rs/tests/fixtures").getCanonicalFile
  val opts = SpinalTraceSimOptions(extract = ExtractOptions(sourceRoots = Seq(new File("../examples/src"))), onFailure = OnFailure.Print)
  val sim  = SimConfig.workspacePath("target/fixturegen")

  def save[T <: Component](name: String, t: TracedSim[T], test: String, times: Map[String, Long]): Unit = {
    val dir = new File(out, name); dir.mkdirs()
    Files.copy(t.pdg.toPath, new File(dir, "pdg.json").toPath, StandardCopyOption.REPLACE_EXISTING)
    Files.copy(t.waveFile(test).get.toPath, new File(dir, "wave.vcd").toPath, StandardCopyOption.REPLACE_EXISTING)
    t.hgldd.foreach { h =>
      val hd = new File(dir, "hgldd"); hd.mkdirs()
      h.listFiles().filter(_.getName.endsWith(".dd")).foreach(f => Files.copy(f.toPath, new File(hd, f.getName).toPath, StandardCopyOption.REPLACE_EXISTING))
    }
    val meta = ujson.Obj.from(times.map { case (k, v) => k -> ujson.Num(SpinalTraceSim.traceTime(v).toDouble) })
    Files.write(new File(dir, "meta.json").toPath, ujson.write(meta, indent = 1).getBytes("UTF-8"))
    println(s"fixture $name -> $dir")
  }

  locally {
    val t = SpinalTraceSim.compile(sim, opts)(new GCD)
    var done = 0L
    t.doSim("gcd") { dut =>
      dut.clockDomain.forkStimulus(10)
      dut.io.a #= 24; dut.io.b #= 36; dut.io.loadValues #= true
      dut.clockDomain.waitSampling()
      dut.io.loadValues #= false
      dut.clockDomain.waitSampling(6)
      done = simTime()
    }
    save("gcd", t, "gcd", Map("done" -> done))
  }
  locally {
    val t = SpinalTraceSim.compile(sim, opts)(new SwitchEnum)
    var sub, dflt = 0L
    t.doSim("switch") { dut =>
      dut.clockDomain.forkStimulus(10)
      dut.io.a #= 9; dut.io.b #= 4; dut.io.op #= AluOp.ADD
      dut.clockDomain.waitSampling(2)
      dut.io.op #= AluOp.SUB
      dut.clockDomain.waitSampling(2); sub = simTime()
      dut.clockDomain.waitSampling()
      dut.io.op #= AluOp.PASS
      dut.clockDomain.waitSampling(2); dflt = simTime()
    }
    save("switch_enum", t, "switch", Map("sub" -> sub, "default" -> dflt))
  }
  locally {
    val t = SpinalTraceSim.compile(sim, opts)(new VecDynamic)
    var at = 0L
    t.doSim("vec") { dut =>
      dut.clockDomain.forkStimulus(10)
      dut.io.wrEn #= false; dut.io.wrIdx #= 0; dut.io.wrData #= 0; dut.io.rdIdx #= 0
      dut.clockDomain.waitSampling(2)
      dut.io.wrEn #= true; dut.io.wrIdx #= 2; dut.io.wrData #= 0x55
      dut.clockDomain.waitSampling()
      dut.io.wrIdx #= 1; dut.io.wrData #= 0x11
      dut.clockDomain.waitSampling()
      dut.io.wrEn #= false; dut.io.rdIdx #= 2
      dut.clockDomain.waitSampling(2); at = simTime()
    }
    save("vec_dynamic", t, "vec", Map("read" -> at))
  }
  locally {
    val t = SpinalTraceSim.compile(sim, opts)(new ResetCounter)
    var before, after = 0L
    t.doSim("reset") { dut =>
      dut.clockDomain.forkStimulus(10)
      dut.io.enable #= true
      dut.clockDomain.waitSampling(6); before = simTime()
      dut.clockDomain.assertReset()
      dut.clockDomain.waitRisingEdge(2)
      dut.clockDomain.deassertReset()
      dut.clockDomain.waitSampling(3); after = simTime()
      dut.clockDomain.waitSampling()
    }
    save("reset_counter", t, "reset", Map("before" -> before, "after" -> after))
  }
  locally {
    val t = SpinalTraceSim.compile(sim, opts)(new SyncMem)
    var at = 0L
    t.doSim("mem") { dut =>
      dut.clockDomain.forkStimulus(10)
      dut.io.wrEn #= false; dut.io.wrAddr #= 0; dut.io.wrData #= 0; dut.io.rdAddr #= 0
      dut.clockDomain.waitSampling(2)
      dut.io.wrEn #= true; dut.io.wrAddr #= 3; dut.io.wrData #= 0x42
      dut.clockDomain.waitSampling()
      dut.io.wrAddr #= 5; dut.io.wrData #= 0x99
      dut.clockDomain.waitSampling()
      dut.io.wrEn #= false; dut.io.rdAddr #= 3
      dut.clockDomain.waitSampling(2); at = simTime()
    }
    save("sync_mem", t, "mem", Map("read" -> at))
  }
}
