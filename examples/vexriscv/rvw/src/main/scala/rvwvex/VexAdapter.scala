package rvwvex

import java.io.File
import spinal.core._
import spinal.core.sim._
import riscvsim._
import vexriscv.plugin.RvfiPort
import scala.collection.mutable

object VexAdapter extends CoreAdapter {
  override def freshInstancePerRun = true
  override def supportsSimThreads = true
  type Model = SimCompiled[VexTop]
  override def irqInputMask: BigInt = 0x888
  def core = "vexriscv"
  val configs = Seq("rv32im") ++ VexDebug.configs ++ VexCached.configs
  def xlen = 32
  def isa(config: String) = VexCached.isa(config)
  def sourceDir = new File(sys.env("VEXRISCV")).getCanonicalFile
  override def replayEnv = Seq("VEXRISCV" -> sourceDir.getPath) ++
    Seq("RVW_COSIM_DPI", "RVW_COSIM_FAULT_ORDER", "RVW_VEX_LOCK", "RVW_VEX_CSR_FULL", "RVW_VEX_CSR_CAPTURE").flatMap(
      name => sys.env.get(name).map(name -> _))
  override def supportsProbes = true
  override def supportsInstructionPort(config: String) = config == "rv32im"

  private def report(key: ModelKey, work: File): SpinalReport[VexTop] = {
    require(!key.konata, "VexRiscv adapter does not support Konata")
    spinalprobes.Probe.enabled(key.probes) {
      RiscvSimConfig.elaborate(key, work, VexTop.spinalConfig,
        sourceRoots = Seq(new File(sourceDir, "src/main/scala")))(new VexTop(VexDebug.configuration(key.config)))
    }
  }
  override def elaborate(key: ModelKey, work: File): Seq[File] =
    report(key, work).generatedSourcesPaths.toSeq.map(new File(_))
  def compile(key: ModelKey, work: File, cache: File): Model =
    RiscvSimConfig(key, work, cache, VexTop.spinalConfig).compile(report(key, work))
  override def generatedVerilog(model: Model): Seq[File] =
    Option(new File(model.compiledPath, "rtl").listFiles()).toSeq.flatten
      .filter(f => f.getName.endsWith(".v") || f.getName.endsWith(".sv"))

  def record(p: RvfiPort, cycle: Long, handler: Boolean): RvfiRecord =
    RvfiRecord(p.order.toBigInt, cycle, p.insn.toLong, p.trap.toBoolean, p.halt.toBoolean,
      handler, p.mode.toInt, p.ixl.toInt,
      p.rs1.addr.toInt, p.rs1.rdata.toBigInt, p.rs2.addr.toInt, p.rs2.rdata.toBigInt,
      p.rd.addr.toInt, p.rd.wdata.toBigInt, p.pc.rdata.toBigInt, p.pc.wdata.toBigInt,
      p.mem.addr.toBigInt, p.mem.rmask.toInt, p.mem.wmask.toInt,
      p.mem.rdata.toBigInt, p.mem.wdata.toBigInt, memFault = false)

