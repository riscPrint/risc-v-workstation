package rvwvex

import java.io.File
import spinal.core._
import spinal.core.sim._
import riscvsim._
import vexriscv.plugin.RvfiPort
import scala.collection.mutable

object VexAdapter extends CoreAdapter {
  override def freshInstancePerRun = true
  type Model = SimCompiled[VexTop]
  override def irqInputMask: BigInt = 0xA88
  def core = "vexriscv"
  val configs = Seq("rv32im")
  def xlen = 32
  def isa(config: String) = "rv32im_zicsr_zifencei"
  def sourceDir = new File(sys.env("VEXRISCV")).getCanonicalFile
  override def replayEnv = Seq("VEXRISCV" -> sourceDir.getPath)

  private def report(key: ModelKey, work: File): SpinalReport[VexTop] = {
    require(!key.konata, "VexRiscv adapter does not support Konata")
    RiscvSimConfig.elaborate(key, work, VexTop.spinalConfig)(new VexTop)
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
    job.socMap.foreach(m => require(m.regions.forall(_.kind == "ram"), "VexRiscv adapter supports RAM only"))
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
    val writer = if (job.rvfiTrace) Some(new RvfiTraceWriter(new File(job.out, "rvfi.jsonl"), ctx.rvfiHeader)) else None
    var retired = 0L
    var traps = 0L
    var nextOrder = BigInt(0)
    var handler = false
    val (status, code, message, cycles) = try {
      val result = SimSession.run(model, job, ctx) { (dut, ctl) =>
        val cd = dut.clockDomain
        dut.csr.timerInterrupt #= false
        dut.csr.softwareInterrupt #= false
        dut.csr.externalInterrupt #= false
        dut.csr.externalInterruptS #= false
        dut.ibus.cmd.ready #= false
        dut.ibus.rsp.valid #= false
        dut.ibus.rsp.error #= false
        dut.ibus.rsp.inst #= 0
        dut.dbus.cmd.ready #= false
        dut.dbus.rsp.ready #= false
        dut.dbus.rsp.error #= false
        dut.dbus.rsp.data #= 0
        cd.forkStimulus(10)
        // One outstanding response per bus. Fixed latency 0 has no extra wait.
        // Absent --mem-latency uses the recorded simulation seed.
        val random = new scala.util.Random(job.seed)
        def delay(): Long = job.memLatency.map(_.toLong).getOrElse(random.nextInt(4).toLong) + 1L
        fork {
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
              val addr = cmd.address.toLong & ~3L
              val permission = if (cmd.wr.toBoolean) 'w' else 'r'
              val selected = job.socMap.flatMap(_.region(BigInt(addr), 4, permission))
              capture.foreach(_.request(cycle, "dbus", BigInt(addr), 4, cmd.wr.toBoolean, selected))
              val valid = inRam(addr, 4, permission)
              if (cmd.wr.toBoolean) {
                require(valid, f"store outside RAM at 0x$addr%x")
                val data = cmd.data.toBigInt
                for (i <- 0 until 4 if (cmd.mask.toInt & (1 << i)) != 0)
                  memory(addr + i) = ((data >> (8 * i)) & 255).toInt
              } else pending = Some((cycle + delay(), readWord(addr), !valid))
            }
          }
        }
        var irqLevels = BigInt(-1)
        cd.onSamplings {
          ctl.tick()
          val levels = job.irqSchedule.map(_.levelsAt(ctl.cycle)).getOrElse(BigInt(0))
          dut.csr.timerInterrupt #= levels.testBit(7)
          dut.csr.softwareInterrupt #= levels.testBit(3)
          dut.csr.externalInterrupt #= levels.testBit(11)
          dut.csr.externalInterruptS #= levels.testBit(9)
          if (levels != irqLevels) { writer.foreach(_.irq(ctl.cycle, levels)); irqLevels = levels }
          if (dut.traps.valid.toBoolean) {
            traps += 1
            val cause = dut.traps.cause.toBigInt
            writer.foreach(_.trap(ctl.cycle, cause, dut.traps.tval.toBigInt, cause.testBit(31)))
            handler = true
          }
          if (dut.rvfi.valid.toBoolean) {
            val r = record(dut.rvfi, ctl.cycle, handler)
            handler = false
            require(r.order == nextOrder, s"RVFI order ${r.order}, expected $nextOrder")
            nextOrder += 1
            retired += 1
            writer.foreach(_.write(r))
            if (r.memWmask != 0) {
              val lane = Integer.numberOfTrailingZeros(r.memWmask)
              val count = Integer.bitCount(r.memWmask)
              require(Set(1, 2, 4)(count), "unsupported RVFI store mask")
              tohost.onStore(r.memAddr + lane, Integer.numberOfTrailingZeros(count), r.memWdata) match {
                case Some(ToHost.Pass) => ctl.finish(Status.Pass)
                case Some(f: ToHost.Fail) => ctl.finish(Status.Fail, Some(f.code), Some(s"tohost = ${Hex(f.raw)}"))
                case None =>
              }
            }
          }
        }
        cd.waitSamplingWhere(false)
      }
      writer.foreach(_.end(result._4, result._1.name))
      result
    } finally { writer.foreach(_.close()); capture.foreach(_.close()) }
    RunOutcome(status, cycles, retired, code, message,
      ujson.Obj("traps" -> RvwJson.num(traps), "rvfi_records" -> RvwJson.num(retired), "tohost" -> Hex(tohost.value),
        "rvfi_monitor" -> false, "memory_bytes" -> job.socMap.map(m => ujson.Str(m.regions.map(_.size).sum.toString)).getOrElse(ujson.Num(16777216))))
  }
}

object Main {
  def main(args: Array[String]): Unit = new Driver(VexAdapter).main(args)
}
