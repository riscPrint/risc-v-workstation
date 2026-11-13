package rvwvex

import java.io.File
import spinal.core._
import spinal.core.sim._
import spinalchecks._
import riscvsim.{ElfFile, ToHost}
import vexriscv.VexRiscv
import vexriscv.plugin._
import scala.collection.mutable

/** Bounded example execution. Observation faults do not modify the core. */
object CsrChecksRuntime {
  def main(args: Array[String]): Unit = {
    require(args.length >= 4, "usage: CsrChecksRuntime model.json out-dir none|csr|hpm|hpm_read program.elf ...")
    val model = CsrChecksPlugin.loadModel(args(0))
    val out = new File(args(1)).getCanonicalFile
    require(Set("none", "csr", "hpm", "hpm_read")(args(2)))
    val fault = args(2)
    val allChecks = sys.env.get("RVW_CHECKS_ISA").contains("1")
    require(!allChecks || fault == "none", "ISA qualification requires clean observations")
    val core = VexTop.configuration()
    core.plugins += new CsrChecksPlugin(model, observationFault = fault == "csr")
    core.plugins += new HpmChecksPlugin(observationFault = fault == "hpm", readObservationFault = fault == "hpm_read")
    val (config, result) = SpinalChecks.install(VexTop.spinalConfig.copy(targetDirectory = new File(out, "rtl").getPath,
      debugComponents = scala.collection.mutable.HashSet[Class[_]](classOf[VexRiscv])),
      ChecksConfig(streamCancellations = if (allChecks) CheckSemantics.cancellations else Nil,
        mode = if (allChecks) Mode.Both else Mode.Monitor,
        enable = if (allChecks) Seq("*") else Seq("csr.*", "hpm.*"), reportPath = new File(out, "checks.json").getPath))
    if (sys.env.get("RVW_CHECKS_FORMAL").contains("1")) {
      config.includeFormal.generateVerilog(new VexRiscv(core))
      return
    }
    val simConfig = SimConfig.withConfig(config).workspacePath(out.getPath).workspaceName("native").withVerilator.addSimulatorFlag("--assert")
    if (sys.env.get("RVW_CHECKS_WAVE").contains("1")) simConfig.withWave
    val compiled = simConfig.compile(new VexRiscv(core))
    require(result.inserted.count(_.kind.startsWith("csr.")) == 3 && result.inserted.count(_.kind == "hpm.count") == 2 &&
      result.inserted.count(_.kind == "hpm.read") == 4)
    var campaignFailed = false
    var scratchInstructions = 0L
    var counterInstructions = 0L
    var counterReads = 0L
    for ((path, index) <- args.drop(3).zipWithIndex) {
      val elf = ElfFile(path)
      require(elf.xlen == 32 && elf.entry == 0x80000000L)
      val memory = mutable.LongMap.empty[Int]
      elf.load { (base, bytes) => bytes.indices.foreach(i => memory(base + i) = bytes(i) & 255) }
      val host = new ToHost(ToHost.find(elf).getOrElse(throw new IllegalArgumentException("ELF needs tohost")), 4)
      def word(address: Long): BigInt = (0 until 4).foldLeft(BigInt(0))((v, i) =>
        v | (BigInt(memory.getOrElse((address & ~3L) + i, 0)) << (8 * i)))
      val scratchBefore = scratchInstructions
      val readsBefore = counterReads
      compiled.doSim(name = s"program_$index") { dut =>
        val cd = dut.clockDomain
        val ibus = dut.config.get(classOf[IBusSimplePlugin]).iBus
        val dbus = dut.config.get(classOf[DBusSimplePlugin]).dBus
        val csr = dut.config.get(classOf[CsrPlugin])
        val rvfi = dut.config.get(classOf[FormalPlugin]).rvfi
        csr.timerInterrupt #= false; csr.softwareInterrupt #= false; csr.externalInterrupt #= false
        if (csr.externalInterruptS != null) csr.externalInterruptS #= false
        ibus.cmd.ready #= false; ibus.rsp.valid #= false; ibus.rsp.inst #= 0; ibus.rsp.error #= false
        dbus.cmd.ready #= false; dbus.rsp.ready #= false; dbus.rsp.data #= 0; dbus.rsp.error #= false
        cd.forkStimulus(10); cd.waitSampling(8)
        var instruction = Option.empty[BigInt]
        var data = Option.empty[BigInt]
        var done = Option.empty[Int]
        var cycle = 0
        var retired = 0L
        while (cycle < (if (allChecks) 200000 else 20000) && done.forall(cycle < _ + 20)) {
          cd.waitFallingEdge()
          ibus.cmd.ready #= instruction.isEmpty
          ibus.rsp.valid #= instruction.nonEmpty
          instruction.foreach(v => ibus.rsp.inst #= v)
          dbus.cmd.ready #= data.isEmpty
          dbus.rsp.ready #= data.nonEmpty
          data.foreach(v => dbus.rsp.data #= v)
          cd.waitSampling()
          cycle += 1
          instruction = None; data = None
          if (ibus.cmd.valid.toBoolean && ibus.cmd.ready.toBoolean) instruction = Some(word(ibus.cmd.pc.toLong))
          if (dbus.cmd.valid.toBoolean && dbus.cmd.ready.toBoolean) {
            val cmd = dbus.cmd
            val address = cmd.address.toLong
            require(address >= 0x80000000L && address < 0x81000000L, "data access outside example RAM")
            if (cmd.wr.toBoolean) {
              val value = cmd.data.toBigInt
              for (lane <- 0 until 4 if (cmd.mask.toInt & (1 << lane)) != 0)
                memory((address & ~3L) + lane) = ((value >> (lane * 8)) & 255).toInt
              if (host.onStore(BigInt(address), cmd.size.toInt, value).nonEmpty && done.isEmpty) done = Some(cycle)
            } else data = Some(word(address))
          }
          if (rvfi.valid.toBoolean) {
            retired += 1
            val insn = rvfi.insn.toLong
            if ((insn & 0x7f) == 0x73) {
              val address = (insn >> 20) & 0xfff
              if (address == 0x340) scratchInstructions += 1
              if (Set(0xb00L, 0xb80L, 0xb02L, 0xb82L)(address)) counterInstructions += 1
              if (Set(0xb00L, 0xb80L, 0xb02L, 0xb82L, 0xc00L, 0xc80L, 0xc02L, 0xc82L)(address) &&
                  ((insn >> 7) & 31) != 0) counterReads += 1
            }
          }
        }
        val fs = ChecksSim.firings(dut)
        ChecksSim.writeRunReport(dut, new File(out, s"run_$index.json").getPath, Seq(
          "status" -> Json.Str(if (done.nonEmpty && host.value == 1) "pass" else "fail"),
          "elf" -> Json.Str(elf.file.getCanonicalPath), "elf_sha256" -> Json.Str(elf.sha256),
          "program_status" -> Json.Str(if (done.isEmpty) "timeout" else if (host.value == 1) "pass" else "fail"),
          "observation_fault" -> Json.Str(fault), "cycles" -> Json.Num(BigDecimal(cycle)), "retired" -> Json.Num(BigDecimal(retired))))
        if (allChecks) {
          import Json._
          val kinds = result.records.toSeq.map(_.kind).distinct.sorted.map { kind =>
            val records = result.records.filter(_.kind == kind)
            kind -> obj("generated" -> records.size, "bound" -> records.count(_.inserted),
              "fired" -> fs.count(_.check.kind == kind),
              "firing_count" -> fs.filter(_.check.kind == kind).map(_.count.toLong).sum,
              "unbound" -> records.count(r => !r.inserted))
          }
          val status = if (done.isEmpty) "timeout" else if (host.value != 1 || fs.nonEmpty) "fail" else "pass"
          campaignFailed ||= status != "pass"
          ChecksSim.writeFile(new File(out, s"c1_$index.json").getPath, Json.write(obj(
            "schema" -> "rvw.run/1", "core" -> "vexriscv", "config" -> "rv32im-generated-checks",
            "status" -> status, "elf" -> elf.file.getCanonicalPath, "elf_sha256" -> elf.sha256,
            "cycles" -> cycle, "instret" -> retired, "max_cycles" -> 200000,
            "artifacts" -> obj("checks" -> s"run_$index.json", "inventory" -> "checks.json"),
            "details" -> obj("checks" -> obj(kinds: _*), "assertions_compiled" -> true,
              "program_status" -> (if (done.isEmpty) "timeout" else if (host.value == 1) "pass" else "fail")),
            "inconclusive" -> "Bounded example run. Input closure and whole-core qualification are not certified."
          )) + "\n")
        }
        require(allChecks || (done.nonEmpty && host.value == 1), s"program failed or timed out: tohost=${host.value}")
        if (fault == "none" && !allChecks) require(fs.isEmpty, fs.map(_.check.id).mkString(", "))
        if (fault == "hpm") require(fs.exists(_.check.kind == "hpm.count"), "HPM observation fault was not detected")
        if (fault == "hpm_read" && counterReads > readsBefore)
          require(fs.exists(_.check.kind == "hpm.read"), "HPM read observation fault was not detected")
        // An absent-CSR program has no mscratch write. Its initial state stays unknown.
        if (fault == "csr" && scratchInstructions > scratchBefore)
          require(fs.exists(_.check.kind == "csr.state"), "CSR observation fault was not detected")
      }
    }
    require(allChecks || (scratchInstructions >= 3 && counterInstructions >= 4 && counterReads >= 8), "programs did not exercise scratch and counter CSRs")
    require(!campaignFailed, "ISA campaign has failed programs or generated checks; see C1 reports")
    println(s"CSR_CHECKS_RUNTIME_OK fault=$fault scratch_instructions=$scratchInstructions counter_instructions=$counterInstructions counter_reads=$counterReads")
  }
}
