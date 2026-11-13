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

object VexiiAdapter extends CoreAdapter {
  override def freshInstancePerRun = true
  type Model = SimCompiled[VexiiRiscv]
  override def irqInputMask: BigInt = 0x888
  def core = "vexiiriscv"
  val configs = VexiiTop.configs
  def xlen = 32
  def isa(config: String) = "rv32im_zicsr_zifencei"
  def sourceDir = new File(sys.env("VEXIIRISCV")).getCanonicalFile
  override def replayEnv = Seq("VEXIIRISCV" -> sourceDir.getPath)
  val ramBase = 0x80000000L
  val ramSize = 0x1000000L

  private def report(key: ModelKey, work: File): SpinalReport[VexiiRiscv] =
    RiscvSimConfig.elaborate(key, work, VexiiTop.spinalConfig,
      sourceRoots = Seq(new File(sourceDir, "src/main/scala")))(VexiiTop(key.config))
  override def elaborate(key: ModelKey, work: File): Seq[File] =
    report(key, work).generatedSourcesPaths.toSeq.map(new File(_))
  def compile(key: ModelKey, work: File, cache: File): Model =
    RiscvSimConfig(key, work, cache, VexiiTop.spinalConfig).compile(report(key, work))
  override def generatedVerilog(model: Model): Seq[File] =
    Option(new File(model.compiledPath, "rtl").listFiles()).toSeq.flatten
      .filter(f => f.getName.endsWith(".v") || f.getName.endsWith(".sv"))

  /** In-order memory responses after a fixed latency, or after 0..3 seeded wait cycles. */
  private class Responder(latency: () => Long) {
    val queue = mutable.Queue.empty[(Long, BigInt, Boolean, Int)]
    var driven = false
    def accept(cycle: Long, data: BigInt, error: Boolean, id: Int): Unit = queue.enqueue((cycle + latency(), data, error, id))
    /** Call once per sampled edge: retires the response the core sampled, returns the next one to drive. */
    def next(cycle: Long): Option[(BigInt, Boolean, Int)] = {
      if (driven) { queue.dequeue(); driven = false }
      queue.headOption.filter(_._1 <= cycle).map { case (_, d, e, id) => driven = true; (d, e, id) }
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
    val writer = if (job.rvfiTrace) Some(new RvfiTraceWriter(new File(job.out, "rvfi.jsonl"), ctx.rvfiHeader)) else None
    val konataLog = if (job.konata) Some(new konata.Backend(new File(job.out, "konata.log"))) else None
    val bench = ctx.elf.symbol("bench_stats").map(new MemWords(_, 2, busBytes))
    var backend: C2Backend = null
    val (status, code, message, cycles) = try {
      val result = SimSession.run(model, job, ctx) { (dut, ctl) =>
        val cd = dut.clockDomain
        val priv = dut.host[PrivilegedPlugin].logic.harts(0)
        val tap = dut.host[TrapTapPlugin].logic
        val ibus = dut.host[FetchCachelessPlugin].logic.bus
        val dbus = dut.host[LsuCachelessPlugin].logic.bus
        priv.int.m.timer #= false
        priv.int.m.software #= false
        priv.int.m.external #= false
        dut.host[PrivilegedPlugin].logic.rdtime #= 0
        ibus.cmd.ready #= true
        ibus.rsp.valid #= false
        dbus.cmd.ready #= true
        dbus.rsp.valid #= false
        cd.forkStimulus(10)
        val random = new scala.util.Random(job.seed)
        def latency(): Long = job.memLatency.map(_.toLong).getOrElse(random.nextInt(4).toLong)
        val fetch = new Responder(() => latency())
        val lsu = new Responder(() => latency())
        val ibytes = ibus.p.dataWidth / 8
        val dbytes = dbus.p.dataWidth / 8
        val traps = mutable.Queue.empty[(BigInt, BigInt)]
        var irqLevels = BigInt(-1)
        // Registered before the probe: the trap values are queued before the probe reports the trap.
        cd.onSamplings {
          ctl.tick()
          val cycle = ctl.cycle
          dut.host[PrivilegedPlugin].logic.rdtime #= cycle
          val levels = job.irqSchedule.map(_.levelsAt(cycle)).getOrElse(BigInt(0))
          priv.int.m.software #= levels.testBit(3)
          priv.int.m.timer #= levels.testBit(7)
          priv.int.m.external #= levels.testBit(11)
          if (levels != irqLevels) { writer.foreach(_.irq(cycle, levels)); irqLevels = levels }
          if (tap.fire.toBoolean) traps.enqueue((tap.epc.toBigInt, tap.tval.toBigInt))

          if (ibus.cmd.valid.toBoolean && ibus.cmd.ready.toBoolean) {
            val addr = ibus.cmd.address.toLong & ~(ibytes - 1L)
            fetch.accept(cycle, read(addr, ibytes), !inRam(addr, ibytes), ibus.cmd.id.toInt)
          }
          if (dbus.cmd.valid.toBoolean && dbus.cmd.ready.toBoolean) {
            val cmd = dbus.cmd
            val addr = cmd.address.toLong & ~(dbytes - 1L)
            val ok = inRam(addr, dbytes)
            if (cmd.write.toBoolean && ok) {
              val data = cmd.data.toBigInt
              val mask = cmd.mask.toInt
              for (i <- 0 until dbytes if (mask & (1 << i)) != 0) memory(addr + i) = ((data >> (8 * i)) & 255).toInt
            }
            lsu.accept(cycle, if (cmd.write.toBoolean) BigInt(0) else read(addr, dbytes), !ok, cmd.id.toInt)
          }
          fetch.next(cycle) match {
            case Some((d, e, id)) => ibus.rsp.valid #= true; ibus.rsp.word #= d; ibus.rsp.error #= e; ibus.rsp.id #= id
            case None => ibus.rsp.valid #= false
          }
          lsu.next(cycle) match {
            case Some((d, e, id)) => dbus.rsp.valid #= true; dbus.rsp.data #= d; dbus.rsp.error #= e; dbus.rsp.id #= id
            case None => dbus.rsp.valid #= false
          }
        }
        backend = new C2Backend(xlen, () => ctl.cycle, () => (tap.privilege.toInt & 3),
          () => if (traps.nonEmpty) traps.dequeue() else throw new IllegalStateException("trap reported without trap-entry values"),
          r => writer.foreach(_.write(r)),
          (c, cause, tval, intr) => writer.foreach(_.trap(c, cause, tval, intr)),
          (addr, sizeLog2, data) => {
            bench.foreach(_.onStore(addr, sizeLog2, data))
            tohost.onStore(addr, sizeLog2, data) match {
              case Some(ToHost.Pass) => ctl.finish(Status.Pass)
              case Some(f: ToHost.Fail) => ctl.finish(Status.Fail, Some(f.code), Some(s"tohost = ${Hex(f.raw)}"))
              case None =>
            }
          })
        val probe = new VexiiRiscvProbe(dut, konataLog, withRvls = false)
        probe.checkLiveness = false
        probe.trace = job.konata
        probe.add(backend)
        cd.waitSamplingWhere(false)
      }
      result
    } finally {
      if (backend != null) backend.drain()
      konataLog.foreach(_.close())
    }
    writer.foreach { w => w.end(cycles, status.name); w.close() }
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
  def main(args: Array[String]): Unit = new Driver(VexiiAdapter).main(args)
}
