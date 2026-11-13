package rvwvexii

import java.io.File
import spinal.core._
import spinal.core.sim._
import riscvsim._
import vexiiriscv.VexiiRiscv
import vexiiriscv.execute.lsu.LsuCachelessPlugin
import vexiiriscv.fetch.FetchCachelessPlugin
import vexiiriscv.misc.PrivilegedPlugin
import vexiiriscv.test.{VexiiRiscvProbe, konata}
import scala.collection.mutable

class VexiiAdapter(val xlen: Int) extends CoreAdapter {
  override def freshInstancePerRun = true
  type Model = SimCompiled[VexiiRiscv]
  override def irqInputMask: BigInt = if (xlen == 64) 0xa88 else 0x888
  def core = "vexiiriscv"
  val configs = VexiiTop.configs.filter(_.startsWith(s"rv$xlen"))
  def isa(config: String) = s"rv${xlen}im${if (config.endsWith("asu")) "a" else ""}_zicsr_zifencei"
  def sourceDir = new File(sys.env("VEXIIRISCV")).getCanonicalFile
  override def replayEnv = Seq("VEXIIRISCV" -> sourceDir.getPath) ++
    Seq("RVW_COSIM_DPI", "RVW_COSIM_FAULT_ORDER", "RVW_VEX_LOCK", "RVW_VEX_XLEN", "RVW_VEX_DEVICE_MAP", "RVW_DEVICE_LIBRARY").flatMap(
      name => sys.env.get(name).map(name -> _))
  val ramBase = 0x80000000L
  val ramSize = 0x1000000L

  override def supportsProbes = true
  private def report(key: ModelKey, work: File): SpinalReport[VexiiRiscv] = spinalprobes.Probe.enabled(key.probes) {
    RiscvSimConfig.elaborate(key, work, VexiiTop.spinalConfig,
      sourceRoots = Seq(new File(sourceDir, "src/main/scala")))(VexiiTop(key.config))
  }
  override def elaborate(key: ModelKey, work: File): Seq[File] =
    report(key, work).generatedSourcesPaths.toSeq.map(new File(_))
  def compile(key: ModelKey, work: File, cache: File): Model =
    RiscvSimConfig(key, work, cache, VexiiTop.spinalConfig).compile(report(key, work))
  override def generatedVerilog(model: Model): Seq[File] =
    Option(new File(model.compiledPath, "rtl").listFiles()).toSeq.flatten
      .filter(f => f.getName.endsWith(".v") || f.getName.endsWith(".sv"))

  /** In-order memory responses after a fixed latency, or after 0..3 seeded wait cycles. */
  private class Responder(latency: () => Long) {
    val queue = mutable.Queue.empty[(Long, BigInt, Boolean, Int, Boolean)]
    var driven = false
    def accept(cycle: Long, data: BigInt, error: Boolean, id: Int, scMiss: Boolean = false): Unit = queue.enqueue((cycle + latency(), data, error, id, scMiss))
    /** Call once per sampled edge: retires the response the core sampled, returns the next one to drive. */
    def next(cycle: Long): Option[(BigInt, Boolean, Int, Boolean)] = {
      if (driven) { queue.dequeue(); driven = false }
      queue.headOption.filter(_._1 <= cycle).map { case (_, d, e, id, sc) => driven = true; (d, e, id, sc) }
    }
  }

