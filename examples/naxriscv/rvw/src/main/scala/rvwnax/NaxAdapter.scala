package rvwnax

import java.io.File
import spinal.core._
import spinal.core.sim._
import riscvsim._
import naxriscv.NaxRiscv
import naxriscv.fetch.FetchCachePlugin
import naxriscv.lsu.DataCachePlugin
import naxriscv.lsu2.Lsu2Plugin
import naxriscv.misc.{CommitPlugin, PrivilegedPlugin}
import naxriscv.platform.NaxriscvProbe
import scala.collection.mutable

/** C1 adapter for the NaxRiscv out-of-order core. It drives the core's native refill buses
  * (FetchL1Bus, DataMemBus, LsuPeripheralBus) from a flat RAM and builds C2 from the upstream
  * `NaxriscvProbe` commit events. */
class NaxAdapter extends CoreAdapter {
  override def freshInstancePerRun = true
  type Model = SimCompiled[NaxRiscv]
  val xlen = 32
  def core = "naxriscv"
  val configs = NaxTop.configs
  def isa(config: String) = "rv32ima_zicsr_zifencei"
  def sourceDir = new File(sys.env("NAXRISCV")).getCanonicalFile
  override def replayEnv = Seq("NAXRISCV" -> sourceDir.getPath) ++
    Seq("RVW_NAX_LOCK", "RVW_SPINAL_SOURCE").flatMap(name => sys.env.get(name).map(name -> _))
  val ramBase = 0x80000000L
  val ramSize = 0x1000000

  override def supportsProbes = true
  private def report(key: ModelKey, work: File): SpinalReport[NaxRiscv] = spinalprobes.Probe.enabled(key.probes) {
    RiscvSimConfig.elaborate(key, work, NaxTop.spinalConfig,
      sourceRoots = Seq(new File(sourceDir, "src/main/scala")))(NaxTop(key.config))
  }
  override def elaborate(key: ModelKey, work: File): Seq[File] =
    report(key, work).generatedSourcesPaths.toSeq.map(new File(_))
  /** `RVW_NAX_CHECKS=DIR`: a generated `rvw.micro-checks/1` directory (monitors.sv, binds.sv) to
    * compile into the model. Each failed assertion prints one firing line instead of stopping. */
  val checksDir: Option[File] = sys.env.get("RVW_NAX_CHECKS").filter(_.nonEmpty).map(new File(_).getCanonicalFile)
  def compile(key: ModelKey, work: File, cache: File): Model = {
    val cfg = RiscvSimConfig(key, work, cache, NaxTop.spinalConfig)
    // The pinned SpinalHDL ignores addRtl when it compiles a report; pass the files to Verilator.
    // Content-addressed names keep the Verilator cache key (which includes the flags) exact.
    checksDir.foreach { dir =>
      def read(name: String) = new String(java.nio.file.Files.readAllBytes(new File(dir, name).toPath), "UTF-8")
      val text = NaxAdapter.firingMonitors(read("monitors.sv")) + "\n" + read("binds.sv")
      cache.mkdirs()
      val file = new File(cache, s"rvw-checks-${ElfFile.sha256(text.getBytes("UTF-8"))}.sv")
      if (!file.isFile) java.nio.file.Files.write(file.toPath, text.getBytes("UTF-8"))
      cfg.addSimulatorFlag(file.getAbsolutePath)
    }
    cfg.compile(report(key, work))
  }
  override def generatedVerilog(model: Model): Seq[File] =
    Option(new File(model.compiledPath, "rtl").listFiles()).toSeq.flatten
      .filter(f => f.getName.endsWith(".v") || f.getName.endsWith(".sv"))

