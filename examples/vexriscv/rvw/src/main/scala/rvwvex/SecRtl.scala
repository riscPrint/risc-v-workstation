package rvwvex

import spinal.core._
import vexriscv.{VexRiscv, VexRiscvConfig}
import vexriscv.plugin._
import vexriscv.ip.{DataCacheConfig, InstructionCacheConfig}

/** Plain Verilog for `rvw sec` native runs. `rv32im` is the example configuration with probes.
  * `rv32imu` adds user mode (CsrPlugin userGen) for isolation runs across a privilege switch.
  * `rv32imu-cache` replaces the simple buses with 4 KiB direct-mapped caches.
  * `rv32imu-pmp` adds a 4-region NAPOT PMP (32-byte granularity) on fetch and data accesses.
  * Usage: SecRtl OUT [rv32im|rv32imu]... */
object SecRtl {
  def configuration(variant: String): VexRiscvConfig = {
    val base = VexTop.configuration()
    variant match {
      case "rv32im" => base
      case "rv32imu" => VexRiscvConfig(plugins = base.plugins.map {
        case c: CsrPlugin => new CsrPlugin(c.config.copy(userGen = true))
        case p => p
      })
      case "rv32imu-pmp" => VexRiscvConfig(plugins = configuration("rv32imu").plugins.flatMap {
        // Route fetch and data accesses through a 4-region PMP. The bus parameters stay the same.
        case _: IBusSimplePlugin => Seq(new IBusSimplePlugin(resetVector = 0x80000000L, cmdForkOnSecondStage = false,
          cmdForkPersistence = true, prediction = STATIC, catchAccessFault = true, compressedGen = false,
          memoryTranslatorPortConfig = MmuPortConfig(portTlbSize = 4)))
        case _: DBusSimplePlugin => Seq(new DBusSimplePlugin(catchAddressMisaligned = true, catchAccessFault = true,
          memoryTranslatorPortConfig = MmuPortConfig(portTlbSize = 4)),
          new PmpPluginNapot(regions = 4, granularity = 32, ioRange = _ => False))
        case p => Seq(p)
      })
      case "rv32imu-cache" => VexRiscvConfig(plugins = configuration("rv32imu").plugins.flatMap {
        // 4 KiB direct-mapped instruction and data caches with 32-byte lines. ProbePlugin reads
        // DBusSimplePlugin, so this variant has no SpinalProbes.
        case _: IBusSimplePlugin => Seq(new IBusCachedPlugin(resetVector = 0x80000000L, prediction = STATIC,
          compressedGen = false, config = InstructionCacheConfig(cacheSize = 4096, bytePerLine = 32, wayCount = 1,
            addressWidth = 32, cpuDataWidth = 32, memDataWidth = 32, catchIllegalAccess = true,
            catchAccessFault = true, asyncTagMemory = false, twoCycleRam = false, twoCycleCache = true)))
        case _: DBusSimplePlugin => Seq(new DBusCachedPlugin(config = DataCacheConfig(cacheSize = 4096,
          bytePerLine = 32, wayCount = 1, addressWidth = 32, cpuDataWidth = 32, memDataWidth = 32,
          catchAccessError = true, catchIllegal = true, catchUnaligned = true)),
          new StaticMemoryTranslatorPlugin(ioRange = _(31 downto 28) === 0xF))
        case _: ProbePlugin => Seq()
        case f: FormalPlugin => Seq(f, new FormalMemPlaceholder)
        case p => Seq(p)
      })
      case other => sys.error(s"unknown sec variant $other")
    }
  }

  def main(args: Array[String]): Unit = {
    val variants = if (args.length > 1) args.drop(1).toSeq else Seq("rv32im", "rv32imu")
    for (variant <- variants) spinalprobes.Probe.enabled(true) {
      VexTop.spinalConfig.copy(targetDirectory = s"${args(0)}/$variant").generateVerilog(
        new VexRiscv(configuration(variant)).setDefinitionName("VexTop"))
    }
  }
}

/** DBusCachedPlugin in this VexRiscv revision does not drive the RVFI memory fields. Zero
  * placeholders let FormalPlugin elaborate; the core binding then checks C2 without them. */
class FormalMemPlaceholder extends Plugin[VexRiscv] {
  override def build(pipeline: VexRiscv): Unit = {
    import pipeline._
    import pipeline.config._
    execute plug new Area {
      import execute._
      insert(FORMAL_MEM_ADDR) := FORMAL_MEM_ADDR().getZero
      insert(FORMAL_MEM_WMASK) := FORMAL_MEM_WMASK().getZero
      insert(FORMAL_MEM_RMASK) := FORMAL_MEM_RMASK().getZero
      insert(FORMAL_MEM_WDATA) := FORMAL_MEM_WDATA().getZero
      insert(FORMAL_MEM_RDATA) := FORMAL_MEM_RDATA().getZero
    }
  }
}
