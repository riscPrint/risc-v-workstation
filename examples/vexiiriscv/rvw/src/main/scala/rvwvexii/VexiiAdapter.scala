package rvwvexii

import java.io.File
import spinal.core._
import spinal.core.sim._
import riscvsim._
import vexiiriscv.VexiiRiscv
import vexiiriscv.execute.lsu.{LsuCachelessPlugin, LsuPlugin}
import vexiiriscv.fetch.FetchCachelessPlugin
import vexiiriscv.misc.PrivilegedPlugin
import vexiiriscv.test.{VexiiRiscvProbe, konata}
import scala.collection.mutable

class VexiiAdapter(val xlen: Int) extends CoreAdapter {
  override def freshInstancePerRun = true
  override def supportsBootPayloads = true
  type Model = SimCompiled[VexiiRiscv]
  override def irqInputMask: BigInt = if (xlen == 64) 0xa88 else 0x888
  def core = "vexiiriscv"
  val configs = VexiiTop.configs.filter(_.startsWith(s"rv$xlen"))
  def isa(config: String) = s"rv${xlen}im${if (VexiiTop.supervisor(config)) "a" else ""}${if (VexiiTop.compressed(config)) "c" else ""}_zicsr_zifencei"
  def sourceDir = new File(sys.env("VEXIIRISCV")).getCanonicalFile
  override def replayEnv = Seq("VEXIIRISCV" -> sourceDir.getPath) ++
    Seq("RVW_COSIM_DPI", "RVW_COSIM_FAULT_ORDER", "RVW_VEX_LOCK", "RVW_VEX_XLEN", "RVW_VEX_DEVICE_MAP", "RVW_DEVICE_LIBRARY").flatMap(
      name => sys.env.get(name).map(name -> _))
  val ramBase = 0x80000000L
  val ramSize = 0x1000000L