  def run(model: Model, job: RunJob, ctx: RunContext): RunOutcome = {
    require(!job.rvfiCheck, "NaxRiscv adapter has no riscv-formal monitor; use --rvfi-trace")
    require(job.socMap.isEmpty, "NaxRiscv adapter does not support --soc-map")
    require(job.irqSchedule.isEmpty, "NaxRiscv adapter does not drive interrupt schedules")
    require(!job.konata, "NaxRiscv adapter has no Konata backend; use --probes")
    require(ctx.elf.entry == ramBase, "ELF entry must equal reset PC 0x80000000")
    val tohost = new ToHost(ToHost.find(ctx.elf).getOrElse(
      throw new IllegalArgumentException("ELF has no tohost symbol")), busBytes)
    val ram = new Array[Byte](ramSize)
    def inRam(a: Long, n: Long): Boolean = a >= ramBase && n >= 0 && a + n <= ramBase + ramSize
    ctx.elf.load { (addr, bytes) =>
      require(inRam(addr, bytes.length), "ELF segment outside RAM")
      System.arraycopy(bytes, 0, ram, (addr - ramBase).toInt, bytes.length)
    }
    // The architectural image: the ELF plus every committed store, in commit order.
    val arch = ram.clone()
    def read(mem: Array[Byte], addr: Long, n: Int): BigInt =
      if (!inRam(addr, n)) BigInt(0)
      else (0 until n).foldLeft(BigInt(0))((v, i) => v | (BigInt(mem((addr - ramBase).toInt + i) & 0xff) << (8 * i)))
    def write(mem: Array[Byte], addr: Long, n: Int, data: BigInt): Unit =
      if (inRam(addr, n)) for (i <- 0 until n) mem((addr - ramBase).toInt + i) = ((data >> (8 * i)) & 0xff).toByte

    var writer = Option.empty[RvfiTraceWriter]
    var finish = Option.empty[(Status, Option[Long], Option[String])]
    var traceEnded = false
    val bench = ctx.elf.symbol("bench_stats").map(new MemWords(_, 2, busBytes))
    var backend: C2Backend = null
    var probes = Option.empty[ProbeCollector]
    // Generated-check firings, counted from the monitors' output lines while this run is active.
    val firings = mutable.LinkedHashMap.empty[String, Long]
    val capture = checksDir.isDefined && NativeOutput.start()
    val onLine: NativeOutput.Line => Unit = l => NaxAdapter.firedRule(l.text).foreach(id =>
      firings.synchronized(firings(id) = firings.getOrElse(id, 0L) + 1))
    if (capture) NativeOutput.subscribe(onLine)
    val (status0, code0, message0, cycles) = try {
      val result = SimSession.run(model, job, ctx) { (dut, ctl) =>
        val cd = dut.clockDomain
        writer = if (job.rvfiTrace) Some(new RvfiTraceWriter(new File(job.out, "rvfi.jsonl"), ctx.rvfiHeader)) else None
        probes = ProbeCollector.open(spinalprobes.Probe.of(dut), job, ctx.rvfiHeader)
        val fw = dut.framework
        val ibus = fw.getService[FetchCachePlugin].mem.get
        val dmem = fw.getService[DataCachePlugin].mem.get
        val pbus = fw.getService[Lsu2Plugin].peripheralBus.get
        val priv = fw.getService[PrivilegedPlugin]
        val int = priv.io.get.int
        val tap = fw.getService[TapPlugin].logic.get
        val reschedule = fw.getService[CommitPlugin].logic.get.whitebox.reschedule

        int.machine.timer #= false
        int.machine.software #= false
        int.machine.external #= false
        if (priv.p.withSupervisor) int.supervisor.external #= false
        if (int.user != null) int.user.external #= false
        priv.io.get.rdtime #= 0
        ibus.cmd.ready #= true
        ibus.rsp.valid #= false
        dmem.read.cmd.ready #= true
        dmem.read.rsp.valid #= false
        dmem.write.cmd.ready #= true
        dmem.write.rsp.valid #= false
        pbus.cmd.ready #= true
        pbus.rsp.valid #= false
        cd.forkStimulus(10)

        val random = new scala.util.Random(job.seed)
        def latency(): Long = job.memLatency.map(_.toLong).getOrElse(random.nextInt(4).toLong)
        val ibytes = ibus.p.dataWidth / 8
        val ibeats = ibus.p.lineSize / ibytes
        val dbytes = dmem.p.dataWidth / 8
        val dbeats = dmem.p.lineSize / dbytes
        // (address, beats left, first cycle)
        var fetchPending = Option.empty[(Long, Int, Long)]
        val reads = mutable.Queue.empty[(Int, Long, Int, Long)]
        val writes = mutable.Queue.empty[(Int, Boolean, Long)]
        var writeAddress = -1L
        var writeBeat = 0
        var ioRsp = false
        // xepc of the next trap: the ROB pc of the latest commit-time reschedule with `trap` set.
        // Some of them are not traps (a satp write flushes this way), so only the latest one counts.
        var epc = Option.empty[BigInt]
        var probe: NaxriscvProbe = null

        cd.onSamplings {
          ctl.tick()
          val cycle = ctl.cycle
          probes.foreach(_.sample(cycle))
          if (reschedule.valid.toBoolean && reschedule.trap.toBoolean)
            epc = Some(BigInt(probe.robArray(reschedule.robId.toInt).pc) & ((BigInt(1) << xlen) - 1))

          if (ibus.cmd.valid.toBoolean && ibus.cmd.ready.toBoolean)
            fetchPending = Some((ibus.cmd.address.toLong & ~(ibus.p.lineSize - 1L), ibeats, cycle + latency()))
          if (dmem.read.cmd.valid.toBoolean && dmem.read.cmd.ready.toBoolean) {
            val id = if (dmem.p.readIdWidth > 0) dmem.read.cmd.id.toInt else 0
            reads.enqueue((id, dmem.read.cmd.address.toLong & ~(dmem.p.lineSize - 1L), dbeats, cycle + latency()))
          }
          if (dmem.write.cmd.valid.toBoolean && dmem.write.cmd.ready.toBoolean) {
            val f = dmem.write.cmd.fragment
            if (writeBeat == 0) writeAddress = f.address.toLong & ~(dmem.p.lineSize - 1L)
            val ok = inRam(writeAddress, dmem.p.lineSize)
            write(ram, writeAddress + writeBeat * dbytes, dbytes, f.data.toBigInt)
            writeBeat += 1
            if (dmem.write.cmd.last.toBoolean) {
              writes.enqueue((if (dmem.p.writeIdWidth > 0) f.id.toInt else 0, !ok, cycle + latency()))
              writeBeat = 0
            }
          }
          // No device is mapped: every peripheral access answers with an error.
          pbus.rsp.valid #= ioRsp
          pbus.rsp.error #= true
          ioRsp = pbus.cmd.valid.toBoolean && pbus.cmd.ready.toBoolean

          ibus.rsp.valid #= false
          fetchPending match {
            case Some((a, n, at)) if at <= cycle =>
              ibus.rsp.valid #= true
              ibus.rsp.data #= read(ram, a, ibytes)
              ibus.rsp.error #= !inRam(a, ibytes)
              fetchPending = if (n > 1) Some((a + ibytes, n - 1, at)) else None
            case _ =>
          }
          ibus.cmd.ready #= fetchPending.isEmpty
          dmem.read.rsp.valid #= false
          reads.headOption match {
            case Some((id, a, n, at)) if at <= cycle =>
              dmem.read.rsp.valid #= true
              if (dmem.p.readIdWidth > 0) dmem.read.rsp.id #= id
              dmem.read.rsp.data #= read(ram, a, dbytes)
              dmem.read.rsp.error #= !inRam(a, dbytes)
              if (n > 1) reads(0) = (id, a + dbytes, n - 1, at) else reads.dequeue()
            case _ =>
          }
          dmem.write.rsp.valid #= false
          writes.headOption match {
            case Some((id, err, at)) if at <= cycle =>
              dmem.write.rsp.valid #= true
              if (dmem.p.writeIdWidth > 0) dmem.write.rsp.id #= id
              dmem.write.rsp.error #= err
              writes.dequeue()
            case _ =>
          }
        }

        backend = new C2Backend(xlen, () => ctl.cycle, () => tap.privilege.toInt & 3,
          pc => read(arch, pc, 4).toLong,
          () => { val e = epc.getOrElse(throw new IllegalStateException("trap reported without a trapping ROB entry")); epc = None; e },
          r => writer.foreach(_.write(r)),
          (c, cause, tval, intr) => writer.foreach(_.trap(c, cause, tval, intr)),
          (addr, sizeLog2, data) => {
            write(arch, addr.toLong, 1 << sizeLog2, data)
            bench.foreach(_.onStore(addr, sizeLog2, data))
            tohost.onStore(addr, sizeLog2, data) match {
              case Some(ToHost.Pass) => finish = Some((Status.Pass, None, None))
              case Some(f: ToHost.Fail) => finish = Some((Status.Fail, Some(f.code), Some(s"tohost = ${Hex(f.raw)}")))
              case None =>
            }
          })
        probe = new NaxriscvProbe(dut, 0)
        probe.add(backend, isa(job.model.config))
        fork {
          while (true) {
            cd.waitSampling()
            sleep(1) // The upstream probe callbacks finish first.
            finish.foreach { case (s, c, m) =>
              backend.drain()
              writer.foreach(_.end(ctl.cycle, s.name)); traceEnded = true
              ctl.finish(s, c, m)
            }
          }
        }
        cd.waitSamplingWhere(false)
      }
      probes.foreach(_.close(result._4))
      result
    } finally {
      probes.foreach(_.abandon())
      if (backend != null && !traceEnded) backend.drain()
      if (capture) { NativeOutput.drain(); NativeOutput.unsubscribe(onLine) }
    }
    val checks = checksDir.map { dir =>
      val rules = scala.io.Source.fromFile(new File(dir, "binds.sv")).getLines().count(_.startsWith("bind "))
      val fired = firings.synchronized(firings.toSeq)
      val report = ujson.Obj("schema" -> "rvw.checks-run/1", "toplevel" -> "NaxRiscv", "source" -> dir.getPath,
        "inserted" -> rules, "fired" -> fired.size, "capture" -> capture,
        "status" -> (if (!capture) "inconclusive" else if (fired.nonEmpty) "fail" else status0.name),
        "firings" -> ujson.Arr.from(fired.map { case (id, n) => ujson.Obj("id" -> id, "count" -> RvwJson.num(n)) }))
      java.nio.file.Files.write(new File(job.out, "checks-run.json").toPath, ujson.write(report, indent = 1).getBytes("UTF-8"))
      (capture, fired)
    }
    // A pass needs zero firings; without output capture the checks are inconclusive.
    val (status, code, message) = checks match {
      case Some((false, _)) if status0 == Status.Pass => (Status.Error, None, Some("generated checks compiled but their output was not captured"))
      case Some((true, fired)) if fired.nonEmpty && status0 == Status.Pass =>
        (Status.Fail, None, Some(s"generated checks fired: ${fired.map(_._1).mkString(", ")}"))
      case _ => (status0, code0, message0)
    }
    if (!traceEnded) writer.foreach(_.end(cycles, status.name))
    writer.foreach(_.close())
    val retired = if (backend == null) 0L else backend.retired
    val metrics = ujson.Obj()
    bench.filter(_.complete).foreach { b =>
      metrics("roi_cycles") = RvwJson.num(b.words(0).toLong)
      metrics("roi_instret") = RvwJson.num(b.words(1).toLong)
    }
    RunOutcome(status, cycles, retired, code, message,
      ujson.Obj("traps" -> RvwJson.num(if (backend == null) 0L else backend.traps), "rvfi_records" -> RvwJson.num(retired),
        "tohost" -> Hex(tohost.value), "rvfi_monitor" -> false, "memory_bytes" -> RvwJson.num(ramSize.toLong),
        "commit_source" -> "NaxriscvProbe",
        "generated_checks" -> checks.map { case (c, f) => ujson.Obj("captured" -> c, "fired" -> f.size,
          "firings" -> RvwJson.num(f.map(_._2).sum)) }.getOrElse(ujson.Null)), metrics)
  }
}

object NaxAdapter {
  private val Assert = """assert\(([^;]*)\);""".r
  private val Fired = """RVW_CHECK_FIRE \S*rvw_rule_([A-Za-z0-9_]+)_instance""".r.unanchored
  /** The generated monitors with each `assert(e);` turned into a firing line, so that a run
    * counts failures instead of stopping at the first one. */
  def firingMonitors(source: String): String =
    Assert.replaceAllIn(source, m => java.util.regex.Matcher.quoteReplacement(s"""if(!(${m.group(1)})) $$display("RVW_CHECK_FIRE %m");"""))
  def firedRule(line: String): Option[String] = line match { case Fired(id) => Some(id); case _ => None }
}

object Main {
  def main(args: Array[String]): Unit = new Driver(new NaxAdapter).main(args)
}
