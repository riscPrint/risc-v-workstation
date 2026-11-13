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
      "use probe conversion for Kanata; runtime RVFI monitor are not mapped yet")
    require(job.memLatency.forall(_ == 0), "only zero-latency RAM is mapped")
    val ram = scala.collection.mutable.LongMap.empty[Int]
    ctx.loadMemory { (base, bytes) => bytes.indices.foreach(i => ram(base+i) = bytes(i) & 255) }
    def word(addr: Long): BigInt = (0 until 4).foldLeft(BigInt(0))((v,i) => v | BigInt(ram.getOrElse(addr+i,0)) << (8*i))
    val host = new ToHost(ToHost.find(ctx.elf).getOrElse(throw new IllegalArgumentException("ELF requires tohost")),4)
    var outcome = RunOutcome(Status.Timeout,0,0)
    var cycle = 0L
    var retired = 0L
    var firstSample = -1L
    try model.doSim(job.out.getAbsolutePath,job.seed) { dut =>
      dut.io.boot #= ctx.elf.entry
      dut.io.interrupts #= 0
      dut.io.instruction #= 0; dut.io.loadData #= 0
      dut.clockDomain.forkStimulus(10)
      dut.clockDomain.waitSampling()
      if(job.wave && job.waveFrom.exists(_ > 0)) disableSimWave()
      val control = new SimControl(job,ctx.wallClock)
      dut.clockDomain.onSamplings { control.cycle += 1 }
      FaultInjector.forJob(job).foreach(_.attach(dut,control))
      val rvfi = new RvfiProbe(Seq(dut.io.retire))
      val writer = if(job.rvfiTrace) Some(new RvfiTraceWriter(new File(job.out,"rvfi.jsonl"),ctx.rvfiHeader)) else None
      val probes = ProbeCollector.open(Probe.of(dut),job,ctx.rvfiHeader)
      var previousLevels = BigInt(-1)
      var stop = false
      try {
        while(cycle < job.maxCycles && !stop && !ctx.wallClock.over()) {
          dut.clockDomain.waitFallingEdge()
          if(job.wave) {
            if(job.waveFrom.contains(cycle)) enableSimWave()
            if(job.waveTo.exists(cycle > _)) disableSimWave()
          }
          val levels = job.irqSchedule.map(_.levelsAt(cycle)).getOrElse(BigInt(0))
          require((levels & ~BigInt(0x888)) == 0,"only machine software, timer and external interrupts are mapped")
          val levelsChanged = levels != previousLevels
          dut.io.interrupts #= levels
          if(levelsChanged) {
            writer.foreach(_.irq(cycle,levels))
            previousLevels = levels
          }
          // Settle an interrupt change before reading the selected load address.
          if(levelsChanged) sleep(1)
          // Both addresses depend on registered core state. The new fetch word
          // cannot change the selected older ROB operation's load address.
          val instruction = word(dut.io.fetch.toLong)
          val loadData = word(dut.io.loadAddress.toLong)
          dut.io.instruction #= instruction
          dut.io.loadData #= loadData
          // Probe rename fields observe the new fetch word. Architectural commit
          // fields are registered and do not depend on these RAM inputs.
          if(job.probes) sleep(1)
          // Sample pre-edge commit signals. Apply stores after the same edge.
          if(dut.io.interruptTaken.toBoolean) {
            val cause = dut.io.interruptCause.toBigInt
            writer.foreach(_.trap(cycle,cause,BigInt(0),true))
          }
          if(firstSample < 0) firstSample = simTime()
          val records = rvfi.sample(cycle)
          val store = dut.io.store.toBoolean
          val addr = dut.io.storeAddress.toLong
          val mask = dut.io.storeMask.toInt
          val data = dut.io.storeData.toBigInt
          probes.foreach(_.sample(cycle))
          records.foreach { r => writer.foreach(_.write(r)); if(!r.trap) retired += 1 }
          dut.clockDomain.waitRisingEdge()
          if(store) {
            for(i <- 0 until 4 if (mask & (1 << i)) != 0) {
              ram(addr+i) = ((data >> (8*i)) & 255).toInt
              host.onStore(BigInt(addr+i),0,((data >> (8*i)) & 255) << (8*((addr+i)%4).toInt)).foreach {
                case ToHost.Pass => outcome = RunOutcome(Status.Pass,cycle+1,retired); stop = true
                case ToHost.Fail(code,_,_) => outcome = RunOutcome(Status.Fail,cycle+1,retired,Some(code)); stop = true
              }
            }
          }
          cycle += 1
        }
        if(!stop) outcome = RunOutcome(Status.Timeout,cycle,retired)
        ChecksSim.writeRunReport(dut,new File(job.out,"checks-run.json").getPath)
        outcome = outcome.copy(details = ujson.Obj("generated_sv_bindings" -> (if(job.config == "default") 8 else 0),
          "generated_sv_assertions_enabled" -> (job.config == "default"),
          // C2 samples before the edge and numbers its first cycle zero.
          "wave_time_per_cycle" -> 10, "wave_time_of_cycle_1" -> (firstSample + 10),
          "wave_window" -> ujson.Obj("from" -> job.waveFrom.map(x => ujson.Num(x)).getOrElse(ujson.Null),
            "to" -> job.waveTo.map(x => ujson.Num(x)).getOrElse(ujson.Null))))
        if(ChecksSim.firings(dut).nonEmpty && outcome.status == Status.Pass)
          outcome = outcome.copy(status = Status.Fail,message = Some("generated check fired"))
        writer.foreach(_.end(cycle,outcome.status.name))
        probes.foreach(_.close(cycle))
      } finally { writer.foreach(_.close()); probes.foreach(_.abandon()) }
    } catch {
      case e: spinal.sim.SimFailure =>
        outcome = RunOutcome(Status.Assert,cycle,retired,message = Some(e.getMessage))
    }
    outcome
  }
}
object Main { def main(args: Array[String]): Unit = new Driver(Adapter).main(args) }
