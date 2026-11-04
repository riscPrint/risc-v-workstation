package riscvsim.boom

import java.io.File

import spinal.core._
import spinal.core.sim._
import spinal.lib.sim.SparseMemory

import boom.common.{BoomConfigs, BoomTileParams, SpinalBoomConfig}
import boom.sim.{BoomMemoryAgent, BoomSim, Disasm, KonataTracer}
import boom.system.BoomSimTop

import riscvsim._

/**
 * BOOM's run-contract adapter. Builds BoomSimTop (from the spinal-boom checkout in
 * SPINAL_BOOM) and runs bare-metal ELFs that report through `tohost`.
 *
 * The run loop follows boom.sim.BoomSim.run (same memory model, CLINT/interrupt
 * generator, tohost from the D$ store acks) and adds: exact-cycle stop, RVFI capture
 * from `io.rvfi` (one channel per retire slot, ordered by `order`), trap events from
 * `io.trace`, the riscv-formal monitor's error code, the wave window, and Konata.
 *
 * ECALL and EBREAK are plain retirements in BOOM's `io.trace` (as in rocket), with no cause.
 * Their trap event reads the cause and tval BOOM actually wrote: RVFI models make the CSR
 * file's `reg_mcause`/`reg_mtval`/`reg_scause`/`reg_stval` public (from here, without changing
 * BOOM's sources). BOOM's CSR file takes these traps when the instruction executes, before it
 * commits, so the registers hold the new values when the trace reports the retirement. The
 * cause registers have no write strobe, so the adapter also requires `mepc` (or `sepc`) to hold
 * the ECALL/EBREAK's PC; otherwise the cause could be stale and the run ends with `assert`.
 *
 * The trace also carries C2 `irq` events: the levels of the interrupt inputs (MSIP, MTIP, SEIP,
 * MEIP) the harness drives, at the first sampled cycle and at every change, so `rvw cosim` can
 * accept an input bit read from `mip` only when the input was high.
 */
object BoomAdapter extends CoreAdapter {
  override def freshInstancePerRun = true
  type Model = SimCompiled[BoomSimTop]

  val boomDir: File = new File(sys.props.getOrElse("riscvsim.boom.dir",
    sys.env.getOrElse("SPINAL_BOOM", "."))).getCanonicalFile

  override def irqInputMask: BigInt = 0xA88
  def core = "boom"
  val configs = Seq("small", "medium", "large", "mega", "giga")
  def xlen = 64
  def isa(config: String) = "rv64imafdc_zicsr_zifencei_zba_zbb_zbs"
  def sourceDir: File = boomDir
  override def replayEnv: Seq[(String, String)] = Seq("SPINAL_BOOM" -> boomDir.getPath)

  def tile(config: String): BoomTileParams = config match {
    case "small" => BoomConfigs.small()
    case "medium" => BoomConfigs.medium()
    case "large" => BoomConfigs.large()
    case "mega" => BoomConfigs.mega()
    case "giga" => BoomConfigs.giga()
  }

  private def report(key: ModelKey, work: File): SpinalReport[BoomSimTop] = {
    implicit val p = BoomSim.params(tile(key.config), key.rvfi)
    val formal = new File(boomDir, "formal")
    RiscvSimConfig.elaborate(key, work, SpinalBoomConfig(),
      Seq("src/main/scala", "src/test/scala").map(new File(sourceDir, _))) {
      val top = new BoomSimTop(BoomSim.resetVector, if (key.rvfi) Some(formal.getPath) else None, key.konata)
      if (key.rvfi) {
        trapCsrs(top).productIterator.foreach { case d: Data => d.simPublic(); case _ => }
        trapEpcs(top).productIterator.foreach { case d: Data => d.simPublic(); case _ => }
      }
      top
    }
  }

  override def elaborate(key: ModelKey, work: File): Seq[File] =
    report(key, work).generatedSourcesPaths.toSeq.map(new File(_))

  def compile(key: ModelKey, work: File, cache: File): Model =
    RiscvSimConfig(key, work, cache, SpinalBoomConfig()).compile(report(key, work))

  /** The CSR file registers an ECALL/EBREAK trap writes: (mcause, mtval, scause, stval). */
  def trapCsrs(top: BoomSimTop) = {
    val csr = top.tile.core.csr
    (csr.reg_mcause, csr.reg_mtval, csr.reg_scause, csr.reg_stval)
  }

  /** The CSR file's exception PCs: (mepc, sepc). */
  def trapEpcs(top: BoomSimTop) = {
    val csr = top.tile.core.csr
    (csr.reg_mepc, csr.reg_sepc)
  }

