package rvwvex

import spinal.core._
import vexriscv.{VexRiscv, VexRiscvConfig}
import vexriscv.ip.{DataCacheConfig, InstructionCacheConfig}
import vexriscv.plugin._

/** Cached configurations of the example core. Additive: `rv32im` stays the default.
  *
  * `rv32im_cached` replaces the simple buses of `rv32im` with the upstream instruction and data
  * caches of `GenFullNoMmu`: 4 KiB, 32-byte lines, one way each. The data cache is write-through
  * and does not allocate on a store miss. Addresses 0xF0000000 and up are uncached I/O.
  * Everything else (CSR set, ISA, probes) is the same as `rv32im`.
  *
  * `rv32ima_linux` is the `Linux.scala` class plugin set on the same caches: Sv32 MMU
  * (`MmuPlugin`, 4-entry port TLBs), M/S/U privilege, LR/SC and AMOs in the data cache. */
object VexCached {
  val configs = Seq("rv32im_cached", "rv32ima_linux")
  val lineBytes = 32

  def icache = InstructionCacheConfig(cacheSize = 4096, bytePerLine = lineBytes, wayCount = 1,
    addressWidth = 32, cpuDataWidth = 32, memDataWidth = 32, catchIllegalAccess = true,
    catchAccessFault = true, asyncTagMemory = false, twoCycleRam = true, twoCycleCache = true)

  def dcache = DataCacheConfig(cacheSize = 4096, bytePerLine = lineBytes, wayCount = 1,
    addressWidth = 32, cpuDataWidth = 32, memDataWidth = 32, catchAccessError = true,
    catchIllegal = true, catchUnaligned = true)

  /** M/S/U with the M-mode CSR choices of `rv32im`. `satp` lives in the MMU plugin. */
  def linuxCsr: CsrPluginConfig = CsrPluginConfig.all2(0x80000000L).copy(userGen = true, supervisorGen = true,
    misaExtensionsInit = 0x141101, misaAccess = CsrAccess.READ_ONLY, ebreakGen = true,
    satpAccess = CsrAccess.NONE, scycleAccess = CsrAccess.NONE, sinstretAccess = CsrAccess.NONE)

  def isa(config: String): String = if (config == "rv32ima_linux") "rv32ima_zicsr_zifencei" else "rv32im_zicsr_zifencei"

  def configuration(config: String): VexRiscvConfig = {
    require(configs.contains(config), s"unknown cached config $config")
    val linux = config == "rv32ima_linux"
    val port = if (linux) MmuPortConfig(portTlbSize = 4) else null
    val io: UInt => Bool = _(31 downto 28) === 0xF
    val plugins = VexTop.configuration().plugins.flatMap {
      case _: IBusSimplePlugin => Seq(
        new IBusCachedPlugin(resetVector = 0x80000000L, prediction = STATIC, compressedGen = false,
          config = icache, memoryTranslatorPortConfig = port),
        if (linux) new MmuPlugin(ioRange = io) else new StaticMemoryTranslatorPlugin(ioRange = io))
      case _: DBusSimplePlugin => Seq(new DBusCachedPlugin(
        config = if (linux) dcache.copy(withLrSc = true, withAmo = true) else dcache,
        memoryTranslatorPortConfig = port), new CachedFormalPlugin)
      case _: CsrPlugin if linux => Seq(new CsrPlugin(linuxCsr))
      case p => Seq(p)
    }
    VexRiscvConfig(plugins = plugins)
  }
}

/** `DBusCachedPlugin` does not feed the RVFI memory fields, so `FormalPlugin` lacks them.
  * Rebuild them at write-back from the plugin's own stage values: the address, the store
  * data replicated by size, and the load word moved back to its byte lanes. */
