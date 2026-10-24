package spinalkonata.boom

import spinal.core._
import spinal.core.sim._
import spinal.lib.sim.SparseMemory
import _root_.boom.system.BoomSimTop
import _root_.boom.sim.{BoomSim, BoomMemoryAgent}
import _root_.boom.sim.BoomSim._
import riscvsim.ElfFile

/** Snapshot of BoomSim.run at 0cb0b69, using the generic writer.
  * No hardware/probe changes.
  * This stays in the BOOM adapter, never in the generic library.
  */
object ProbeRun {
  def run(compiled: SimCompiled[BoomSimTop], elf: ElfFile, disassembly: Map[BigInt, (Long, String)], maxCycles: Long = 200000, verbose: Boolean = false,
          seed: Int = scala.util.Random.nextInt(),
          onStore: (BigInt, Int, BigInt) => Unit = (_, _, _) => (),
          onFinish: (Long, Long) => Unit = (_, _) => (),
          konata: Option[java.io.File] = None,
          memLatency: Option[Int] = None): Result = {
    val tohost = elf.symbol("tohost").getOrElse(sys.error("captured ELF has no tohost symbol"))
    var result: Result = Timeout
    compiled.doSim(elf.file.getName, seed) { dut =>
      dut.clockDomain.forkStimulus(10)
      dut.io.interrupts.flatten.foreach { case b: Bool => b #= false; case _ => }

      val mem = SparseMemory(seed = 0)
      elf.load((a, d) => mem.write(a, d))
      val agent = new BoomMemoryAgent(dut.io.mem, dut.clockDomain, mem, memLatency)
      import Platform._
      mem.write(msip, 0)
      mem.write(mtimecmp, -1L)
      mem.write(intGen, 0L)
      def readLong(a: Long): Long = (0 until 8).map(i => (mem.read(a + i).toLong & 0xff) << (8 * i)).reduce(_ | _)
      var mtimeValue = 0L
      mem.write(mtime, mtimeValue)
      if (verbose) agent.monitor.add(new spinal.lib.bus.tilelink.sim.MonitorSubscriber {
        import spinal.lib.bus.tilelink.sim._
        def log(ch: String, t: Any): Unit = println(s"[${simTime()}] TL $ch ${t.toString.replace('\n', ' ').take(160)}")
        override def onA(a: TransactionA) = log("A", a)
        override def onB(b: TransactionB) = log("B", b)
        override def onC(c: TransactionC) = log("C", c)
        override def onD(d: TransactionD) = log("D", d)
        override def onE(e: TransactionE) = log("E", e)
      })

      val tracer = konata.map { f =>
        require(dut.konata != null, "compile with konata = true to write a Konata log")
        new BoomKonataTracer(dut.konata, f, disassembly)
      }

      var done = false
      var tohostWord = BigInt(0)
      var retired = 0L
      dut.clockDomain.onSamplings {
        tracer.foreach(_.sample())
        // mtime counts cycles unless software wrote it
        val stored = readLong(mtime)
        mtimeValue = (if (stored != mtimeValue) stored else mtimeValue) + 1
        mem.write(mtime, mtimeValue)
        dut.io.interrupts.mtip #= java.lang.Long.compareUnsigned(mtimeValue, readLong(mtimecmp)) >= 0
        dut.io.interrupts.msip #= (mem.readInt(msip) & 1) != 0
        dut.io.interrupts.meip #= (mem.readInt(intGen) & 1) != 0
        if (dut.io.interrupts.seip != null) dut.io.interrupts.seip #= (mem.readInt(intGen + 4) & 1) != 0
        for (e <- dut.rvfiErr) if (!done && e.toInt != 0) {
          done = true
          result = RvfiError(e.toInt)
        }
        val addr = if (dut.io.tohost.valid.toBoolean) dut.io.tohost.payload.addr.toBigInt else BigInt(-1)
        if (addr >= 0) onStore(addr, dut.io.tohost.payload.size.toInt, dut.io.tohost.payload.data.toBigInt)
        if (addr >= tohost && addr < tohost + 8) {
          // Merge the stored bytes (StoreGen replicates narrow data across the word)
          val off = (addr - tohost).toInt
          val bytes = 1 << dut.io.tohost.payload.size.toInt
          val data = dut.io.tohost.payload.data.toBigInt
          for (b <- off until (off + bytes min 8)) {
            val byte = (data >> (8 * b)) & 0xff
            tohostWord = (tohostWord & ~(BigInt(0xff) << (8 * b))) | (byte << (8 * b))
          }
          val v = tohostWord
          if (v != 0 && !done) {
            done = true
            result = if (v == 1) Pass else Fail((v >> 1).toLong)
          }
        }
        for (t <- dut.io.trace.insns) {
          if (t.valid.toBoolean) {
            retired += 1
            val wd = if (t.wdata != null) f" ${t.wdata.toBigInt}%x" else ""
            if (verbose) println(f"[${simTime()}%8d] ${t.iaddr.toBigInt}%016x ${t.insn.toLong}%08x$wd")
          }
          if (verbose && (t.exception.toBoolean || t.interrupt.toBoolean))
            println(f"[${simTime()}%8d] TRAP cause=${t.cause.toBigInt}%x tval=${t.tval.toBigInt}%x")
        }
      }
      dut.clockDomain.waitSampling(10)
      var cycles = 0L
      while (!done && cycles < maxCycles) {
        dut.clockDomain.waitSampling(100)
        cycles += 100
      }
      if (verbose) println(s"retired $retired instructions in $cycles cycles")
      for (t <- tracer) {
        t.close()
        println(s"Konata log: ${konata.get.getPath}" + (if (t.desyncs != 0) s" (${t.desyncs} tracking mismatches)" else ""))
      }
      onFinish(cycles, retired)
    }
    result
  }
}
