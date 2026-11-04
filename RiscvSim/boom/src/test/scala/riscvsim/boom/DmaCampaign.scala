package riscvsim.boom

import java.io.File
import spinal.core.sim._
import spinal.lib.sim.SparseMemory
import boom.sim.BoomMemoryAgent
import riscvsim._

/** Bounded native coherent-DMA campaign. Not a committed-core gate. */
object DmaCampaign {
  def main(args: Array[String]): Unit = {
    require(args.length == 2, "DmaCampaign ELF WORK")
    val elf = new ElfFile(new File(args(0)))
    val work = new File(args(1)); work.mkdirs()
    val model = BoomAdapter.compile(ModelKey("small"), work, new File(work,"cache"))
    val seen = scala.collection.mutable.Set.empty[(Int,Int)]
    for (delay <- Seq(2,128)) model.doSim(seed = 7) { dut =>
      val cd = dut.clockDomain
      cd.forkStimulus(10)
      dut.io.interrupts.flatten.foreach { case b: spinal.core.Bool => b #= false; case _ => }
      val mem = SparseMemory(seed = 0)
      elf.load((a,d) => mem.write(a,d))
      mem.write(0x0c000100L,0); mem.write(0x0c000108L,0)
      val manager = new BoomMemoryAgent(dut.io.mem,cd,mem,Some(0))
      val shared = elf.symbol("shared").get.toLong
      val expected = new MemoryImage(64); val backing = new MemoryImage(64)
      var captures = 0
      val transport = new TileLinkDmaTransport(manager,shared)
      val dma = new DmaAgent(backing,expected,None,_ => captures += 1,Some(transport))
      val tohost = new ToHost(ToHost.find(elf).get,8)
      var cycles = 0L
      var atomicArmed = false
      var atomicOld = Option.empty[(Int, Long)]
      cd.onSamplings {
        cycles += 1
        val a = dut.io.mem.a
        if (atomicArmed && a.valid.toBoolean && a.ready.toBoolean && a.payload.address.toLong == 0x0c000110L) {
          atomicOld = Some((a.payload.data.toBigInt.toInt,cycles))
        }
        assert(cycles <= 20000, s"DMA campaign cycle limit: phase=${mem.readInt(0x0c000100L)} flag=${mem.readInt(0x0c000108L)}")
        if (dut.io.tohost.valid.toBoolean) {
          val p = dut.io.tohost.payload
          tohost.onStore(p.addr.toBigInt,p.size.toInt,p.data.toBigInt) match {
            case Some(ToHost.Pass) =>
              assert(captures == 5)
              println(s"[dma-campaign] five accepted DMA checks and stale-read rejection; cycles=$cycles")
              simSuccess()
            case Some(_) => sys.error("DMA campaign program failed")
            case None =>
          }
        }
      }
      def phase(n: Int): Unit = {
        while (mem.readInt(0x0c000100L) != n) cd.waitSampling()
        println(s"[dma-campaign] phase=$n cycles=$cycles")
      }
      def word(n: Int): Vector[Byte] = Vector.tabulate(4)(i => (n >>> (i*8)).toByte)
      // Expected CPU values come from fixed program operands, not DUT data.
      phase(1); expected.write(0,word(37),15)
      assert(mem.readInt(shared) == 0, "CPU dirty data must not already be in backing memory")
      assert(dma.read(0,4,true) == word(37)) // actual dirty writeback through B/C
      dma.write(0,word(73),15,false) // leave the CPU B copy stale deliberately
      mem.write(0x0c000108L,10)
      phase(10)
      val staleCpu = mem.readInt(0x0c000110L)
      assert(staleCpu == 37 && staleCpu != 73, "noncoherent device write must leave stale CPU bytes before maintenance")
      dma.write(0,word(73),15,true) // actual CPU invalidation before publication
      mem.write(0x0c000108L,1)
      phase(2); expected.write(0,word(78),15) // CPU AMOADD 5
      val stale = try { dma.read(0,4,false); false } catch {
        case e: IllegalArgumentException => assert(e.getMessage.contains("stale or corrupt")); true
      }
      assert(stale, "noncoherent dirty-buffer read must expose stale backing bytes")
      assert(dma.read(0,4,true) == word(78))
      dma.write(0,word(0x1234),3,true) // masked write after snoop completion
      mem.write(0x0c000108L,2)
      phase(3)
      // Release CPU AMOADD and coherent DMA write without a barrier between them.
      // Both legal serialization orders are computed from fixed operands first.
      val allowed = Set((0x1234,1000),(1000,1005))
      var dmaComplete = false
      var dmaSerializationCycle = -1L
      atomicArmed = true
      val released = cycles
      mem.write(0x0c000108L,3)
      fork {
        cd.waitSampling(delay)
        transport.write(0,word(1000),15,true,() => { dmaSerializationCycle = cycles; dmaComplete = true })
      }
      phase(4)
      while (!dmaComplete) cd.waitSampling()
      var sampled = false
      val finalBytes = transport.read(0,4,true,() => { sampled = true })
      val finalValue = finalBytes.zipWithIndex.map { case (b,i) => (b.toInt & 255) << (i*8) }.reduce(_ | _)
      val (old,oldObservedCycle) = atomicOld.getOrElse(sys.error("missing independent CPU old-value bus observation"))
      assert(dmaSerializationCycle >= released && oldObservedCycle >= released)
      assert(sampled && allowed((old,finalValue)), s"CPU atomic / DMA forbidden outcome: old=$old final=$finalValue")
      seen += ((old,finalValue))
      println(s"[dma-campaign] delay=$delay concurrent CPU AMOADD/DMA outcome: old=$old final=$finalValue; DMA serialized=$dmaSerializationCycle CPU old observed=$oldObservedCycle")
      mem.write(0x0c000108L,4)
      while (true) cd.waitSampling()
    }
    assert(seen.toSet == Set((0x1234,1000),(1000,1005)), "both CPU/DMA serialization orders must be observed")
  }
}
