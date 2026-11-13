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
      val out = sys.env.getOrElse("RVW_OOO_RUN_ROOT", "out") + "/" + bug
      Files.createDirectories(Paths.get(out))
      val (cfg, checks) = SpinalChecks.install(SpinalConfig(targetDirectory=out,
        defaultConfigForClockDomains=ClockDomainConfig(resetKind=SYNC)),
        ChecksConfig(mode=if(formal) Mode.Assert else Mode.Monitor,
          enable=Seq("rename.*","queue.*","arbiter.*","freelist.*","execution.*","store.*","recovery.*")))
      if(formal) Probe.enabled(true) { cfg.includeFormal.generateVerilog(new TinyOoo(bug)) }
      else {
        val sim = Probe.enabled(true) {
          SimConfig.withConfig(cfg).workspacePath("simWorkspace").workspaceName(bug).withVerilator.compile(new TinyOoo(bug))
        }
        sim.doSim(seed=17) { dut =>
          dut.io.dispatch #= false; dut.io.wake #= false; dut.io.commit #= false
          dut.io.mispredict #= false; dut.io.load #= false
          dut.io.fence #= false
          dut.io.destination #= 0; dut.io.store #= false; dut.io.data #= 0
          dut.clockDomain.forkStimulus(10)
          dut.clockDomain.waitSampling(4)
          val collector = new riscvsim.ProbeCollector(Probe.of(dut), new java.io.File(out, "probe-events.jsonl"))
          val trace = new java.io.PrintWriter(out + "/rvfi.jsonl")
          trace.println(ujson.write(ujson.Obj("schema"->"rvw.rvfi/1", "xlen"->32, "core"->"tiny-ooo-command-fixture",
            "config"->bug,"isa"->"rv32i","elf"->"commands.json")))
          var order = 0L
          var sampled = 0L
          dut.clockDomain.onSamplings {
            collector.sample(sampled)
            if(dut.io.retired.toBoolean) {
              val rd = dut.retiredDestination.toInt + 1
              val value = dut.retiredValue.toInt
              val pc = 0x80000000L + dut.retiredSerial.toLong * 4
              val row = ujson.Obj("order"->order.toDouble,"cycle"->sampled.toDouble,"mode"->3,
                "pc"->s"0x${pc.toHexString}","pc_next"->s"0x${(pc+4).toHexString}",
                "insn"->s"0x${((value << 20) | (rd << 7) | 0x13).toHexString}",
                "rs1"->0,"rs2"->0,"rd"->rd,"rs1_rdata"->"0x0","rs2_rdata"->"0x0", "rd_wdata"->s"0x${value.toHexString}",
                "mem_addr"->"0x0","mem_rdata"->"0x0","mem_wdata"->"0x0","mem_rmask"->0,"mem_wmask"->0,
                "trap"->false,"intr"->false,"halt"->false,"mem_fault"->false)
              trace.println(ujson.write(row)); order += 1
            }
            sampled += 1
          }
          val faultFile = sys.env.get("RVW_OOO_FAULT").map(p => ujson.read(Files.readString(Paths.get(p))))
          var faultApplied = false
          val random=new scala.util.Random(17)
          for(cycle <- 0 until 1200) {
            dut.clockDomain.waitFallingEdge()
            faultFile.foreach { doc =>
              for(f <- doc("faults").arr if cycle == f("cycle").num.toInt) {
                require(f("site").str == "head" && f("kind").str == "flip", "fixture supports a head flip only")
                val before = dut.head.toBigInt
                val bit = f("bit").num.toInt
                require(bit >= 0 && bit < 2)
                dut.head #= before.flipBit(bit)
                sleep(1)
                faultApplied = dut.head.toBigInt == before.flipBit(bit)
              }
            }
            dut.io.dispatch #= random.nextBoolean()
            dut.io.fence #= random.nextInt(31)==0
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
          collector.close(sampled)
          trace.println(ujson.write(ujson.Obj("event"->"end","cycle"->sampled.toDouble,"status"->(if(fs.isEmpty) "pass" else "fail"))))
          trace.close()
          val details = ujson.Obj()
          if(faultFile.nonEmpty) details("fault") = ujson.Obj("applied"->faultApplied)
          Files.writeString(Paths.get(out,"result.json"),ujson.write(ujson.Obj("schema"->"rvw.run/1", "core"->"tiny-ooo-command-fixture",
            "config"->bug,"status"->(if(fs.isEmpty) "pass" else "fail"),"cycles"->sampled.toDouble,"instret"->order.toDouble,
            "artifacts"->ujson.Obj("rvfi_trace"->"rvfi.jsonl","probes"->"probe-events.jsonl"),"details"->details)))
          if(bug=="clean" && faultFile.isEmpty) require(fs.isEmpty, fs.map(_.check.id).mkString(","))
          else if(bug!="clean") require(fs.exists(_.check.kind==expected(bug)), "missing expected failure "+expected(bug))
        }
      }
    }
  }
}
