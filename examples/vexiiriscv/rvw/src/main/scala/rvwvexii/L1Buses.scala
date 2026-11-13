package rvwvexii

import spinal.core.sim._
import vexiiriscv.VexiiRiscv
import vexiiriscv.execute.lsu.LsuL1Plugin
import vexiiriscv.fetch.FetchL1Plugin
import scala.collection.mutable

/** Memory for the native L1 buses of the `*_cached` configs. Each read command returns one
  * line, one memory word per cycle, after `latency()` cycles; responses keep command order.
  * A write burst stores each beat at once and answers after its last beat. Call `tick` once
  * per sampled edge; it reads the handshakes of that edge and drives the next responses. */
class L1Buses(dut: VexiiRiscv, memory: mutable.LongMap[Int], inRam: (Long, Long) => Boolean,
    latency: () => Long) {
  private def read(addr: Long, n: Int): BigInt = (0 until n).foldLeft(BigInt(0)) { (v, i) =>
    v | (BigInt(memory.getOrElse(addr + i, 0)) << (8 * i))
  }

  /** In-order beats (ready cycle, data, error, id) of a line-burst read port. */
  private class Lines(wordBytes: Int, lineBytes: Int) {
    val beats = mutable.Queue.empty[(Long, BigInt, Boolean, Int)]
    var driven = false
    def accept(cycle: Long, address: Long, id: Int): Unit = {
      val base = address & ~(lineBytes - 1L)
      val start = cycle + latency()
      for (i <- 0 until lineBytes / wordBytes) {
        val a = base + i * wordBytes
        beats.enqueue((start + i, read(a, wordBytes), !inRam(a, wordBytes), id))
      }
    }
    def next(cycle: Long, accepted: Boolean): Option[(BigInt, Boolean, Int)] = {
      if (driven && accepted) beats.dequeue()
      driven = false
      beats.headOption.filter(_._1 <= cycle).map { case (_, d, e, id) => driven = true; (d, e, id) }
    }
  }

  private val fetch = dut.host.get[FetchL1Plugin].map { p =>
    val bus = p.logic.bus
    bus.cmd.ready #= true
    bus.rsp.valid #= false
    (bus, new Lines(bus.p.dataWidth / 8, bus.p.lineSize))
  }

  private val lsu = dut.host.get[LsuL1Plugin].map { p =>
    val bus = p.logic.bus
    bus.read.cmd.ready #= true
    bus.read.rsp.valid #= false
    bus.write.cmd.ready #= true
    bus.write.rsp.valid #= false
    (bus, new Lines(bus.p.dataWidth / 8, bus.p.lineSize))
  }
  private var writeBeat = 0
  private val writeRsps = mutable.Queue.empty[(Long, Int)]

  def tick(cycle: Long): Unit = {
    fetch.foreach { case (bus, lines) =>
      val accepted = bus.rsp.ready.toBoolean
      if (bus.cmd.valid.toBoolean && bus.cmd.ready.toBoolean)
        lines.accept(cycle, bus.cmd.address.toLong, bus.cmd.id.toInt)
      lines.next(cycle, accepted) match {
        case Some((d, e, id)) => bus.rsp.valid #= true; bus.rsp.data #= d; bus.rsp.error #= e; bus.rsp.id #= id
        case None => bus.rsp.valid #= false
      }
    }
    lsu.foreach { case (bus, lines) =>
      val accepted = bus.read.rsp.ready.toBoolean
      if (bus.read.cmd.valid.toBoolean && bus.read.cmd.ready.toBoolean)
        lines.accept(cycle, bus.read.cmd.address.toLong, bus.read.cmd.id.toInt)
      lines.next(cycle, accepted) match {
        case Some((d, e, id)) => bus.read.rsp.valid #= true; bus.read.rsp.data #= d; bus.read.rsp.error #= e; bus.read.rsp.id #= id
        case None => bus.read.rsp.valid #= false
      }
      val w = bus.write.cmd
      if (w.valid.toBoolean && w.ready.toBoolean) {
        val bytes = bus.p.dataWidth / 8
        val base = w.fragment.address.toLong & ~(bus.p.lineSize - 1L)
        val addr = base + writeBeat * bytes
        require(inRam(addr, bytes), f"L1 writeback outside RAM at 0x$addr%x")
        val data = w.fragment.data.toBigInt
        for (i <- 0 until bytes) memory(addr + i) = ((data >> (8 * i)) & 255).toInt
        writeBeat += 1
        if (w.last.toBoolean) { writeRsps.enqueue((cycle + latency(), w.fragment.id.toInt)); writeBeat = 0 }
      }
      writeRsps.headOption.filter(_._1 <= cycle) match {
        case Some((_, id)) => writeRsps.dequeue(); bus.write.rsp.valid #= true; bus.write.rsp.error #= false; bus.write.rsp.id #= id
        case None => bus.write.rsp.valid #= false
      }
    }
  }
}