  def run(model: Model, job: RunJob, ctx: RunContext): RunOutcome = {
    require(!job.rvfiCheck, "VexRiscv adapter has no riscv-formal monitor; use --rvfi-trace")
    require(ctx.elf.entry == 0x80000000L, "ELF entry must equal reset PC 0x80000000")
    val tohost = new ToHost(ToHost.find(ctx.elf).getOrElse(
      throw new IllegalArgumentException("ELF has no tohost symbol")), busBytes)
    job.socMap.foreach(m => require(m.regions.forall(r => !r.cacheable && r.base + r.size <= (BigInt(1) << 32)) && m.interrupts.isEmpty, "VexRiscv requires uncached 32-bit regions and device-owned routes"))
    val devices = job.socMap.map(new LiveDevices(_))
    devices.foreach(d => require((d.interruptMask & ~irqInputMask) == 0, "unsupported device interrupt pin"))
    val initialDeviceState = devices.map { d =>
      ElfFile.sha256(d.snapshot().render().getBytes("UTF-8"))
    }
    val memory = mutable.LongMap.empty[Int]
    def inRam(a: Long, n: Long, permission: Char = 'r'): Boolean = job.socMap match {
      case Some(m) => m.region(BigInt(a), BigInt(n), permission).exists(_.kind == "ram")
      case None => a >= 0x80000000L && n >= 0 && a + n <= 0x81000000L
    }
    ctx.elf.load { (addr, bytes) =>
      require(inRam(addr, bytes.length), "ELF segment outside mapped RAM")
      bytes.indices.foreach(i => memory(addr + i) = bytes(i) & 255)
    }
    def readWord(addr: Long): BigInt = (0 until 4).foldLeft(BigInt(0)) { (v, i) =>
      v | (BigInt(memory.getOrElse((addr & ~3L) + i, 0)) << (8 * i))
    }
    val capture = job.socMap.map(m => new MapCapture(m, job, ctx))
    val captureCsrs = !sys.env.get("RVW_VEX_CSR_CAPTURE").contains("0")
    var writer = Option.empty[RvfiTraceWriter]
    var traceEnded = false
    var probes = Option.empty[ProbeCollector]
    val bench = ctx.elf.symbol("bench_stats").map(new MemWords(_, 2, busBytes))
    val marker = ctx.elf.symbol("setStats")
    var markers = 0
    var roiActive = false
    var roiLoads, roiStores, roiBranches, roiRetired = 0L
    var waveStart = -1L
    var retired = 0L
    var traps = 0L
    var nextOrder = BigInt(0)
    var handler = false
    val (status, code, message, cycles) = try {
      val result = SimSession.runCtl(model, job, ctx) { (dut, ctl) =>
        val cd = dut.clockDomain
        dut.lockstepDpi.foreach(_.initialize())
        val header = if (captureCsrs) ujson.Obj.from(ctx.rvfiHeader.value.toSeq :+
          ("csr_snapshot" -> ujson.Arr.from(dut.traps.snapshots.keys.toSeq.sorted.map(a => Hex(BigInt(a))))))
          else ctx.rvfiHeader
        writer = if (job.rvfiTrace) Some(new RvfiTraceWriter(
          new File(job.out, "rvfi.jsonl"), header,
          observe = dut.lockstepDpi.filter(_ => sys.env.contains("RVW_COSIM_PORT"))
            .map(m => (line: String) => m.observe(line)))) else None

        probes = ProbeCollector.open(spinalprobes.Probe.of(dut), job, ctx.rvfiHeader)
        dut.csr.timerInterrupt #= false
        dut.csr.softwareInterrupt #= false
        dut.csr.externalInterrupt #= false
        if (dut.csr.externalInterruptS != null) dut.csr.externalInterruptS #= false
        val cached = dut.icached.nonEmpty
        require(!cached || job.socMap.isEmpty, "cached VexRiscv configs support bare RAM only (no --soc-map)")
        if (!cached) {
          if (job.instructionPort.isEmpty) dut.ibus.cmd.ready #= false
          if (job.instructionPort.isEmpty) dut.ibus.rsp.valid #= false
          if (job.instructionPort.isEmpty) dut.ibus.rsp.error #= false
          if (job.instructionPort.isEmpty) dut.ibus.rsp.inst #= 0
          dut.dbus.cmd.ready #= false
          dut.dbus.rsp.ready #= false
          dut.dbus.rsp.error #= false
          dut.dbus.rsp.data #= 0
        }
        cd.forkStimulus(10)
        // One outstanding response per bus. Fixed latency 0 has no extra wait.
        // Absent --mem-latency uses the recorded simulation seed.
        val random = new scala.util.Random(job.seed)
        def delay(): Long = job.memLatency.map(_.toLong).getOrElse(random.nextInt(4).toLong) + 1L
        if (cached) CachedBuses.drive(dut, cd, delay, readWord, inRam(_, _, 'r'), memory)
        else {
          if (job.instructionPort.isEmpty) fork {
            var pending = Option.empty[(Long, BigInt, Boolean)]
            var cycle = 0L
            while (true) {
              cd.waitFallingEdge()
              val respond = pending.exists(_._1 <= cycle)
              dut.ibus.cmd.ready #= pending.isEmpty
              dut.ibus.rsp.valid #= respond
              pending.foreach { case (_, data, error) => dut.ibus.rsp.inst #= data; dut.ibus.rsp.error #= error }
              cd.waitSampling()
              cycle += 1
              if (respond) pending = None
              if (dut.ibus.cmd.valid.toBoolean && dut.ibus.cmd.ready.toBoolean) {
                val addr = dut.ibus.cmd.pc.toLong
                val selected = job.socMap.flatMap(_.region(BigInt(addr & ~3L), 4, 'x'))
                capture.foreach(_.request(cycle, "ibus", BigInt(addr & ~3L), 4, false, selected))
                pending = Some((cycle + delay(), readWord(addr), !inRam(addr & ~3L, 4, 'x')))
              }
            }
          }
          fork {
            var pending = Option.empty[(Long, BigInt, Boolean)]
            var cycle = 0L
            while (true) {
              cd.waitFallingEdge()
              val respond = pending.exists(_._1 <= cycle)
              dut.dbus.cmd.ready #= pending.isEmpty
              dut.dbus.rsp.ready #= respond
              pending.foreach { case (_, data, error) => dut.dbus.rsp.data #= data; dut.dbus.rsp.error #= error }
              cd.waitSampling()
              cycle += 1
              if (respond) pending = None
              if (dut.dbus.cmd.valid.toBoolean && dut.dbus.cmd.ready.toBoolean) {
                val cmd = dut.dbus.cmd
                val byteAddress = cmd.address.toLong
                val addr = byteAddress & ~3L
                val bytes = 1 << cmd.size.toInt
                val lane = (byteAddress & 3).toInt
                val permission = if (cmd.wr.toBoolean) 'w' else 'r'
                val selected = job.socMap.flatMap(_.region(BigInt(byteAddress), bytes, permission))
                capture.foreach(_.request(cycle, "dbus", BigInt(byteAddress), bytes, cmd.wr.toBoolean, selected))
                val device = devices.filter(_.contains(byteAddress, bytes))
                val valid = inRam(addr, 4, permission)
                if (cmd.wr.toBoolean) {
                  val data = cmd.data.toBigInt
                  device match {
                    case Some(d) => d.write(byteAddress, bytes, (data >> (8 * lane)) & ((BigInt(1) << (8 * bytes)) - 1))
                    case None =>
                      require(valid, f"store outside RAM at 0x$addr%x")
                      for (i <- 0 until 4 if (cmd.mask.toInt & (1 << i)) != 0)
                        memory(addr + i) = ((data >> (8 * i)) & 255).toInt
                  }
                } else pending = Some((cycle + delay(), device.map(_.read(byteAddress, bytes) << (8 * lane)).getOrElse(readWord(addr)), !valid && device.isEmpty))
              }
            }
          }
        }
        var irqLevels = BigInt(-1)
        fork {
          while (true) {
          cd.waitSampling()
          ctl.tick()
          probes.foreach(_.sample(ctl.cycle))
          val deviceLevels = devices.map(_.tick(ctl.cycle)).getOrElse(BigInt(0))
          val levels = job.irqSchedule.map(_.levelsAt(ctl.cycle)).getOrElse(deviceLevels)
          dut.csr.timerInterrupt #= levels.testBit(7)
          dut.csr.softwareInterrupt #= levels.testBit(3)
          dut.csr.externalInterrupt #= levels.testBit(11)
          if (dut.csr.externalInterruptS != null) dut.csr.externalInterruptS #= levels.testBit(9)
          // Snapshot every signal before the DPI transport can yield simulation time.
          val trap = if (dut.traps.valid.toBoolean)
            Some((dut.traps.cause.toBigInt, dut.traps.tval.toBigInt)) else None
          if (trap.nonEmpty) handler = true
          val sample = if (dut.rvfi.valid.toBoolean)
            Some(record(dut.rvfi, ctl.cycle, handler)) else None
          // RVFI describes the firing edge. CSR storage must include that edge's effects.
          if (sample.nonEmpty) sleep(1)
          val csrState = if (sample.nonEmpty && captureCsrs)
            dut.traps.snapshots.map { case (address, value) => address -> value.toBigInt }
            else Map.empty[Int, BigInt]
          if (levels != irqLevels) { writer.foreach(_.irq(ctl.cycle, levels)); irqLevels = levels }
          trap.foreach { case (cause, tval) =>
            traps += 1
            writer.foreach(_.trap(ctl.cycle, cause, tval, cause.testBit(31)))
          }
          sample.foreach { retirement =>
            val sampled = retirement.copy(csrState = csrState)
            val r = if (sys.env.get("RVW_COSIM_FAULT_ORDER").contains(sampled.order.toString)) {
              require(sampled.rd != 0, "fault target must write a GPR")
              sampled.copy(rdWdata = sampled.rdWdata ^ 1)
            } else sampled
            handler = false
            require(r.order == nextOrder, s"RVFI order ${r.order}, expected $nextOrder")
            nextOrder += 1
            retired += 1
            // Match gem5's retired-PC window: exclude entry and include exit.
            if (roiActive && !r.trap) {
              roiRetired += 1
              (r.insn.toInt & 0x7f) match {
                case 0x03 => roiLoads += 1
                case 0x23 => roiStores += 1
                case 0x63 | 0x67 | 0x6f => roiBranches += 1
                case _ =>
              }
            }
            if (!r.trap && marker.contains(r.pc.toLong)) {
              markers += 1
              require(markers <= 2, "more than two ROI markers")
              roiActive = markers == 1
            }
            writer.foreach(_.write(r))
            if (r.memWmask != 0) {
              val lane = Integer.numberOfTrailingZeros(r.memWmask)
              val count = Integer.bitCount(r.memWmask)
              require(Set(1, 2, 4)(count), "unsupported RVFI store mask")
              bench.foreach(_.onStore(r.memAddr + lane, Integer.numberOfTrailingZeros(count), r.memWdata))
              tohost.onStore(r.memAddr + lane, Integer.numberOfTrailingZeros(count), r.memWdata) match {
                case Some(ToHost.Pass) =>
                  writer.foreach(_.end(ctl.cycle, "pass")); traceEnded = true
                  ctl.finish(Status.Pass)
                case Some(f: ToHost.Fail) =>
                  writer.foreach(_.end(ctl.cycle, "fail")); traceEnded = true
                  ctl.finish(Status.Fail, Some(f.code), Some(s"tohost = ${Hex(f.raw)}"))
                case None =>
              }
            }
          }
        }
        }
        cd.waitSamplingWhere(false)
      }
      if (!traceEnded && !sys.env.get("RVW_COSIM_DPI").contains("1"))
        writer.foreach(_.end(result._4, result._1.name))
      probes.foreach(_.close(result._4))
      waveStart = result._5.timeOfCycle1
      (result._1, result._2, result._3, result._4)
    } finally { writer.foreach(_.close()); capture.foreach(_.close()); probes.foreach(_.abandon()) }
    val metrics = ujson.Obj()
    bench.filter(_.complete).filter(_ => markers == 2).foreach { b =>
      metrics("roi_cycles") = RvwJson.num(b.words(0).toLong)
      metrics("roi_instret") = RvwJson.num(b.words(1).toLong)
      metrics("roi_retired") = RvwJson.num(roiRetired)
      metrics("roi_loads") = RvwJson.num(roiLoads)
      metrics("roi_stores") = RvwJson.num(roiStores)
      metrics("roi_branches") = RvwJson.num(roiBranches)
    }
    RunOutcome(status, cycles, retired, code, message,
      ujson.Obj("wave_time_per_cycle" -> 10, "wave_time_of_cycle_1" -> RvwJson.num(waveStart),
        "wave_window" -> ujson.Obj("from" -> job.waveFrom.map(v => ujson.Num(v.toDouble)).getOrElse(ujson.Null), "to" -> job.waveTo.map(v => ujson.Num(v.toDouble)).getOrElse(ujson.Null)),
        "traps" -> RvwJson.num(traps), "rvfi_records" -> RvwJson.num(retired), "tohost" -> Hex(tohost.value),
        "device_reset" -> "fresh-instance-per-request",
        "initial_device_state_sha256" -> initialDeviceState.map(ujson.Str).getOrElse(ujson.Null),
        "device_output" -> devices.map(_.outputs).getOrElse(ujson.Obj()), "rvfi_monitor" -> false, "memory_bytes" -> job.socMap.map(m => ujson.Str(m.regions.map(_.size).sum.toString)).getOrElse(ujson.Num(16777216)), "roi_markers" -> markers), metrics)
  }
}

object Main {
  def main(args: Array[String]): Unit = new Driver(VexAdapter).main(args)
}
