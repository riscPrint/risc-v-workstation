package rvwvexii

import spinal.core._
import spinal.lib._
import spinalprobes.Probe
import vexiiriscv.execute.lsu.{LsuL1, LsuL1Plugin, LsuPlugin}
import vexiiriscv.fetch.FetchL1Plugin

/** L1 probes of the `*_cached` configs, on existing signals (no core source change).
  * Events per cache (`icache`, `dcache`), as in the VexRiscv example:
  *  - `access`: I$ at each commit (whitebox commit port), a miss when a refill of the
  *    instruction's line started since the last commit in it. D$ at the LSU commit probe (the
  *    upstream prefetcher training stream: the first attempt of each load or store; redos after
  *    a miss are not repeated), `hit` = the L1 tag lookup (`!MISS`; a hazard alone is a hit).
  *    Accesses that trap for another reason, and I/O, are left out.
  *  - `fill`: a refill completes, with the line bytes. `evict`: a refill replaces a loaded way
  *    (victim line address). `writeback`: a dirty line burst completes, with its bytes.
  *  - `flush`: the fetch L1 starts a full invalidation (FENCE.I).
  * Counters: `icache_accesses`, `icache_misses`, `icache_fills`, `dcache_accesses`,
  * `dcache_misses`, `dcache_load_misses`, `dcache_store_misses`, `dcache_fills`,
  * `dcache_writebacks`, `dcache_hazards`. */
object CacheProbes {
  def lineCapture(beat: Bool, data: Bits, beats: Int): (Bool, Bits) = {
    val count = Reg(UInt(log2Up(beats) + 1 bits)) init(0)
    val line = Reg(Bits(beats * widthOf(data) bits))
    val done = beat && count === beats - 1
    when(beat) {
      line.subdivideIn(beats slices)(count.resize(log2Up(beats) max 1 bits)) := data
      count := count + 1
      when(done) { count := 0 }
    }
    val full = line.subdivideIn(beats slices).zipWithIndex.map { case (w, i) => (done && count === i) ? data | w }
    (done, Cat(full))
  }

  /** Fetch L1. `commits` are the whitebox commit ports (valid, pc). */
  def fetch(f: FetchL1Plugin, commits: Seq[(Bool, UInt)]): Unit = {
    val bus = f.logic.bus
    val lineBits = log2Up(bus.p.lineSize)
    val beats = bus.p.lineSize * 8 / bus.p.dataWidth
    val pending = Reg(UInt(widthOf(bus.cmd.address) bits))
    when(bus.cmd.fire) { pending := bus.cmd.address }
    val (filled, line) = lineCapture(bus.rsp.fire, bus.rsp.data, beats)
    Probe.cacheAccess("icache", "fill", filled, (pending >> lineBits) << lineBits, data = Some(line))
    val missLine = Reg(UInt(widthOf(bus.cmd.address) - lineBits bits))
    val missValid = RegInit(False)
    val hits = for ((valid, pc) <- commits) yield {
      val missed = missValid && missLine === (pc.resize(widthOf(bus.cmd.address)) >> lineBits)
      when(valid && missed) { missValid := False }
      Probe.cacheAccess("icache", "access", valid, pc, hit = Some(!missed))
      (valid, missed)
    }
    when(bus.cmd.fire) { missValid := True; missLine := bus.cmd.address >> lineBits }
    val inv = f.logic.invalidate
    Probe.cacheAccess("icache", "flush", inv.done && inv.cmd.valid, U(0, 32 bits))
    Probe.counter("icache_accesses", hits.map(_._1.asUInt.resize(4 bits)).reduce(_ + _))
    Probe.counter("icache_misses", hits.map(h => (h._1 && h._2).asUInt.resize(4 bits)).reduce(_ + _))
    Probe.counter("icache_fills", filled)
  }

  /** LSU L1 and the LSU commit probe. */
  def lsu(l1: LsuL1Plugin, lsu: LsuPlugin): Unit = {
    val bus = l1.logic.bus
    val lineBytes = bus.p.lineSize
    val lineBits = log2Up(lineBytes)
    val beats = lineBytes * 8 / bus.p.dataWidth
    val pending = Reg(UInt(bus.p.addressWidth bits))
    when(bus.read.cmd.fire) { pending := bus.read.cmd.address }
    val (filled, line) = lineCapture(bus.read.rsp.fire, bus.read.rsp.data, beats)
    Probe.cacheAccess("dcache", "fill", filled, (pending >> lineBits) << lineBits, data = Some(line))

    val wbAddress = Reg(UInt(bus.p.addressWidth bits))
    val wcmd = bus.write.cmd
    val first = RegInit(True)
    when(wcmd.fire) { first := wcmd.last; when(first) { wbAddress := wcmd.fragment.address } }
    val (written, wline) = lineCapture(wcmd.fire, wcmd.fragment.data, beats)
    val wbLine = first ? wcmd.fragment.address | wbAddress
    Probe.cacheAccess("dcache", "writeback", written, (wbLine >> lineBits) << lineBits, data = Some(wline))

    // Victim of a refill: the target way's tag, read at the control stage.
    val ctrl = l1.logic.lsu.ctrl
    val tags = ctrl(l1.logic.WAYS_TAGS)
    val victim = tags(ctrl.targetWay)
    val tagLow = log2Up(l1.setCount * lineBytes)
    val physical = ctrl(LsuL1.PHYSICAL_ADDRESS)
    val victimAddress = (victim.address.resize(widthOf(physical)) << tagLow).resize(widthOf(physical)) |
      (physical & U((BigInt(1) << tagLow) - (BigInt(1) << lineBits), widthOf(physical) bits))
    val refilling = ctrl.doRefill && !ctrl.preventSideEffects
    Probe.cacheAccess("dcache", "evict", refilling && victim.loaded, victimAddress)

    val probe = lsu.logic.commitProbe
    val oc = lsu.logic.onCtrl
    val miss = oc(LsuL1.MISS) || oc(LsuL1.MISS_UNIQUE)
    val access = probe.valid && !probe.io && (!probe.trap || miss || oc(LsuL1.HAZARD))
    Probe.cacheAccess("dcache", "access", access, probe.address, hit = Some(!miss), write = Some(probe.store))
    Probe.counter("dcache_accesses", access)
    Probe.counter("dcache_misses", access && miss)
    Probe.counter("dcache_load_misses", access && miss && !probe.store)
    Probe.counter("dcache_store_misses", access && miss && probe.store)
    Probe.counter("dcache_hazards", access && !miss && oc(LsuL1.HAZARD))
    Probe.counter("dcache_fills", filled)
    Probe.counter("dcache_writebacks", written)
  }
}
