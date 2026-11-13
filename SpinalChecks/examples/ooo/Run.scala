package spinalchecks.examples.ooo

import java.nio.file.{Files, Paths}
import spinal.core._
import spinal.core.sim._
import spinalchecks._
import spinalprobes.Probe

object Run {
  val bugs = Seq("clean","leak","double_allocate","commit_order","not_ready","young_store","stale_map","lost_flush")
  def main(args: Array[String]): Unit = {
    val selected = args.headOption.toSeq match { case Nil => bugs; case xs => xs }
    val formal = sys.env.get("RVW_OOO_FORMAL").contains("1")
    for(bug <- selected) {
      require(bugs.contains(bug))
      val out = "out/" + bug
      val (cfg, checks) = SpinalChecks.install(SpinalConfig(targetDirectory=out,
        defaultConfigForClockDomains=ClockDomainConfig(resetKind=SYNC)),
        ChecksConfig(mode=if(formal) Mode.Assert else Mode.Monitor,
          enable=Seq("queue.*","arbiter.*","freelist.*","execution.*","store.*","recovery.*")))
      if(formal) Probe.enabled(true) { cfg.includeFormal.generateVerilog(new TinyOoo(bug)) }
      else {
        val sim = Probe.enabled(true) {
          SimConfig.withConfig(cfg).workspacePath("simWorkspace").workspaceName(bug).withVerilator.compile(new TinyOoo(bug))
        }
        sim.doSim(seed=17) { dut =>
          dut.io.dispatch #= false; dut.io.wake #= false; dut.io.commit #= false
          dut.io.mispredict #= false; dut.io.load #= false
          dut.io.destination #= 0; dut.io.store #= false; dut.io.data #= 0
          dut.clockDomain.forkStimulus(10)
          dut.clockDomain.waitSampling(4)
          val random=new scala.util.Random(17)
          for(cycle <- 0 until 1200) {
            dut.clockDomain.waitFallingEdge()
            dut.io.dispatch #= random.nextBoolean()
            dut.io.wake #= random.nextInt(3)==0
            dut.io.commit #= random.nextBoolean()
            dut.io.mispredict #= random.nextInt(23)==0
            dut.io.load #= random.nextBoolean()
            dut.io.destination #= random.nextInt(2)
            dut.io.store #= random.nextBoolean()
            dut.io.data #= random.nextInt(256)
          }
          dut.clockDomain.waitSampling(2)
          val fs=ChecksSim.firings(dut)
          val expected=Map("leak"->"freelist.conservation","double_allocate"->"freelist.allocate",
            "commit_order"->"queue.order","not_ready"->"execution.operands",
            "young_store"->"store.forward_age","stale_map"->"recovery.map","lost_flush"->"recovery.flush")
          ChecksSim.writeRunReport(dut,out+"/run-checks.json",Seq("seed"->Json.Num(17)))
          if(bug=="clean") require(fs.isEmpty, fs.map(_.check.id).mkString(","))
          else require(fs.exists(_.check.kind==expected(bug)), "missing expected failure "+expected(bug))
        }
      }
    }
  }
}
