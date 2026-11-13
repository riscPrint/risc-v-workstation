package rvwsmp

import java.io.File
import spinal.core._
import spinal.core.sim._
import riscvsim._
import vexiiriscv.execute.lsu.LsuCachelessPlugin
import vexiiriscv.fetch.FetchCachelessPlugin
import vexiiriscv.misc.PrivilegedPlugin
import vexiiriscv.test.VexiiRiscvProbe
import scala.collection.mutable

/** Cacheless RTL harts. RAM, atomic memory service and devices are simulation models. */
object SmpAdapter extends CoreAdapter {
  type Model = SimCompiled[SmpTop]
  override def freshInstancePerRun = true
  def core = "smp"
  def configs = VexiiTop.configs
  def xlen = 64
  def isa(config: String) = "rv64ima_zicsr_zifencei"
  override def hartIds(config: String) = 0 until VexiiTop.count(config)
  def sourceDir = new File(sys.env("VEXIIRISCV")).getCanonicalFile
  override def replayEnv = Seq("VEXIIRISCV" -> sourceDir.getPath, "RVW_VEX_LOCK" -> "vex-mem") ++
    Seq("RVW_SMP_MAX_DELAY", "RVW_SMP_READY_PERCENT", "RVW_SMP_CLOCK_PERCENT")
      .flatMap(name => sys.env.get(name).map(name -> _))
  private def report(key: ModelKey, work: File) = RiscvSimConfig.elaborate(key, work,
    VexiiTop.spinalConfig, sourceRoots = Seq(new File(sourceDir, "src/main/scala")))(new SmpTop(key.config))
  override def elaborate(key: ModelKey, work: File) = report(key, work).generatedSourcesPaths.toSeq.map(new File(_))
  def compile(key: ModelKey, work: File, cache: File): Model =
    RiscvSimConfig(key, work, cache, VexiiTop.spinalConfig).compile(report(key, work))
  override def generatedVerilog(model: Model) = Option(new File(model.compiledPath, "rtl").listFiles()).toSeq.flatten
    .filter(f => f.getName.endsWith(".v") || f.getName.endsWith(".sv"))