  def run(model: Model, job: RunJob, ctx: RunContext): RunOutcome = {
    require(!job.rvfiCheck, "VexiiRiscv adapter has no riscv-formal monitor; use --rvfi-trace")
    require(job.socMap.isEmpty, "VexiiRiscv adapter does not support --soc-map")
    require(ctx.elf.entry == ramBase, "ELF entry must equal reset PC 0x80000000")
    val tohost = new ToHost(ToHost.find(ctx.elf).getOrElse(
      throw new IllegalArgumentException("ELF has no tohost symbol")), busBytes)
    val memory = mutable.LongMap.empty[Int]
    def inRam(a: Long, n: Long): Boolean = a >= ramBase && n >= 0 && a + n <= ramBase + ramSize
    ctx.elf.load { (addr, bytes) =>
      require(inRam(addr, bytes.length), "ELF segment outside RAM")
      bytes.indices.foreach(i => memory(addr + i) = bytes(i) & 255)
    }
    def read(addr: Long, n: Int): BigInt = (0 until n).foldLeft(BigInt(0)) { (v, i) =>
      v | (BigInt(memory.getOrElse(addr + i, 0)) << (8 * i))
    }
    val devices = sys.env.get("RVW_VEX_DEVICE_MAP").map(path =>
      new DeviceBus(new File(path), new File(sys.env("RVW_DEVICE_LIBRARY")), job.seed))
    var writer = Option.empty[RvfiTraceWriter]
    val events = mutable.ArrayBuffer.empty[(Long, () => Unit)]
    var finish = Option.empty[(Status, Option[Long], Option[String])]
    var traceEnded = false
    val konataLog = if (job.konata) Some(new konata.Backend(new File(job.out, "konata.log"))) else None
    val bench = ctx.elf.symbol("bench_stats").map(new MemWords(_, 2, busBytes))
    var backend: C2Backend = null
    var probes = Option.empty[ProbeCollector]
    val (status, code, message, cycles) = try {
      val result = SimSession.run(model, job, ctx) { (dut, ctl) =>
        val cd = dut.clockDomain
        val dpi = if (sys.env.get("RVW_COSIM_DPI").contains("1"))
          Some(dut.host[LockstepTapPlugin].logic.transport) else None
        dpi.foreach(_.initialize())
        writer = if (job.rvfiTrace) Some(new RvfiTraceWriter(new File(job.out, "rvfi.jsonl"),
          ctx.rvfiHeader, observe = dpi.filter(_ => sys.env.contains("RVW_COSIM_PORT"))
            .map(m => (line: String) => m.observe(line)))) else None
        probes = ProbeCollector.open(spinalprobes.Probe.of(dut), job, ctx.rvfiHeader)
        val priv = dut.host[PrivilegedPlugin].logic.harts(0)
        val tap = dut.host[TrapTapPlugin].logic
        val ibus = dut.host[FetchCachelessPlugin].logic.bus
        val dbus = dut.host[LsuCachelessPlugin].logic.bus
        if (dut.host[PrivilegedPlugin].p.withSupervisor) priv.int.s.external #= false
        priv.int.m.timer #= false
        priv.int.m.software #= false
        priv.int.m.external #= false
        dut.host[PrivilegedPlugin].logic.rdtime #= 0
        ibus.cmd.ready #= true
        ibus.rsp.valid #= false
        dbus.cmd.ready #= true
        if (dbus.p.withAmo) dbus.rsp.scMiss #= false
        dbus.rsp.valid #= false
        cd.forkStimulus(10)
        val random = new scala.util.Random(job.seed)
        def latency(): Long = job.memLatency.map(_.toLong).getOrElse(random.nextInt(4).toLong)
        val fetch = new Responder(() => latency())
        val lsu = new Responder(() => latency())
        val ibytes = ibus.p.dataWidth / 8
        val dbytes = dbus.p.dataWidth / 8
        var reservation = Option.empty[Long]
        val traps = mutable.Queue.empty[(BigInt, BigInt)]
        var irqLevels = BigInt(-1)
        // Registered before the probe: the trap values are queued before the probe reports the trap.
        cd.onSamplings {
          ctl.tick()
          val cycle = ctl.cycle
          probes.foreach(_.sample(cycle))
          dut.host[PrivilegedPlugin].logic.rdtime #= cycle
          val deviceLevels = devices.map(_.tick(cycle)).getOrElse(BigInt(0))
          val levels = job.irqSchedule.map(_.levelsAt(cycle)).getOrElse(deviceLevels)
          if (dut.host[PrivilegedPlugin].p.withSupervisor) priv.int.s.external #= levels.testBit(9)
          priv.int.m.software #= levels.testBit(3)
          priv.int.m.timer #= levels.testBit(7)
          priv.int.m.external #= levels.testBit(11)
          if (levels != irqLevels) { events += ((cycle, () => writer.foreach(_.irq(cycle, levels)))); irqLevels = levels }
          if (tap.fire.toBoolean) traps.enqueue((tap.epc.toBigInt, tap.tval.toBigInt))

          if (ibus.cmd.valid.toBoolean && ibus.cmd.ready.toBoolean) {
            val addr = ibus.cmd.address.toLong & ~(ibytes - 1L)
            fetch.accept(cycle, read(addr, ibytes), !inRam(addr, ibytes), ibus.cmd.id.toInt)
          }
          if (dbus.cmd.valid.toBoolean && dbus.cmd.ready.toBoolean) {
            val cmd = dbus.cmd
            val addr = cmd.address.toLong & ~(dbytes - 1L)
            val ok = inRam(addr, dbytes)
            val atomic = dbus.p.withAmo && cmd.amoEnable.toBoolean
            val op = if (atomic) cmd.amoOp.toInt else -1
            val old = read(addr, dbytes)
            val scMiss = op == 3 && !reservation.contains(addr)
            val width = 1 << cmd.size.toInt
            val shift = (cmd.address.toLong - addr).toInt * 8
            val fieldMask = (BigInt(1) << (width * 8)) - 1
            val data = if (atomic && op != 2 && op != 3)
              (BigInt(VexiiRiscvProbe.amoWriteValue(op, width, (cmd.data.toBigInt >> shift).toLong, (old >> shift).toLong)) & fieldMask) << shift
            else cmd.data.toBigInt
            val write = if (atomic) op != 2 && !scMiss else cmd.write.toBoolean
            if (ok && write) {
              val mask = cmd.mask.toInt
              for (i <- 0 until dbytes if (mask & (1 << i)) != 0) memory(addr + i) = ((data >> (8 * i)) & 255).toInt
              reservation = None
            }
            if (ok && op == 2) reservation = Some(addr)
            if (op == 3) reservation = None
            if (devices.exists(_.contains(cmd.address.toLong, width))) {
              require(!atomic, "device atomics are unsupported")
              if (cmd.write.toBoolean) devices.get.write(cmd.address.toLong, width, cmd.data.toBigInt >> shift)
              val result = if (cmd.write.toBoolean) BigInt(0) else devices.get.read(cmd.address.toLong, width) << shift
              lsu.accept(cycle, result, false, cmd.id.toInt)
            } else {
              lsu.accept(cycle, if (atomic || !cmd.write.toBoolean) old else BigInt(0), !ok, cmd.id.toInt, scMiss)
            }
          }
          fetch.next(cycle) match {
            case Some((d, e, id, _)) => ibus.rsp.valid #= true; ibus.rsp.word #= d; ibus.rsp.error #= e; ibus.rsp.id #= id
            case None => ibus.rsp.valid #= false
          }
          lsu.next(cycle) match {
            case Some((d, e, id, sc)) =>
              dbus.rsp.valid #= true; dbus.rsp.data #= d; dbus.rsp.error #= e; dbus.rsp.id #= id
              if (dbus.p.withAmo) dbus.rsp.scMiss #= sc
            case None => dbus.rsp.valid #= false
          }
        }
        backend = new C2Backend(xlen, () => ctl.cycle, () => (tap.privilege.toInt & 3),
          () => if (traps.nonEmpty) traps.dequeue() else throw new IllegalStateException("trap reported without trap-entry values"),
          r => {
            val sampled = if (sys.env.get("RVW_COSIM_FAULT_ORDER").contains(r.order.toString)) {
              require(r.rd != 0, "fault target must write a GPR")
              r.copy(rdWdata = r.rdWdata ^ 1)
            } else r
            events += ((r.cycle, () => writer.foreach(_.write(sampled))))
          },
          (c, cause, tval, intr) => events += ((c, () => writer.foreach(_.trap(c, cause, tval, intr)))),
          (addr, sizeLog2, data) => {
            bench.foreach(_.onStore(addr, sizeLog2, data))
            tohost.onStore(addr, sizeLog2, data) match {
              case Some(ToHost.Pass) => finish = Some((Status.Pass, None, None))
              case Some(f: ToHost.Fail) => finish = Some((Status.Fail, Some(f.code), Some(s"tohost = ${Hex(f.raw)}")))
              case None =>
            }
          })
        val probe = new VexiiRiscvProbe(dut, konataLog, withRvls = false)
        probe.checkLiveness = false
        probe.trace = job.konata
        probe.add(backend)
        fork {
          while (true) {
            cd.waitSampling()
            sleep(1) // The upstream probe and bus callbacks finish before transport runs.
            if (finish.nonEmpty) backend.drain()
            val watermark = backend.pendingCycle.getOrElse(Long.MaxValue)
            val ready = events.filter(_._1 <= watermark).sortBy(_._1).toVector
            events.filterInPlace(_._1 > watermark)
            ready.foreach(_._2())
            finish.foreach { case (s, c, m) =>
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
      devices.foreach(_.close())
      if (backend != null) backend.drain()
      konataLog.foreach(_.close())
    }
    if (!traceEnded && !sys.env.get("RVW_COSIM_DPI").contains("1")) {
      events.sortBy(_._1).foreach(_._2())
      writer.foreach(_.end(cycles, status.name))
    }
    writer.foreach(_.close())
    val retired = if (backend == null) 0L else backend.retired
    val metrics = ujson.Obj()
    bench.filter(_.complete).foreach { b =>
      metrics("roi_cycles") = RvwJson.num(b.words(0).toLong)
      metrics("roi_instret") = RvwJson.num(b.words(1).toLong)
    }
    RunOutcome(status, cycles, retired, code, message,
      ujson.Obj("traps" -> RvwJson.num(if (backend == null) 0L else backend.traps), "rvfi_records" -> RvwJson.num(retired),
        "tohost" -> Hex(tohost.value), "rvfi_monitor" -> false, "memory_bytes" -> RvwJson.num(ramSize),
        "commit_source" -> "VexiiRiscvProbe"), metrics)
  }
}

object Main {
  def main(args: Array[String]): Unit = new Driver(new VexiiAdapter(sys.env.getOrElse("RVW_VEX_XLEN", "32").toInt)).main(args)
}
