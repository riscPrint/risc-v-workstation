package ooomini

import java.io.File
import spinal.core._
import spinal.core.sim._
import spinalprobes.Probe
import spinalchecks._
import riscvsim._

object Adapter extends CoreAdapter {
  type Model = SimCompiled[Core]
  def core = "ooo-mini"
  def configs = Seq("default", "rob16", "iq4", "sq4", "predictor4")
  def isa(config: String) = "rv32im_zicsr_zifencei"
  def xlen = 32
  def sourceDir = new File(sys.env("OOO_MINI_SOURCE"))
  override def freshInstancePerRun = true
  override def supportsProbes = true
  override def irqInputMask: BigInt = 0x888
  override def replayEnv = Seq("OOO_MINI_SOURCE" -> sourceDir.getPath) ++
    Seq("OOO_MINI_DEVICE_MAP","RVW_DEVICE_LIBRARY").flatMap(name => sys.env.get(name).map(name -> _))
  def report(key: ModelKey, work: File) = Probe.enabled(key.probes) {
    val (config,_) = SpinalChecks.install(SpinalConfig(defaultConfigForClockDomains = ClockDomainConfig(resetKind = SYNC)),
      ChecksConfig(mode = Mode.Monitor,enable = Seq("ooo.*","queue.*","freelist.*","execution.*")))
    RiscvSimConfig.elaborate(key, work, config)(new Core(if(key.config == "rob16") 16 else 8,
      issueEntries = (if(key.config == "iq4") 4 else 8),
      storeEntries = (if(key.config == "sq4") 4 else 8),
      predictorEntries = (if(key.config == "predictor4") 4 else 16)))
  }
  def compile(key: ModelKey, work: File, cache: File): Model = {
    val rtl = report(key,work)
    val config = RiscvSimConfig(key, work, cache, SpinalConfig())
    if(key.config == "default") {
      import scala.sys.process._
      val bindings = new File(work,key.name + "-bindings")
      val command = Seq(new File(sys.env("RVW_HOME"),"rvw/.venv/bin/rvw").getPath,
        "checks","generate","--all","--project",sourceDir.getPath,"--out",bindings.getAbsolutePath)
      val output = new StringBuilder
      val exit = Process(command).!(ProcessLogger(line => output.append(line).append('\n')))
      require(exit == 0,s"check binding generation failed: $output")
      config.addRtl(new File(bindings,"queues/monitors.sv").getAbsolutePath)
      config.addRtl(new File(bindings,"queues/binds.sv").getAbsolutePath)
      config.addSimulatorFlag("--assert")
    }
    config.compile(rtl)
  }
  override def elaborate(key: ModelKey, work: File): Seq[File] =
    report(key,work).generatedSourcesPaths.toSeq.map(new File(_))
  override def generatedVerilog(model: Model): Seq[File] = model.report.generatedSourcesPaths.toSeq.map(new File(_))
  def run(model: Model, job: RunJob, ctx: RunContext): RunOutcome = {
    require(!job.konata && !job.rvfiCheck,
      "use probe conversion for Kanata; runtime RVFI monitor is not mapped")
    require(job.memLatency.forall(_ == 0), "only zero-latency RAM is mapped")
    require(!sys.env.contains("RVW_COSIM_PORT") || job.rvfiTrace,"live comparison needs --rvfi-trace")
    val devices = sys.env.get("OOO_MINI_DEVICE_MAP").map(path =>
      new ProjectDevices(new File(path),new File(sys.env("RVW_DEVICE_LIBRARY")),job.seed))
    val external = devices.flatMap(_.plicEvidence)
    require(external.isEmpty || job.irqSchedule.isEmpty,"PLIC evidence uses device-driven pins")
    val ram = scala.collection.mutable.LongMap.empty[Int]
    ctx.loadMemory { (base,bytes) => bytes.indices.foreach(i => ram(base+i) = bytes(i) & 255) }
    def word(addr: Long): BigInt = (0 until 4).foldLeft(BigInt(0))((v,i) => v | BigInt(ram.getOrElse(addr+i,0)) << (8*i))
    val host = new ToHost(ToHost.find(ctx.elf).getOrElse(throw new IllegalArgumentException("ELF requires tohost")),4)
    var outcome = RunOutcome(Status.Timeout,0,0)
    var cycle = 0L
    var retired = 0L
    var firstSample = -1L
    try model.doSim(job.out.getAbsolutePath,job.seed) { dut =>
      dut.io.boot #= ctx.elf.entry
      dut.io.interrupts #= 0; dut.io.accessDevice #= false
      dut.io.instruction #= 0; dut.io.loadData #= 0
      dut.clockDomain.forkStimulus(10)
      dut.clockDomain.waitSampling()
      if(job.wave && job.waveFrom.exists(_ > 0)) disableSimWave()
      val control = new SimControl(job,ctx.wallClock)
      dut.clockDomain.onSamplings { control.cycle += 1 }
      FaultInjector.forJob(job).foreach(_.attach(dut,control))
      val rvfi = new RvfiProbe(Seq(dut.io.retire))
      val live = sys.env.get("RVW_COSIM_PORT").map(port => new Lockstep(port.toInt))
      val header = ujson.Obj.from(ctx.rvfiHeader.value.toSeq ++ external.toSeq.map(e => "external_interrupts" -> e))
      val writer = if(job.rvfiTrace) Some(new RvfiTraceWriter(new File(job.out,"rvfi.jsonl"),header,
        observe = live.map(client => (line: String) => client.observe(line)))) else None
      val probes = ProbeCollector.open(Probe.of(dut),job,ctx.rvfiHeader)
      def evidence(kind: String, fields: ujson.Obj): Unit =
        if(external.nonEmpty) writer.foreach(_.externalInterrupt(cycle,kind,fields))
      var previousLevels = BigInt(-1)
      var stop = false
      try {
        while(cycle < job.maxCycles && !stop && !ctx.wallClock.over()) {
          dut.clockDomain.waitFallingEdge()
          if(job.wave) {
            if(job.waveFrom.contains(cycle)) enableSimWave()
            if(job.waveTo.exists(cycle > _)) disableSimWave()
          }
          val deviceLevels = devices.map(_.tick(cycle)).getOrElse(BigInt(0))
          val levels = job.irqSchedule.map(_.levelsAt(cycle)).getOrElse(deviceLevels)
          require((levels & ~BigInt(0x888)) == 0,"unsupported interrupt pin")
          dut.io.interrupts #= levels
          val levelsChanged = levels != previousLevels
          if(levelsChanged) {
            writer.foreach(_.irq(cycle,levels))
            evidence("pins",ujson.Obj("levels" -> Hex(levels)))
            previousLevels = levels
          }
          dut.io.instruction #= word(dut.io.fetch.toLong)
          sleep(1)
          val bytes = dut.io.loadBytes.toInt
          dut.io.accessDevice #= devices.exists(_.contains(dut.io.accessAddress.toLong,bytes))
          sleep(1)
          val loadAddress = dut.io.loadAddress.toLong
          val deviceRead = dut.io.load.toBoolean && devices.exists(_.contains(loadAddress,bytes))
          val load = if(deviceRead) devices.get.read(loadAddress,bytes) else word(loadAddress)
          dut.io.loadData #= load
          if(deviceRead && devices.get.isPlic(loadAddress,bytes))
            evidence("mmio",ujson.Obj("address" -> Hex(BigInt(loadAddress)),"value" -> Hex(load),"bytes" -> bytes,"write" -> false))
          sleep(1)
          if(dut.io.interruptTaken.toBoolean) {
            val cause = dut.io.interruptCause.toBigInt
            evidence("taken",ujson.Obj("cause" -> Hex(cause)))
            writer.foreach(_.trap(cycle,cause,BigInt(0),true))
          }
          if(firstSample < 0) firstSample = simTime()
          val records = rvfi.sample(cycle)
          val store = dut.io.store.toBoolean
          val addr = dut.io.storeAddress.toLong
          val mask = dut.io.storeMask.toInt
          val data = dut.io.storeData.toBigInt
          val storeBytes = Integer.bitCount(mask)
          val deviceWrite = store && devices.exists(_.contains(addr,storeBytes))
          // MMIO acceptance and C2 describe the same firing edge. Report acceptance
          // before the matching retirement, then advance the RTL clock.
          if(deviceWrite) {
            require(Set(1,3,15)(mask),"device stores need a contiguous byte mask")
            val value = data & ((BigInt(1) << (8*storeBytes))-1)
            devices.get.write(addr,storeBytes,value)
            if(devices.get.isPlic(addr,storeBytes)) evidence("mmio",ujson.Obj(
              "address" -> Hex(BigInt(addr)),"value" -> Hex(value),"bytes" -> storeBytes,"write" -> true))
          }
          probes.foreach(_.sample(cycle))
          records.foreach { r => writer.foreach(_.write(r)); if(!r.trap) retired += 1 }
          dut.clockDomain.waitRisingEdge()
          if(store && !deviceWrite) for(i <- 0 until 4 if (mask & (1 << i)) != 0) {
            ram(addr+i) = ((data >> (8*i)) & 255).toInt
            host.onStore(BigInt(addr+i),0,((data >> (8*i)) & 255) << (8*((addr+i)%4).toInt)).foreach {
              case ToHost.Pass => outcome = RunOutcome(Status.Pass,cycle+1,retired); stop = true
              case ToHost.Fail(code,_,_) => outcome = RunOutcome(Status.Fail,cycle+1,retired,Some(code)); stop = true
            }
          }
          cycle += 1
        }
        if(!stop) outcome = RunOutcome(Status.Timeout,cycle,retired)
        ChecksSim.writeRunReport(dut,new File(job.out,"checks-run.json").getPath)
        outcome = outcome.copy(details = ujson.Obj("generated_sv_bindings" -> (if(job.config == "default") 8 else 0),
          "generated_sv_assertions_enabled" -> (job.config == "default"),"device_plugins" -> devices.nonEmpty,
          "external_interrupt_evidence" -> external.nonEmpty,"socket_lockstep" -> live.nonEmpty,
          "wave_time_per_cycle" -> 10,"wave_time_of_cycle_1" -> (firstSample + 10),
          "wave_window" -> ujson.Obj("from" -> job.waveFrom.map(x => ujson.Num(x)).getOrElse(ujson.Null),
            "to" -> job.waveTo.map(x => ujson.Num(x)).getOrElse(ujson.Null))))
        if(ChecksSim.firings(dut).nonEmpty && outcome.status == Status.Pass)
          outcome = outcome.copy(status = Status.Fail,message = Some("generated check fired"))
        writer.foreach(_.end(cycle,outcome.status.name))
        probes.foreach(_.close(cycle))
      } finally { writer.foreach(_.close()); probes.foreach(_.abandon()); live.foreach(_.close()) }
    } catch {
      case e: spinal.sim.SimFailure => outcome = RunOutcome(Status.Assert,cycle,retired,message = Some(e.getMessage))
    } finally { devices.foreach(_.close()) }
    outcome
  }
}
object Main { def main(args: Array[String]): Unit = new Driver(Adapter).main(args) }