  def run(model: Model, job: RunJob, ctx: RunContext): RunOutcome = {
    require(job.hartImages.nonEmpty && job.rvfiTrace, "SMP requires --hart-images and --rvfi-trace")
    require(!job.rvfiCheck && !job.konata && job.irqSchedule.isEmpty && job.socMap.isEmpty,
      "unsupported monitor, Konata, IRQ schedule or SoC map")
    def setting(name: String, default: Int, min: Int, max: Int): Int = {
      val value = sys.env.get(name).map(_.toInt).getOrElse(default)
      require(value >= min && value <= max, s"$name must be $min..$max")
      value
    }
    val maxDelay = setting("RVW_SMP_MAX_DELAY", 3, 0, 1024)
    val readyPercent = setting("RVW_SMP_READY_PERCENT", 100, 1, 100)
    val clockPercent = setting("RVW_SMP_CLOCK_PERCENT", 100, 1, 100)
    val ids = hartIds(job.config)
    val clockStalls = Array.fill(ids.size)(0L)
    val hsmMode = job.config == "hsm2"
    val serialized = job.config == "serial2"
    val commonBoot = serialized || hsmMode
    var memoryOwner = Option.empty[Int]
    val images = ctx.hartImages.get
    val lifecycle = if(hsmMode) Some(new HartLifecycleObserver(ids.toSet, Set(0), 20000,
      "bounded service in the captured seed; no reset or power gating")) else None
    val hsmSymbols = if(hsmMode) Seq("hsm_start_request", "supervisor1", "hsm_stop_request", "hsm_stopped")
      .map(name => name -> BigInt(ctx.elf.symbol(name).getOrElse(throw new IllegalArgumentException(s"missing $name")))).toMap
      else Map.empty[String, BigInt]
    var starts, stops, entered, parked, ipis = 0

    images.harts.foreach { case (h, elf) => require(elf.entry == 0x80000000L + (if(commonBoot) 0L else h*0x20000L), "entry must match hart reset vector") }
    val memory = mutable.LongMap.empty[Int]
    def inRam(a: Long, n: Int) = a >= 0x80000000L && a+n <= 0x82000000L
    ctx.loadMemory { (a, bytes) =>
      require(inRam(a, bytes.length), "ELF outside shared RAM")
      bytes.indices.foreach(i => memory(a+i) = bytes(i)&255)
    }
    def read(a: Long, n: Int): BigInt = (0 until n).foldLeft(BigInt(0))((v,i) => v | (BigInt(memory.getOrElse(a+i,0)) << (8*i)))
    def write(a: Long, n: Int, data: BigInt, mask: Int): Unit = {
      for(i <- 0 until n if (mask & (1 << i)) != 0) memory(a+i) = ((data >> (8*i))&255).toInt
    }
    val host = images.harts.map { case (h,e) => h -> new ToHost(ToHost.find(e).get + (if(commonBoot) h*8 else 0), 8) }.toMap
    val done = mutable.Map.empty[Int, Status]
    val reservations = mutable.Map.empty[Int, (Long, Int)]
    val backends = mutable.ArrayBuffer.empty[C2Backend]
    val events = mutable.ArrayBuffer.empty[(Long, () => Unit)]
    val header = ujson.Obj.from(ctx.rvfiHeader.value.toSeq ++ Seq("hart_images" -> images.identity,
      "memory_dependencies" -> ujson.Str("unavailable"), "memory_addresses" -> ujson.Str("physical")))
    if(serialized) header("memory_profile") = "serialized-retirement"
    val trace = new MultiHartTrace(new File(job.out,"rvfi.jsonl"), header, ids)
    ids.foreach(trace.reset(_,0))
    var cycle = 0L
    val result = try SimSession.run(model, job, ctx) { (top, ctl) =>
      val cd = top.clockDomain
      top.enables #= (BigInt(1) << ids.size)-1
      val random = new scala.util.Random(job.seed)
      def selected(percent: Int): Boolean = percent == 100 || random.nextInt(100) < percent
      val devices = new Devices(ids.size)
      val privs = top.cores.map(_.host[PrivilegedPlugin].logic)
      case class Response(due: Long, data: BigInt, error: Boolean, id: Int, miss: Boolean = false)
      val fetchQueues = ids.map(_ => mutable.Queue.empty[Response])
      val dataQueues = ids.map(_ => mutable.Queue.empty[Response])
      val fetchDriven = Array.fill(ids.size)(false)
      val dataDriven = Array.fill(ids.size)(false)
      def delay(): Long = job.memLatency.map(_.toLong).getOrElse(random.nextInt(maxDelay+1).toLong)
      val traps = ids.map(_ => mutable.Queue.empty[(BigInt,BigInt)])
      val irqLevels = Array.fill(ids.size)(BigInt(0))
      // Sample trap values before the upstream probe can report that trap.
      cd.onSamplings {
        for(h <- ids) {
          val tap = top.cores(h).host[TrapTapPlugin].logic
          if(top.enables.toBigInt.testBit(h) && tap.fire.toBoolean) traps(h).enqueue((tap.epc.toBigInt,tap.tval.toBigInt))
        }
      }
      for(h <- ids) {
        val dut = top.cores(h)
        val p = privs(h)
        top.ports.timer(h) #= false; top.ports.software(h) #= false; top.ports.external(h) #= false
        top.ports.time(h) #= 0
        val ib = top.ports.fetch(h)
        val db = top.ports.lsu(h)
        ib.cmd.ready #= false; ib.rsp.valid #= false
        db.cmd.ready #= false; db.rsp.valid #= false; db.rsp.scMiss #= false
        val tap = dut.host[TrapTapPlugin].logic
        val backend = new C2Backend(64, () => ctl.cycle, () => tap.privilege.toInt,
          () => traps(h).dequeue(),
          r => events += ((r.cycle, () => trace.retire(h,r))),
          (c,cause,tval,intr) => events += ((c, () => trace.trap(h,c,cause,tval,intr))),
          (a,s,d) => host(h).onStore(a,s,d).foreach {
            case ToHost.Pass => done(h) = Status.Pass
            case _: ToHost.Fail => done(h) = Status.Fail
          }, r => {
            val failedSc = (r.insn & 0x7f) == 0x2f && (r.insn >> 27) == 3
            if(serialized && (r.memRmask != 0 || r.memWmask != 0 || failedSc)) {
              require(memoryOwner.contains(h), "retired memory operation without bus ownership")
              memoryOwner = None
            }
            lifecycle.foreach { observer =>
              if(hsmSymbols.get("hsm_start_request").contains(r.pc)) {
                require(h == 0 && r.mode == 3, "HSM start service must run on hart 0 in M mode")
                observer.start(h, 1, backends(h).regs(11), backends(h).regs(12), r.cycle); starts += 1
              }
              if(hsmSymbols.get("supervisor1").contains(r.pc)) {
                require(h == 1 && r.mode == 1, "HSM entry must retire in S mode on hart 1")
                observer.started(h, r.pc, backends(h).regs(11), r.cycle); entered += 1
              }
              if(hsmSymbols.get("hsm_stop_request").contains(r.pc)) {
                observer.stop(h, r.cycle); stops += 1
              }
              if(hsmSymbols.get("hsm_stopped").contains(r.pc)) {
                observer.stopped(h, r.cycle); parked += 1
              }
            }
          })
        backends += backend
        val probe = new VexiiRiscvProbe(dut, None, withRvls = false)
        probe.checkLiveness = false; probe.trace = false; probe.add(backend)
      }
      cd.forkStimulus(10)
      cd.onSamplings {
        cycle = ctl.cycle + 1
        devices.time += 1
        val enabled = top.enables.toBigInt
        for(h <- random.shuffle(ids.toList)) {
          val dut = top.cores(h)
          val p = privs(h)
          top.ports.time(h) #= devices.time
          top.ports.external(h) #= devices.external(h)
          top.ports.software(h) #= devices.msip(h)
          top.ports.timer(h) #= (devices.time >= devices.compare(h))
          val ib = top.ports.fetch(h)
          val db = top.ports.lsu(h)
          val iq = fetchQueues(h); val dq = dataQueues(h)
          if(!enabled.testBit(h)) clockStalls(h) += 1
          if(fetchDriven(h) && enabled.testBit(h)) { iq.dequeue(); fetchDriven(h)=false }
          if(dataDriven(h) && enabled.testBit(h)) { dq.dequeue(); dataDriven(h)=false }
          if(enabled.testBit(h) && ib.cmd.valid.toBoolean && ib.cmd.ready.toBoolean) {
            val n = ib.p.dataWidth/8; val a = ib.cmd.address.toLong & ~(n-1L)
            iq.enqueue(Response(cycle+delay(), read(a,n), !inRam(a,n), ib.cmd.id.toInt))
          }
          if(enabled.testBit(h) && db.cmd.valid.toBoolean && db.cmd.ready.toBoolean) {
            if(serialized) {
              require(memoryOwner.isEmpty, "overlapping serialized memory service")
              memoryOwner = Some(h)
            }
            val c = db.cmd; val n = db.p.dataWidth/8; val a = c.address.toLong
            val aligned = a & ~(n-1L); val lane = (a-aligned).toInt
            val size = 1 << c.size.toInt
            val atomic = c.amoEnable.toBoolean
            val op = if(atomic) c.amoOp.toInt else -1
            val old = read(aligned,n)
            var response = old; var miss = false
            val ok = inRam(aligned,n) || devices.contains(a)
            if(atomic) {
              require(inRam(a,size), "atomic outside RAM")
              val mask = (BigInt(1) << (size*8))-1
              val before = read(a,size); val operand = (c.data.toBigInt >> (8*lane)) & mask
              def signed(v: BigInt) = if(v.testBit(size*8-1)) v-(BigInt(1) << (size*8)) else v
              if(op == 2) reservations(h) = (a,size)
              else {
                miss = op == 3 && !reservations.get(h).contains((a,size))
                if(op == 3) reservations.remove(h)
                if(!miss) {
                  val value = op match {
                    case 3 | 1 => operand
                    case 0 => before+operand
                    case 4 => before ^ operand
                    case 12 => before & operand
                    case 8 => before | operand
                    case 16 => if(signed(before)<signed(operand)) before else operand
                    case 20 => if(signed(before)>signed(operand)) before else operand
                    case 24 => before.min(operand)
                    case 28 => before.max(operand)
                    case _ => throw new IllegalArgumentException("unknown AMO")
                  }
                  write(a,size,value,(1 << size)-1)
                  reservations.filterInPlace { case (_, (r,s)) => r+s<=a || a+size<=r }
                }
              }
            } else if(c.write.toBoolean && ok) {
              if(inRam(aligned,n)) {
                write(aligned,n,c.data.toBigInt,c.mask.toInt)
                reservations.filterInPlace { case (_, (r,s)) => r+s<=aligned || aligned+n<=r }
              } else {
                val data = c.data.toBigInt >> (8*lane)
                devices.write(a,data,size)
                if(a >= 0x2000000L && a < 0x2000000L+4*ids.size) lifecycle.foreach { observer =>
                  val target = ((a-0x2000000L)/4).toInt
                  if(data.testBit(0)) { observer.sendIpi(h, Set(target), ctl.cycle); ipis += 1 }
                  else observer.clearIpi(target, ctl.cycle)
                }
              }
            } else if(!inRam(aligned,n)) response = (if(devices.contains(a)) devices.read(a,size) else BigInt(0)) << (8*lane)
            dq.enqueue(Response(cycle+delay(),response,!ok,c.id.toInt,miss))
          }
          iq.headOption.filter(_.due<=cycle) match {
            case Some(r) => ib.rsp.valid #= true; ib.rsp.word #= r.data; ib.rsp.error #= r.error; ib.rsp.id #= r.id; fetchDriven(h)=true
            case None => ib.rsp.valid #= false
          }
          dq.headOption.filter(_.due<=cycle) match {
            case Some(r) => db.rsp.valid #= true; db.rsp.data #= r.data; db.rsp.error #= r.error; db.rsp.id #= r.id; db.rsp.scMiss #= r.miss; dataDriven(h)=true
            case None => db.rsp.valid #= false
          }
          // Ready and clock enables change only after every probe sampled this edge.
        }
        for(h <- ids) {
          top.ports.software(h) #= devices.msip(h)
          top.ports.timer(h) #= (devices.time >= devices.compare(h))
          top.ports.external(h) #= devices.external(h)
        }
        lifecycle.foreach(_.check(ctl.cycle))
      }
      fork {
        while(true) {
          cd.waitSampling(); sleep(1)
          for(h <- ids) {
            val levels = (if(top.ports.software(h).toBoolean) BigInt(8) else BigInt(0)) |
              (if(top.ports.timer(h).toBoolean) BigInt(128) else BigInt(0)) |
              (if(top.ports.external(h).toBoolean) BigInt(2048) else BigInt(0))
            if(levels != irqLevels(h)) {
              val c = ctl.cycle
              events += ((c, () => trace.irq(h,c,levels))); irqLevels(h) = levels
            }
            lifecycle.foreach(_.observeIpi(h, top.ports.software(h).toBoolean, ctl.cycle))
          }
          for(h <- ids if done.contains(h)) backends(h).drain()
          val watermark = backends.flatMap(_.pendingCycle).minOption.getOrElse(Long.MaxValue)
          val ready = events.filter(_._1 <= watermark).sortBy(_._1).toVector
          events.filterInPlace(_._1 > watermark)
          ready.foreach(_._2())
          val nextEnables = ids.foldLeft(BigInt(0)) { (bits,h) =>
            if(selected(clockPercent)) bits.setBit(h) else bits
          }
          top.enables #= nextEnables
          for(h <- ids) {
            top.ports.fetch(h).cmd.ready #= (nextEnables.testBit(h) && !done.contains(h) && selected(readyPercent))
            top.ports.lsu(h).cmd.ready #= (!serialized && nextEnables.testBit(h) && !done.contains(h) && selected(readyPercent))
          }
          if(serialized && memoryOwner.isEmpty) {
            val candidates = ids.filter(h => nextEnables.testBit(h) && !done.contains(h) && selected(readyPercent))
            if(candidates.nonEmpty) top.ports.lsu(candidates(random.nextInt(candidates.size))).cmd.ready #= true
          }
          if(done.size == ids.size) ctl.finish(if(done.values.forall(_ == Status.Pass)) Status.Pass else Status.Fail)
          ctl.tick()
        }
      }
      cd.waitSamplingWhere(false)
    } finally { () }
    backends.foreach(_.drain())
    events.sortBy(_._1).foreach(_._2())
    ids.foreach(h => trace.complete(h,result._4,done.getOrElse(h,result._1)))
    if(result._1 == Status.Pass) lifecycle.foreach { observer =>
      observer.finish(result._4, Map(0 -> "started", 1 -> "started"))
      require(starts == 2 && entered == 2 && stops == 1 && parked == 1 && ipis == 2,
        "HSM campaign did not observe both starts, stop and both IPIs")
    }
    val aggregate = trace.outcome(result._4, backends.map(_.retired).sum)
    trace.close()
    val details = aggregate.details
    details("memory_dependencies") = "unavailable"
    details("memory_service") = "simulation"
    details("cache_coherence") = "not_present"
    details("timing") = ujson.Obj("seed" -> job.seed, "random_max_delay" -> maxDelay,
      "ready_percent" -> readyPercent, "clock_enable_percent" -> clockPercent,
      "fixed_latency" -> job.memLatency.map(v => ujson.Num(v)).getOrElse(ujson.Null),
      "base_sample_edges" -> RvwJson.num(cycle),
      "clock_stall_edges" -> ujson.Obj.from(ids.map(h => h.toString -> RvwJson.num(clockStalls(h)))))
    if(hsmMode) details("hsm") = ujson.Obj("starts" -> starts, "entries" -> entered,
      "stops" -> stops, "stopped" -> parked, "ipis" -> ipis, "scope" -> "SBI software lifecycle; no clock/reset/power gating")
    RunOutcome(result._1,result._4,backends.map(_.retired).sum,message=result._3,details=details)
  }
}
object Main { def main(args: Array[String]): Unit = new Driver(SmpAdapter).main(args) }
