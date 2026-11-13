import spinal.core._
import vexriscv._
import vexriscv.plugin._

/** Private formal RV32IM configuration. No source changes to VexRiscv. */
object FormalMTop {
  def main(args: Array[String]): Unit = {
    require(args.length == 1, "provide output directory")
    SpinalConfig(targetDirectory=args(0), defaultConfigForClockDomains=ClockDomainConfig(resetKind=spinal.core.SYNC)).generateVerilog {
      new VexRiscv(VexRiscvConfig(plugins=List(
        new IBusSimplePlugin(resetVector=0x80000000L, cmdForkOnSecondStage=false,
          cmdForkPersistence=true, prediction=STATIC, catchAccessFault=true, compressedGen=false),
        new DBusSimplePlugin(catchAddressMisaligned=true, catchAccessFault=true),
        new DecoderSimplePlugin(catchIllegalInstruction=true),
        new RegFilePlugin(regFileReadyKind=vexriscv.plugin.SYNC, zeroBoot=false),
        new IntAluPlugin, new SrcPlugin(separatedAddSub=false, executeInsertion=true),
        new FullBarrelShifterPlugin,
        new HazardSimplePlugin(bypassExecute=true,bypassMemory=true,bypassWriteBack=true,
          bypassWriteBackBuffer=true,pessimisticUseSrc=false,pessimisticWriteRegFile=false,pessimisticAddressMatch=false),
        new MulSimplePlugin, new DivPlugin,
        new CsrPlugin(CsrPluginConfig.all2(0x80000000L).copy(userGen=false,supervisorGen=false,misaExtensionsInit=0x1100)),
        new BranchPlugin(earlyBranch=false, catchAddressMisaligned=true), new FormalPlugin)))
    }
  }
}