class CachedFormalPlugin extends Plugin[VexRiscv] {
  override def build(pipeline: VexRiscv): Unit = {
    import pipeline._
    import pipeline.config._
    val dc = pipeline.config.get(classOf[DBusCachedPlugin])
    writeBack plug new Area {
      import writeBack._
      val address = U(input(REGFILE_WRITE_DATA))
      val size = input(INSTRUCTION)(13 downto 12).asUInt
      val bytes = size.mux(0 -> B"0001", 1 -> B"0011", default -> B"1111")
      val mask = (bytes << address(1 downto 0)).resize(4 bits)
      val enabled = input(dc.MEMORY_ENABLE)
      val write = input(dc.MEMORY_WR)
      val laneMask = Cat((0 to 3).map(i => mask(i) ? B"xFF" | B"x00"))
      insert(FORMAL_MEM_ADDR) := address & U"xFFFFFFFC"
      // LR reads; SC writes only on success (rd = 0); an AMO reads and writes.
      val amo = if (dc.config.withAmo) input(dc.MEMORY_AMO) else False
      val lrsc = if (dc.config.withLrSc) input(dc.MEMORY_LRSC) else False
      val scFailed = lrsc && write && output(REGFILE_WRITE_DATA) =/= 0
      insert(FORMAL_MEM_WMASK) := (enabled && write && !scFailed) ? mask | B"0000"
      insert(FORMAL_MEM_RMASK) := (enabled && (!write || amo)) ? mask | B"0000"
      val rdata = ((output(dc.MEMORY_LOAD_DATA).resize(32 bits) << (address(1 downto 0) @@ U"000")).resize(32 bits)) & laneMask
      // The cache writes the AMO result, which it keeps internal: recompute it from rs2 and the old word.
      val rs2 = input(dc.MEMORY_STORE_DATA_RF)
      val funct5 = input(INSTRUCTION)(31 downto 27)
      val (a, b) = (rdata.asSInt, rs2.asSInt)
      val amoResult = funct5.mux(
        B"00001" -> rs2, B"00000" -> (a + b).asBits, B"00100" -> (rdata ^ rs2),
        B"01100" -> (rdata & rs2), B"01000" -> (rdata | rs2),
        B"10000" -> ((a < b) ? rdata | rs2), B"10100" -> ((a > b) ? rdata | rs2),
        B"11000" -> ((rdata.asUInt < rs2.asUInt) ? rdata | rs2), default -> ((rdata.asUInt > rs2.asUInt) ? rdata | rs2))
      insert(FORMAL_MEM_WDATA) := amo ? amoResult | rs2
      insert(FORMAL_MEM_RDATA) := rdata
    }
  }
}

/** Memory responders for the cached buses: one outstanding read per bus, answered after
  * `delay()` cycles, one 32-bit beat per cycle. Data-cache writes are single beats, written at
  * once, with no response (write-through, no write response in this config). */
object CachedBuses {
  import spinal.core.sim._
  import scala.collection.mutable

  def drive(dut: VexTop, cd: ClockDomain, delay: () => Long, readWord: Long => BigInt,
      inRam: (Long, Long) => Boolean, memory: mutable.LongMap[Int]): Unit = {
    val ibus = dut.icached.get.iBus
    val dbus = dut.dcached.get.dBus
    ibus.cmd.ready #= false
    ibus.rsp.valid #= false
    dbus.cmd.ready #= false
    dbus.rsp.valid #= false
    dbus.rsp.aggregated #= 0
    // Each pending beat: (first cycle it may be driven, data, error, last).
    def burst(cycle: Long, address: Long, bytes: Int): mutable.Queue[(Long, BigInt, Boolean, Boolean)] = {
      val start = cycle + delay()
      val beats = math.max(1, bytes / 4)
      val base = address & ~(beats * 4L - 1)
      mutable.Queue.from((0 until beats).map { i =>
        val a = base + 4L * i
        (start + i, readWord(a), !inRam(a, 4), i == beats - 1)
      })
    }
    fork {
      var pending = mutable.Queue.empty[(Long, BigInt, Boolean, Boolean)]
      var cycle = 0L
      while (true) {
        cd.waitFallingEdge()
        val beat = pending.headOption.filter(_._1 <= cycle)
        ibus.cmd.ready #= pending.isEmpty
        ibus.rsp.valid #= beat.nonEmpty
        beat.foreach { case (_, data, error, _) => ibus.rsp.data #= data; ibus.rsp.error #= error }
        cd.waitSampling()
        cycle += 1
        if (beat.nonEmpty) pending.dequeue()
        if (ibus.cmd.valid.toBoolean && ibus.cmd.ready.toBoolean)
          pending = burst(cycle, ibus.cmd.address.toLong, 1 << ibus.cmd.size.toInt)
      }
    }
    fork {
      var pending = mutable.Queue.empty[(Long, BigInt, Boolean, Boolean)]
      var cycle = 0L
      while (true) {
        cd.waitFallingEdge()
        val beat = pending.headOption.filter(_._1 <= cycle)
        dbus.cmd.ready #= pending.isEmpty
        dbus.rsp.valid #= beat.nonEmpty
        beat.foreach { case (_, data, error, last) =>
          dbus.rsp.data #= data; dbus.rsp.error #= error; dbus.rsp.last #= last
        }
        cd.waitSampling()
        cycle += 1
        if (beat.nonEmpty) pending.dequeue()
        if (dbus.cmd.valid.toBoolean && dbus.cmd.ready.toBoolean) {
          val cmd = dbus.cmd
          val address = cmd.address.toLong
          if (cmd.wr.toBoolean) {
            val word = address & ~3L
            require(inRam(word, 4), f"store outside RAM at 0x$address%x")
            val data = cmd.data.toBigInt
            for (i <- 0 until 4 if (cmd.mask.toInt & (1 << i)) != 0)
              memory(word + i) = ((data >> (8 * i)) & 255).toInt
          } else pending = burst(cycle, address, 1 << cmd.size.toInt)
        }
      }
    }
  }
}
