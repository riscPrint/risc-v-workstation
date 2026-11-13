package rvwvex

import spinal.core._
import spinal.lib._
import spinalprobes.Probe
import vexriscv.{VexRiscv, Riscv}
import vexriscv.ip.{DataCache, InstructionCache}
import vexriscv.plugin._

/** Cache probes of the cached configs, on existing signals (no core source change).
  * Events per cache (`icache`, `dcache`):
  *  - `access` at the commit point (write-back firing), one per committed instruction (I$) or
  *    committed load/store/AMO (D$). `hit` is the first lookup of that instruction: a load
  *    or AMO that refilled is a miss (the core redoes it after the refill, and the redo hits);
  *    a store looks up once (write-through, no allocation), so it is a miss when no way hit.
  *    I$: a miss when a refill of the instruction's line started since the last commit in it.
  *  - `fill` when a line refill completes, with the line address and its bytes.
  *  - `evict` (D$) when a refill replaces a valid line, with the victim line address.
  *  - `flush` at the cache invalidation request (I$), or at the commit of a data-cache management instruction (D$):
  *    the whole cache is invalidated.
  * Counters: `icache_accesses`, `icache_misses`, `dcache_accesses`, `dcache_misses`,
  * `dcache_load_misses`, `dcache_store_misses`, `icache_fills`, `dcache_fills`. */
object CacheProbes {
  def apply(pipeline: VexRiscv): Unit = {
    import pipeline._
    import pipeline.config._
    val ic = pipeline.config.plugins.collectFirst { case p: IBusCachedPlugin => p }
    val dc = pipeline.config.plugins.collectFirst { case p: DBusCachedPlugin => p }
    val wb = writeBack
    val commit = wb.arbitration.isFiring

    /** Collect the beats of one line refill; `done` is the last beat. */
    def lineCapture(beat: Bool, data: Bits, beats: Int): (Bool, Bits) = {
      val count = Reg(UInt(log2Up(beats) + 1 bits)) init(0)
      val line = Reg(Bits(beats * widthOf(data) bits))
      val done = beat && count === beats - 1
      when(beat) {
        line.subdivideIn(beats slices)(count.resize(log2Up(beats) max 1 bits)) := data
        count := count + 1
        when(done) { count := 0 }
      }
      val full = line.subdivideIn(beats slices).zipWithIndex.map { case (w, i) =>
        (done && count === i) ? data | w }
      (done, Cat(full))
    }

    ic.foreach { p =>
      val cache = pipeline.children.collectFirst { case c: InstructionCache => c }.get
      val cfg = p.config
      val lineBits = log2Up(cfg.bytePerLine)
      val bus = p.iBus
      val beats = cfg.bytePerLine * 8 / cfg.memDataWidth
      val pending = Reg(UInt(32 bits))
      when(bus.cmd.fire) { pending := bus.cmd.address }
      val (filled, line) = lineCapture(bus.rsp.valid, bus.rsp.data, beats)
      Probe.cacheAccess("icache", "fill", filled, (pending >> lineBits) << lineBits, data = Some(line))
      // The line of the last refill, until an instruction of that line commits.
      val missLine = Reg(UInt(32 - lineBits bits))
      val missValid = RegInit(False)
      val pc = wb.input(PC)
      val missed = missValid && missLine === (pc >> lineBits)
      when(commit && missed) { missValid := False }
      when(bus.cmd.fire) { missValid := True; missLine := bus.cmd.address >> lineBits }
      Probe.cacheAccess("icache", "access", commit, pc, hit = Some(!missed))
      val invalidating = cache.io.flush.pull()
      Probe.cacheAccess("icache", "flush", invalidating && !RegNext(invalidating).init(False), pc)
      Probe.counter("icache_accesses", commit)
      Probe.counter("icache_misses", commit && missed)
      Probe.counter("icache_fills", filled)
    }

    dc.foreach { p =>
      val cache = pipeline.children.collectFirst { case c: DataCache => c }.get
      val cfg = p.config
      require(cfg.wayCount == 1, "dcache evict probe expects one way")
      val lineBits = log2Up(cfg.bytePerLine)
      val tagLow = log2Up(cfg.cacheSize / cfg.wayCount)
      val bus = p.dBus
      val beats = cfg.bytePerLine * 8 / cfg.memDataWidth
      val refillCmd = bus.cmd.fire && !bus.cmd.wr && bus.cmd.size === lineBits
      val pending = Reg(UInt(32 bits))
      val refilling = RegInit(False)
      when(refillCmd) { pending := bus.cmd.address; refilling := True }
      val (filled, line) = lineCapture(bus.rsp.valid && refilling, bus.rsp.data, beats)
      when(filled) { refilling := False }
      Probe.cacheAccess("dcache", "fill", filled, (pending >> lineBits) << lineBits, data = Some(line))
      // Victim: the way-0 tag read for the refilling access (pulled out of the cache component).
      val victim = cache.stageB.tagsReadRsp.head.pull()
      val victimAddress = (victim.address.resize(32 bits) << tagLow).resize(32 bits) |
        (bus.cmd.address & U((1L << tagLow) - (1L << lineBits), 32 bits))
      Probe.cacheAccess("dcache", "evict", refillCmd && victim.valid, victimAddress)

      val waysHit = cache.stageB.waysHit.pull()
      val enabled = wb.input(p.MEMORY_ENABLE) && !wb.input(p.MEMORY_MANAGMENT)
      val write = wb.input(p.MEMORY_WR)
      val amo = if (cfg.withAmo) wb.input(p.MEMORY_AMO) else False
      val io = cache.stageB.mmuRsp.isIoAccess.pull()
      // A refill started for the instruction now in write-back, until a memory access commits.
      val refilled = RegInit(False)
      when(refillCmd) { refilled := True }
      when(commit && wb.input(p.MEMORY_ENABLE)) { refilled := False }
      val hit = (write && !amo) ? waysHit | !refilled
      val access = commit && enabled && !io
      val address = U(wb.input(REGFILE_WRITE_DATA))
      Probe.cacheAccess("dcache", "access", access, address, hit = Some(hit), write = Some(write))
      Probe.cacheAccess("dcache", "flush", commit && wb.input(p.MEMORY_MANAGMENT), address)
      Probe.counter("dcache_accesses", access)
      Probe.counter("dcache_misses", access && !hit)
      Probe.counter("dcache_load_misses", access && !hit && !write)
      Probe.counter("dcache_store_misses", access && !hit && write)
      Probe.counter("dcache_fills", filled)
    }
  }
}