  /** C2 `irq` levels: each input in its `mip` bit position. */
  def irqLevels(msip: Boolean, mtip: Boolean, seip: Boolean, meip: Boolean): BigInt =
    BigInt((if (msip) 1 << 3 else 0) | (if (mtip) 1 << 7 else 0) | (if (seip) 1 << 9 else 0) | (if (meip) 1 << 11 else 0))

  override def generatedVerilog(m: Model): Seq[File] =
    Option(m.compiledPath).toSeq.flatMap(d => Option(new File(d, "rtl").listFiles()).toSeq.flatten)
      .filter(f => f.getName.endsWith(".v") || f.getName.endsWith(".sv"))

  /** ECALL, EBREAK or C.EBREAK: they trap, but BOOM's trace reports them as plain retirements. */
  def isEnvTrap(insn: Long): Boolean =
    insn == 0x00000073L || insn == 0x00100073L || (insn & 0xffffL) == 0x9002L && (insn & 3) != 3

  def run(compiled: Model, job: RunJob, ctx: RunContext): RunOutcome = {
    val elf = ctx.elf
    val tohostAddr = ToHost.find(elf).getOrElse(throw new IllegalArgumentException(s"${job.elf} has no tohost symbol"))
    val tohost = new ToHost(tohostAddr, busBytes)
    // riscv-tests benchmarks store ROI cycles and instret here (see BenchmarksSpec)
    val benchStats = elf.symbol("bench_stats").map(new MemWords(_, 2, busBytes))
    val rvfi = if (job.rvfiTrace) Some(new RvfiTraceWriter(new File(job.out, "rvfi.jsonl"), ctx.rvfiHeader)) else None
    val konataFile = new File(job.out, "konata.log")
    var tracer: Option[KonataTracer] = None
    var retired = 0L
    var traps = 0L
    var rvfiCode = 0

    val capture = job.socMap.map(m => new MapCapture(m, job, ctx, "map_monitor"))
    val (status, failCode, message, cycles, simCtl) = try SimSession.runCtl(compiled, job, ctx) { (dut, ctl) =>
      require(!job.irqSchedule.exists(_.mask.testBit(9)) || dut.io.interrupts.seip != null,
        "this configuration has no SEIP input")
      val cd = dut.clockDomain
      cd.forkStimulus(10)
      dut.io.interrupts.flatten.foreach { case b: Bool => b #= false; case _ => }

      val mem = SparseMemory(seed = 0)
      elf.load { (a, d) =>
        job.socMap.foreach(m => require(m.region(BigInt(a), BigInt(d.length), 'r').exists(_.kind == "ram"), "ELF outside mapped RAM"))
        mem.write(a, d)
      }
      new BoomMemoryAgent(dut.io.mem, cd, mem, job.memLatency)
      val msip = job.socMap.map(_.register("clint", "msip")).getOrElse(BoomSim.Platform.msip)
      val mtimecmp = job.socMap.map(_.register("clint", "mtimecmp")).getOrElse(BoomSim.Platform.mtimecmp)
      val mtime = job.socMap.map(_.register("clint", "mtime")).getOrElse(BoomSim.Platform.mtime)
      val intGen = job.socMap.map(_.register("intgen", "meip")).getOrElse(BoomSim.Platform.intGen)
      val seipAddr = job.socMap.map(_.register("intgen", "seip")).getOrElse(BoomSim.Platform.intGen + 4)
      job.socMap.foreach { m =>
        require(m.regions.forall(r => if (r.kind == "ram")
          r.permissions == "rwx" && r.cacheable && r.base >= BigInt("80000000", 16) && r.base + r.size <= BigInt("90000000", 16)
          else r.permissions == "rw" && !r.cacheable), "map attributes differ from fixed RTL memory attributes")
        val wiring = m.interrupts.map(i => (i("region").str, i("register").str, SimMap.number(i("cause")).toInt))
        require(wiring.size == 4 && wiring.toSet == Set(("clint", "msip", 3), ("clint", "mtimecmp", 7),
          ("intgen", "meip", 11), ("intgen", "seip", 9)), "unsupported interrupt wiring")
        for ((region, specs) <- Seq("clint" -> Map("msip" -> 32, "mtimecmp" -> 64, "mtime" -> 64),
                                  "intgen" -> Map("meip" -> 32, "seip" -> 32))) {
          val regs = m.regions.find(_.name == region).get.registers
          require(regs.map(g => g("name").str -> SimMap.number(g("width")).toInt).toMap == specs,
            "unsupported device register layout")
        }
        require(m.regions.filter(_.kind == "mmio").map(_.name).toSet == Set("clint", "intgen"), "unsupported MMIO device")
        require(Seq(msip, mtimecmp, mtime, intGen, seipAddr).forall(a => (a >= 0x02000000L && a < 0x02010000L) || (a >= 0x0c000000L && a < 0x0c001000L)), "device placement must remain in RTL device windows")
      }
      mem.write(msip, job.socMap.map(_.reset("clint", "msip").toInt).getOrElse(0))
      mem.write(mtimecmp, job.socMap.map(_.reset("clint", "mtimecmp")).getOrElse(-1L))
      mem.write(intGen, job.socMap.map(_.reset("intgen", "meip").toInt).getOrElse(0))
      mem.write(seipAddr, job.socMap.map(_.reset("intgen", "seip").toInt).getOrElse(0))
      def readLong(a: Long): Long = (0 until 8).map(i => (mem.read(a + i).toLong & 0xff) << (8 * i)).reduce(_ | _)
      var mtimeValue = job.socMap.map(_.reset("clint", "mtime")).getOrElse(0L)
      mem.write(mtime, mtimeValue)

      tracer = if (job.konata) {
        require(dut.konata != null, "the model was built without Konata probes")
        Some(new KonataTracer(dut.konata, konataFile, elf.withSnapshotFile(job.out)(f => Disasm(f.getPath))))
      } else None
      val probe = rvfi.map { _ =>
        require(dut.io.rvfi != null, "the model was built without RVFI")
        new RvfiProbe(dut.io.rvfi.toSeq)
      }
      val trace = dut.io.trace.insns.toSeq
      val tvalBits = trace.head.tval.getBitsWidth
      // BOOM's trace drives tval one cycle after exception/cause (csr.io.tval is already a
      // cycle late, and the trace registers it again), so a trap event waits a cycle for it.
      def sext(v: BigInt, bits: Int = tvalBits): BigInt = if (v.testBit(bits - 1)) (v - (BigInt(1) << bits)) & ((BigInt(1) << 64) - 1) else v
      val csrs = rvfi.map(_ => trapCsrs(dut))
      val epcs = rvfi.map(_ => trapEpcs(dut))
      var levels = BigInt(-1)

      cd.onSamplings {
        ctl.tick()
        if (dut.io.mem.a.valid.toBoolean && dut.io.mem.a.ready.toBoolean) {
          val a = dut.io.mem.a.payload
          val address = a.address.toBigInt
          val size = BigInt(1) << a.size.toInt
          val write = a.opcode.toInt == 0 || a.opcode.toInt == 1
          val selected = job.socMap.flatMap(_.region(address, size, if (write) 'w' else 'r'))
          capture.foreach(_.request(ctl.cycle, "tilelink_a", address, size, write, selected))
          job.socMap.foreach(_ => require(selected.isDefined, "TileLink request outside mapped region"))
        }
        tracer.foreach(_.sample())
        // mtime counts cycles unless software wrote it
        val stored = readLong(mtime)
        mtimeValue = (if (stored != mtimeValue) stored else mtimeValue) + 1
        mem.write(mtime, mtimeValue)
        val scheduled = job.irqSchedule.map(_.levelsAt(ctl.cycle))
        val mtipLevel = scheduled.map(_.testBit(7)).getOrElse(java.lang.Long.compareUnsigned(mtimeValue, readLong(mtimecmp)) >= 0)
        val msipLevel = scheduled.map(_.testBit(3)).getOrElse((mem.readInt(msip) & 1) != 0)
        val meipLevel = scheduled.map(_.testBit(11)).getOrElse((mem.readInt(intGen) & 1) != 0)
        val seipLevel = scheduled.map(_.testBit(9)).getOrElse(dut.io.interrupts.seip != null && (mem.readInt(seipAddr) & 1) != 0)
        dut.io.interrupts.mtip #= mtipLevel
        dut.io.interrupts.msip #= msipLevel
        dut.io.interrupts.meip #= meipLevel
        if (dut.io.interrupts.seip != null) dut.io.interrupts.seip #= seipLevel

        // A trap seen last cycle is written first (its tval arrives now), then this cycle's records.
        for (w <- rvfi; p <- probe) w.cycle(p.sample(ctl.cycle), sext(trace.head.tval.toBigInt))
        for (t <- trace) {
          if (t.valid.toBoolean) {
            // BOOM's commit trace (like rocket's) reports ECALL/EBREAK as plain retirements; they
            // trap, so they are not counted in instret (as in RVFI) and get a trap event here,
            // with the cause and tval BOOM wrote to the CSR file of the handler's mode.
            if (isEnvTrap(t.insn.toLong)) {
              traps += 1
              for (w <- rvfi; (mcause, mtval, scause, stval) <- csrs; (mepc, sepc) <- epcs) {
                val toS = (t.priv.toInt & 3) == 1
                val (cause, tval, epc) = if (toS) (scause, stval, sepc) else (mcause, mtval, mepc)
                // The cause registers have no write strobe: xepc must hold this instruction's PC,
                // or the cause read here could be left from an earlier trap.
                val pc = t.iaddr.toBigInt & ((BigInt(1) << 64) - 1)
                val epcValue = sext(epc.toBigInt, epc.getBitsWidth)
                if (epcValue != pc)
                  ctl.finish(Status.Assert, message = Some(f"ECALL/EBREAK at pc 0x${pc}%x: ${if (toS) "sepc" else "mepc"} " +
                    f"is 0x${epcValue}%x, so its cause and tval were not written for it"))
                w.trap(ctl.cycle, cause.toBigInt, sext(tval.toBigInt, tval.getBitsWidth), intr = false)
              }
            } else retired += 1
          }
          if (t.exception.toBoolean || t.interrupt.toBoolean) {
            traps += 1
            rvfi.foreach(_.trapNextCycle(ctl.cycle, t.cause.toBigInt, t.interrupt.toBoolean))
          }
        }
        // Input levels after this cycle's records: the core sees them from the next edge.
        for (w <- rvfi) {
          val now = irqLevels(msipLevel, mtipLevel, seipLevel, meipLevel)
          if (now != levels) { w.irq(ctl.cycle, now); levels = now }
        }
        for (e <- dut.rvfiErr) if (e.toInt != 0) {
          rvfiCode = e.toInt
          val text = NativeOutput.await(ctx.outputMark, 500)(_.text.startsWith("Error message:"))
            .map(_.text.stripPrefix("Error message:").trim)
          ctl.finish(Status.RvfiError, message = Some(s"riscv-formal RVFI monitor error $rvfiCode" + text.map(t => s": $t").getOrElse("")))
        }
        if (dut.io.tohost.valid.toBoolean) {
          val p = dut.io.tohost.payload
          for (b <- benchStats) b.onStore(p.addr.toBigInt, p.size.toInt, p.data.toBigInt)
          tohost.onStore(p.addr.toBigInt, p.size.toInt, p.data.toBigInt) match {
            case Some(ToHost.Pass) => ctl.finish(Status.Pass)
            case Some(f: ToHost.Fail) => ctl.finish(Status.Fail, failCode = Some(f.code),
              message = Some(if (f.odd) s"tohost = 0x${f.raw.toString(16)} (test ${f.code} failed)"
                             else s"tohost = 0x${f.raw.toString(16)} (even value: a syscall request, not supported)"))
            case None =>
          }
        }
      }
      while (true) cd.waitSampling(100000)
    } finally {
      for (t <- tracer) t.close()
      capture.foreach(_.close())
    }

    for (w <- rvfi) { w.end(cycles, status.name); w.close() } // a trap still waiting for its tval gets 0
    val details = ujson.Obj("traps" -> RvwJson.num(traps), "tohost" -> Hex(tohost.value),
      "mem_timing" -> ujson.Str(job.memLatency.map(l => s"fixed $l").getOrElse("random")),
      "wave_time_per_cycle" -> 10, "wave_time_of_cycle_1" -> RvwJson.num(simCtl.timeOfCycle1))
    for (w <- rvfi) {
      details("rvfi_records") = RvwJson.num(w.records)
      details("rvfi_trap_records") = RvwJson.num(w.trapRecords)
      details("rvfi_order_gaps") = RvwJson.num(w.orderGaps)
    }
    if (rvfiCode != 0) details("rvfi_errcode") = rvfiCode
    for (t <- tracer) details("konata_desyncs") = RvwJson.num(t.desyncs)
    if (job.wave) details("wave_window") = ujson.Obj("from" -> job.waveFrom.map(v => ujson.Num(v.toDouble)).getOrElse(ujson.Null),
      "to" -> job.waveTo.map(v => ujson.Num(v.toDouble)).getOrElse(ujson.Null))
    val metrics = ujson.Obj()
    for (b <- benchStats) {
      if (b.complete) {
        metrics("roi_cycles") = b.words(0).toDouble
        metrics("roi_instret") = b.words(1).toDouble
        if (b.words(0) > 0) metrics("roi_ipc") = math.round(b.words(1).toDouble / b.words(0).toDouble * 1e4) / 1e4
      } else if (b.touched) details("bench_stats_partial") = b.masks.map(m => f"$m%02x").mkString(",")
    }
    RunOutcome(status, cycles, retired, failCode, message, details, metrics)
  }
}

object Main {
  def main(args: Array[String]): Unit = new Driver(BoomAdapter).main(args)
}