  override def supportsProbes = true
  override def supportsStimulus = true
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
    require(job.socMap.isEmpty || !sys.env.contains("RVW_VEX_DEVICE_MAP"), "select one device map")
    job.socMap.foreach(m => require(m.interrupts.isEmpty && m.regions.forall(r => !r.cacheable), "live devices require uncached regions and device-owned interrupts"))
    job.socMap.foreach(m => require(m.regions.filter(_.kind == "mmio").map(r => (r.base, r.size)).toSet == VexiiTop.liveMap.regions.filter(_.kind == "mmio").map(r => (r.base, r.size)).toSet, "device regions must match project PMA map"))
    val live = job.socMap.map(new LiveDevices(_))
    live.foreach(d => require((d.interruptMask & ~irqInputMask) == 0, "unsupported device interrupt pin"))
    require(ctx.elf.entry == ramBase, "ELF entry must equal reset PC 0x80000000")
    val tohost = new ToHost(ToHost.find(ctx.elf).getOrElse(
      throw new IllegalArgumentException("ELF has no tohost symbol")), busBytes)
    val ramSize = job.socMap.flatMap(_.regions.find(_.kind == "ram")).map(_.size.toLong).getOrElse(this.ramSize)
    require(ramSize > 0 && ramSize <= 128L * 1024 * 1024, "RAM size must be at most 128 MiB")
    val memory = new ByteMemory(ramBase, ramSize.toInt)
    def inRam(a: Long, n: Long): Boolean = a >= ramBase && n >= 0 && a + n <= ramBase + ramSize
    ctx.loadMemory { (addr, bytes) =>
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
    var lastRetiredPc = Option.empty[BigInt]
    var lastRetiredMode = Option.empty[Int]
    val retiredByMode = Array.fill(4)(0L)
    var probes = Option.empty[ProbeCollector]
    val loadAddresses = mutable.LongMap.empty[(Long, Long)]
    val storeAddresses = mutable.LongMap.empty[(Long, Long)]
    val translatedAddresses = mutable.ArrayBuffer.empty[ujson.Value]
    var walkCapture = Option.empty[WalkCapture]
    // rvw.stimulus/1: the program writes a step to stimulus_step; the harness drives the event
    // on the device map and writes the step to stimulus_ack.
    def symbol(name: String) = ctx.elf.symbol(name).getOrElse(throw new IllegalArgumentException(s"stimulus needs ELF symbol $name"))
    val stimulusWords = job.stimulus.map(_ => (symbol("stimulus_step"), symbol("stimulus_ack")))
    var currentCycle = 0L
    val externalEvidence = for (stimulus <- job.stimulus; layout <- devices.flatMap(_.plicEvidence)) yield {
      layout("stimulus") = ujson.Arr.from(stimulus.events)
      layout("request_address") = Hex(BigInt(stimulusWords.get._1))
      layout("ack_address") = Hex(BigInt(stimulusWords.get._2))
      layout
    }
    def external(cycle: Long, kind: String, fields: ujson.Obj): Unit = if (externalEvidence.nonEmpty)
      events += ((cycle, () => writer.foreach(_.externalInterrupt(cycle, kind, fields))))
    val mailbox = job.stimulus.map(s => new StimulusMailbox(s, event => event("kind").str match {
      case "plic-level" =>
        devices.getOrElse(throw new IllegalArgumentException("plic-level stimulus needs RVW_VEX_DEVICE_MAP"))
          .setInput("plic", event("source").num.toInt, event("level").bool)
        external(currentCycle, "source", ujson.Obj("source" -> event("source"), "level" -> event("level"), "step" -> event("step")))
      case other => throw new IllegalArgumentException(s"unsupported stimulus kind $other")
    }, step => {
      (0 until 8).foreach(i => memory(stimulusWords.get._2 + i) = ((step >> (8 * i)) & 255).toInt)
      external(currentCycle, "ack", ujson.Obj("address" -> Hex(BigInt(stimulusWords.get._2)), "bytes" -> 8,
        "value" -> Hex(BigInt(step)), "step" -> RvwJson.num(step)))
    }))
    val lastVirtual = mutable.LongMap.empty[Long]
    def logicalAddress(load: Boolean, id: Long, physical: Long): Long = {
      // The probe reports an AMO's store half with a stale store id. A store whose tag entry is
      // absent or names another address binds to the latest hart command at its physical address
      // (an AMO is one command for both halves).
      val observed = (if (load) loadAddresses.get(id) else storeAddresses.get(id).filter(_._1 == physical))
        .orElse(if (load) None else lastVirtual.get(physical).map(v => (physical, v)))
        .getOrElse(throw new IllegalStateException(s"missing observed address for memory tag $id"))
      require(observed._1 == physical, "memory tag does not match the observed physical address")
      observed._2
    }
    val (status, code, message, cycles) = try {
      val result = SimSession.run(model, job, ctx) { (dut, ctl) =>
        val cd = dut.clockDomain
        val dpi = if (sys.env.get("RVW_COSIM_DPI").contains("1"))
          Some(dut.host[LockstepTapPlugin].logic.transport) else None
        dpi.foreach(_.initialize())
        writer = if (job.rvfiTrace) Some(new RvfiTraceWriter(new File(job.out, "rvfi.jsonl"),
          ujson.Obj.from(ctx.rvfiHeader.value.toSeq ++ externalEvidence.toSeq.map(e => "external_interrupts" -> e)), observe = dpi.filter(_ => sys.env.contains("RVW_COSIM_PORT"))
            .map(m => (line: String) => m.observe(line)))) else None
        probes = ProbeCollector.open(spinalprobes.Probe.of(dut), job, ctx.rvfiHeader)
        val priv = dut.host[PrivilegedPlugin].logic.harts(0)
        val tap = dut.host[TrapTapPlugin].logic
        val ibusOpt = dut.host.get[FetchCachelessPlugin].map(_.logic.bus)
        // With an LSU L1, the cacheless bus is the LSU plugin's I/O bus (uncached regions only).
        val dbus = dut.host.get[LsuCachelessPlugin].map(_.logic.bus).getOrElse(dut.host[LsuPlugin].logic.bus)
        walkCapture = tap.walk.map(w => new WalkCapture(xlen, w.va.getBitsWidth))
        if (dut.host[PrivilegedPlugin].p.withSupervisor) priv.int.s.external #= false
        priv.int.m.timer #= false
        priv.int.m.software #= false
        priv.int.m.external #= false
        dut.host[PrivilegedPlugin].logic.rdtime #= 0
        ibusOpt.foreach { ibus => ibus.cmd.ready #= true; ibus.rsp.valid #= false }
        dbus.cmd.ready #= true
        if (dbus.p.withAmo) dbus.rsp.scMiss #= false
        dbus.rsp.valid #= false
        cd.forkStimulus(10)
        val random = new scala.util.Random(job.seed)
        def latency(): Long = job.memLatency.map(_.toLong).getOrElse(random.nextInt(4).toLong)
        val fetch = new Responder(() => latency())
        val lsu = new Responder(() => latency())
        val ibytes = ibusOpt.map(_.p.dataWidth / 8).getOrElse(4)
        val l1 = new L1Buses(dut, memory, (a, n) => inRam(a, n), () => latency())
        val dbytes = dbus.p.dataWidth / 8
        var reservation = Option.empty[Long]
        val traps = mutable.Queue.empty[(BigInt, BigInt)]
        var irqLevels = BigInt(-1)
        // Registered before the probe: the trap values are queued before the probe reports the trap.
        cd.onSamplings {
          ctl.tick()
          val cycle = ctl.cycle
          currentCycle = cycle
          probes.foreach(_.sample(cycle))
          dut.host[PrivilegedPlugin].logic.rdtime #= cycle
          val deviceLevels = live.map(_.tick(cycle)).orElse(devices.map(_.tick(cycle))).getOrElse(BigInt(0))
          val levels = job.irqSchedule.map(_.levelsAt(cycle)).getOrElse(deviceLevels)
          if (dut.host[PrivilegedPlugin].p.withSupervisor) priv.int.s.external #= levels.testBit(9)
          priv.int.m.software #= levels.testBit(3)
          priv.int.m.timer #= levels.testBit(7)
          priv.int.m.external #= levels.testBit(11)
          if (levels != irqLevels) external(cycle, "pins", ujson.Obj("levels" -> Hex(levels)))
          if (levels != irqLevels) { events += ((cycle, () => writer.foreach(_.irq(cycle, levels)))); irqLevels = levels }
          if (tap.fire.toBoolean) traps.enqueue((tap.epc.toBigInt, tap.tval.toBigInt))
          mailbox.foreach(_.tick(cycle))
          for (w <- tap.walk; capture <- walkCapture) {
            if (w.start.toBoolean) capture.start(w.va.toBigInt, w.read.toBoolean, w.write.toBoolean,
              w.execute.toBoolean, w.rootPpn.toBigInt)
            if (w.pteRsp.toBoolean) capture.response(w.pteData.toBigInt, w.pteError.toBoolean)
            if (w.pteCmd.toBoolean) capture.command(w.pteAddress.toBigInt)
            if (w.done.toBoolean) capture.done(cycle, w.pageFault.toBoolean, w.accessFault.toBoolean, w.address.toBigInt)
          }

          l1.tick(cycle)
          ibusOpt.foreach { ibus =>
            if (ibus.cmd.valid.toBoolean && ibus.cmd.ready.toBoolean) {
              val addr = ibus.cmd.address.toLong & ~(ibytes - 1L)
              fetch.accept(cycle, read(addr, ibytes), !inRam(addr, ibytes), ibus.cmd.id.toInt)
            }
          }
          if (dbus.cmd.valid.toBoolean && dbus.cmd.ready.toBoolean) {
            val cmd = dbus.cmd
            for (va <- tap.lsuVirtualAddress if cmd.fromHart.toBoolean && !cmd.io.toBoolean) {
              val id = cmd.uopId.toLong
              val physical = cmd.address.toLong
              val virtual = va.toBigInt.toLong // XLEN bits; toLong refuses 64-bit signals
              loadAddresses(id & 15) = (physical, virtual)
              storeAddresses(id) = (physical, virtual)
              lastVirtual(physical) = virtual
              if (physical != virtual) translatedAddresses += ujson.Obj(
                "cycle" -> RvwJson.num(cycle), "uop_id" -> RvwJson.num(id),
                "virtual" -> Hex(BigInt(virtual) & ((BigInt(1) << xlen) - 1)), "physical" -> Hex(BigInt(physical)))
            }
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
            if (live.exists(_.contains(cmd.address.toLong, width))) {
              require(!atomic, "device atomics are unsupported")
              if (cmd.write.toBoolean) live.get.write(cmd.address.toLong, width, (cmd.data.toBigInt >> shift) & fieldMask)
              val result = if (cmd.write.toBoolean) BigInt(0) else live.get.read(cmd.address.toLong, width) << shift
              lsu.accept(cycle, result, false, cmd.id.toInt)
            } else if (devices.exists(_.contains(cmd.address.toLong, width))) {
              require(!atomic, "device atomics are unsupported")
              if (cmd.write.toBoolean) devices.get.write(cmd.address.toLong, width, (cmd.data.toBigInt >> shift) & fieldMask) // the bus replicates narrow data across lanes
              val result = if (cmd.write.toBoolean) BigInt(0) else devices.get.read(cmd.address.toLong, width) << shift
              if (devices.get.isPlic(cmd.address.toLong, width)) external(cycle, "mmio", ujson.Obj(
                "address" -> Hex(BigInt(cmd.address.toLong)), "bytes" -> width, "write" -> cmd.write.toBoolean,
                "value" -> Hex(if (cmd.write.toBoolean) (cmd.data.toBigInt >> shift) & fieldMask else result >> shift)))
              lsu.accept(cycle, result, false, cmd.id.toInt)
            } else {
              lsu.accept(cycle, if (atomic || !cmd.write.toBoolean) old else BigInt(0), !ok, cmd.id.toInt, scMiss)
            }
          }
          ibusOpt.foreach { ibus =>
            fetch.next(cycle) match {
              case Some((d, e, id, _)) => ibus.rsp.valid #= true; ibus.rsp.word #= d; ibus.rsp.error #= e; ibus.rsp.id #= id
              case None => ibus.rsp.valid #= false
            }
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
            lastRetiredPc = Some(r.pc); lastRetiredMode = Some(r.mode); retiredByMode(r.mode) += 1
            val faulted = if (sys.env.get("RVW_COSIM_FAULT_ORDER").contains(r.order.toString)) {
              require(r.rd != 0, "fault target must write a GPR")
              r.copy(rdWdata = r.rdWdata ^ 1)
            } else r
            // Walks that ended by this retirement's cycle go on it (C2 `mmu_walks`).
            val walks = walkCapture.map(_.due(r.cycle)).getOrElse(Nil)
            val sampled = if (walks.isEmpty) faulted else faulted.copy(extra = Seq("mmu_walks" -> ujson.Arr.from(walks)))
            events += ((r.cycle, () => writer.foreach(_.write(sampled))))
          },
          (c, cause, tval, intr) => {
            if (intr) external(c, "taken", ujson.Obj("cause" -> Hex(cause)))
            events += ((c, () => writer.foreach(_.trap(c, cause, tval, intr))))
          },
          (addr, sizeLog2, data) => {
            bench.foreach(_.onStore(addr, sizeLog2, data))
            for (m <- mailbox; (step, _) <- stimulusWords if addr == BigInt(step) && sizeLog2 == 3) m.request(ctl.cycle, data)
            if (!job.config.endsWith("_linux")) tohost.onStore(addr, sizeLog2, data) match {
              case Some(ToHost.Pass) => finish = Some((Status.Pass, None, None))
              case Some(f: ToHost.Fail) => finish = Some((Status.Fail, Some(f.code), Some(s"tohost = ${Hex(f.raw)}")))
              case None =>
            }
          }, if (tap.lsuVirtualAddress.nonEmpty) logicalAddress else (_, _, address) => address)
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
    // A passing program that skipped mailbox events did not run the declared stimulus.
    val (finalStatus, finalMessage) = mailbox.filter(m => status == Status.Pass && !m.complete)
      .map(m => (Status.Error, Some(s"stimulus served ${m.served} of its events"))).getOrElse((status, message))
    RunOutcome(finalStatus, cycles, retired, code, finalMessage,
      ujson.Obj("traps" -> RvwJson.num(if (backend == null) 0L else backend.traps), "rvfi_records" -> RvwJson.num(retired),
        "completion" -> (if (job.config.endsWith("_linux")) "bounded" else "tohost"),
        "tohost" -> (if (job.config.endsWith("_linux")) ujson.Null else ujson.Str(Hex(tohost.value))), "rvfi_monitor" -> false, "memory_bytes" -> RvwJson.num(ramSize),
        "retired_by_mode" -> ujson.Obj.from(retiredByMode.indices.map(i => i.toString -> RvwJson.num(retiredByMode(i)))),
        "last_retired_pc" -> lastRetiredPc.map(v => ujson.Str(Hex(v))).getOrElse(ujson.Null),
        "last_retired_mode" -> lastRetiredMode.map(v => ujson.Num(v)).getOrElse(ujson.Null),
        "device_output" -> live.map(_.outputs).getOrElse(ujson.Obj()),
        "commit_source" -> "VexiiRiscvProbe", "translated_addresses" -> ujson.Arr.from(translatedAddresses),
        "mmu_walks" -> RvwJson.num(walkCapture.map(_.walks.toLong).getOrElse(0L)),
        "mmu_walks_unattached" -> RvwJson.num(walkCapture.map(_.undelivered.toLong).getOrElse(0L)),
        "stimulus_served" -> RvwJson.num(mailbox.map(_.served.toLong).getOrElse(0L))), metrics)
  }
}

object Main {
  def main(args: Array[String]): Unit = new Driver(new VexiiAdapter(sys.env.getOrElse("RVW_VEX_XLEN", "32").toInt)).main(args)
}
