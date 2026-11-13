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
  def configs = Seq("default", "rob16")
  def isa(config: String) = "rv32im_zicsr_zifencei"
  def xlen = 32
  def sourceDir = new File(sys.env("OOO_MINI_SOURCE"))
  override def freshInstancePerRun = true
  override def supportsProbes = true
  def report(key: ModelKey, work: File) = Probe.enabled(key.probes) {
    val (config,_) = SpinalChecks.install(SpinalConfig(defaultConfigForClockDomains = ClockDomainConfig(resetKind = SYNC)),
      ChecksConfig(mode = Mode.Monitor,enable = Seq("ooo.*","queue.*","freelist.*","execution.*")))
    RiscvSimConfig.elaborate(key, work, config)(new Core(if(key.config == "rob16") 16 else 8))
  }
  def compile(key: ModelKey, work: File, cache: File): Model =
    RiscvSimConfig(key, work, cache, SpinalConfig()).compile(report(key,work))
  override def elaborate(key: ModelKey, work: File): Seq[File] =
    report(key,work).generatedSourcesPaths.toSeq.map(new File(_))
  override def generatedVerilog(model: Model): Seq[File] = model.report.generatedSourcesPaths.toSeq.map(new File(_))
  def run(model: Model, job: RunJob, ctx: RunContext): RunOutcome = {
    require(!job.konata && !job.spinaltrace && job.fault.isEmpty && !job.rvfiCheck,
      "use probe conversion for Kanata; fault and runtime RVFI monitor are not mapped yet")
    require(job.memLatency.forall(_ == 0), "only zero-latency RAM is mapped")
    val ram = scala.collection.mutable.LongMap.empty[Int]
    ctx.loadMemory { (base, bytes) => bytes.indices.foreach(i => ram(base+i) = bytes(i) & 255) }
    def word(addr: Long): BigInt = (0 until 4).foldLeft(BigInt(0))((v,i) => v | BigInt(ram.getOrElse(addr+i,0)) << (8*i))
    val host = new ToHost(ToHost.find(ctx.elf).getOrElse(throw new IllegalArgumentException("ELF requires tohost")),4)
    var outcome = RunOutcome(Status.Timeout,0,0)
    model.doSim(job.out.getAbsolutePath,job.seed) { dut =>
      dut.io.boot #= ctx.elf.entry
      dut.io.instruction #= 0; dut.io.loadData #= 0
      dut.clockDomain.forkStimulus(10)
      dut.clockDomain.waitSampling()
      val rvfi = new RvfiProbe(Seq(dut.io.retire))
      val writer = if(job.rvfiTrace) Some(new RvfiTraceWriter(new File(job.out,"rvfi.jsonl"),ctx.rvfiHeader)) else None
      val probes = ProbeCollector.open(Probe.of(dut),job,ctx.rvfiHeader)
      var cycle = 0L; var retired = 0L; var stop = false
      try {
        while(cycle < job.maxCycles && !stop && !ctx.wallClock.over()) {
          dut.clockDomain.waitFallingEdge()
          dut.io.instruction #= word(dut.io.fetch.toLong)
          sleep(1)
          dut.io.loadData #= word(dut.io.loadAddress.toLong)
          sleep(1)
          // Sample pre-edge commit signals. Apply stores after the same edge.
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
        if(ChecksSim.firings(dut).nonEmpty && outcome.status == Status.Pass)
          outcome = outcome.copy(status = Status.Fail,message = Some("generated check fired"))
        writer.foreach(_.end(cycle,outcome.status.name))
        probes.foreach(_.close(cycle))
      } finally { writer.foreach(_.close()); probes.foreach(_.abandon()) }
    }
    outcome
  }
}
object Main { def main(args: Array[String]): Unit = new Driver(Adapter).main(args) }
