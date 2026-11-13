package rvwcore

import java.io.File
import spinal.core._
import spinal.core.sim._
import riscvsim._
import scala.collection.mutable

// The mapped adapter for the bring-up check's tiny core. It replaces the rvw init skeleton,
// the step an agent does by hand (docs/AGENT_SETUP.md steps 4 and 5).
object Adapter extends CoreAdapter {
  type Model = SimCompiled[tiny.TinyCore]
  override def freshInstancePerRun = true
  def core: String = "tinycore"
  def configs: Seq[String] = Seq("default")
  def isa(config: String): String = "rv32i"
  def xlen: Int = 32
  def sourceDir: File = new File(sys.env("RVW_CORE_SOURCE"))
  override def replayEnv: Seq[(String, String)] = Seq("RVW_CORE_SOURCE" -> sourceDir.getCanonicalPath)
  // The shared entry in Elaboration.scala (from rvw init) keeps simulation and the database on one RTL.
  private def report(key: ModelKey, work: File) =
    RiscvSimConfig.elaborate(key, work, Elaboration.config, sourceRoots = Seq(new File(sourceDir, "src/main/scala")))(
      Elaboration.top().asInstanceOf[tiny.TinyCore])
  def compile(key: ModelKey, work: File, cache: File): Model =
    RiscvSimConfig(key, work, cache, Elaboration.config).compile(report(key, work))
  override def elaborate(key: ModelKey, work: File): Seq[File] =
    report(key, work).generatedSourcesPaths.toSeq.map(new File(_))
  // Keep the scaffold's RTL identity hook: without it every result is inconclusive.
  override def generatedVerilog(model: Model): Seq[File] =
    Option(new File(model.compiledPath, "rtl").listFiles()).toSeq.flatten
      .filter(f => f.getName.endsWith(".v") || f.getName.endsWith(".sv"))

  def run(model: Model, job: RunJob, ctx: RunContext): RunOutcome = {
    require(ctx.elf.entry == 0x80000000L, "ELF entry must equal reset PC 0x80000000")
    val tohost = new ToHost(ToHost.find(ctx.elf).getOrElse(throw new IllegalArgumentException("ELF has no tohost symbol")), 4)
    val memory = mutable.LongMap.empty[Int]
    ctx.elf.load { (addr, bytes) => bytes.indices.foreach(i => memory(addr + i) = bytes(i) & 255) }
    def word(a: Long): BigInt = (0 until 4).foldLeft(BigInt(0))((v, i) => v | (BigInt(memory.getOrElse((a & ~3L) + i, 0)) << (8 * i)))
    val writer = if (job.rvfiTrace) Some(new RvfiTraceWriter(new File(job.out, "rvfi.jsonl"), ctx.rvfiHeader)) else None
    var retired = 0L
    val (status, code, message, cycles) = try {
      val result = SimSession.run(model, job, ctx) { (dut, ctl) =>
        val cd = dut.clockDomain
        dut.io.mem_rdata #= 0
        cd.forkStimulus(10)
        cd.onSamplings {
          ctl.tick()
          val io = dut.io
          if (io.rvfi_valid.toBoolean) {
            val r = RvfiRecord(io.rvfi_order.toBigInt, ctl.cycle, io.rvfi_insn.toLong, io.rvfi_trap.toBoolean, false, false,
              3, 1, io.rvfi_rs1_addr.toInt, io.rvfi_rs1_rdata.toBigInt, io.rvfi_rs2_addr.toInt, io.rvfi_rs2_rdata.toBigInt,
              io.rvfi_rd_addr.toInt, io.rvfi_rd_wdata.toBigInt, io.rvfi_pc_rdata.toBigInt, io.rvfi_pc_wdata.toBigInt,
              io.rvfi_mem_addr.toBigInt, io.rvfi_mem_rmask.toInt, io.rvfi_mem_wmask.toInt, io.rvfi_mem_rdata.toBigInt,
              io.rvfi_mem_wdata.toBigInt, memFault = false)
            writer.foreach(_.write(r))
            retired += 1
            if (r.trap) ctl.finish(Status.Fail, message = Some(f"illegal instruction at 0x${r.pc}%x"))
            if (r.memWmask != 0) {
              val lane = Integer.numberOfTrailingZeros(r.memWmask)
              val size = Integer.numberOfTrailingZeros(Integer.bitCount(r.memWmask))
              tohost.onStore(r.memAddr + lane, size, r.memWdata) match {
                case Some(ToHost.Pass) => ctl.finish(Status.Pass)
                case Some(f: ToHost.Fail) => ctl.finish(Status.Fail, Some(f.code), Some(s"tohost = ${Hex(f.raw)}"))
                case None =>
              }
            }
          }
          if (io.mem_valid.toBoolean) {
            val a = io.mem_addr.toLong
            if (io.mem_we.toBoolean) {
              val d = io.mem_wdata.toBigInt
              for (i <- 0 until 4 if (io.mem_wmask.toInt & (1 << i)) != 0) memory(a + i) = ((d >> (8 * i)) & 255).toInt
            } else io.mem_rdata #= word(a)
          }
        }
        cd.waitSamplingWhere(false)
      }
      writer.foreach(_.end(result._4, result._1.name))
      result
    } finally writer.foreach(_.close())
    RunOutcome(status, cycles, retired, code, message, ujson.Obj("rvfi_records" -> RvwJson.num(retired)))
  }
}

object Main {
  def main(args: Array[String]): Unit = new Driver(Adapter).main(args)
}
