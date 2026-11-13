package rvwvex

import spinal.core._
import spinal.lib._
import spinalprobes.Probe
import vexriscv.{Stageable, VexRiscv}
import vexriscv.Riscv.IMM
import vexriscv.plugin._

/** Attach workstation probes to existing VexRiscv signals, without changing core sources.
  * Adds nothing unless the elaboration runs under `Probe.enabled(true)` (C1 `--probes`).
  *
  *  - branch: at write-back firing (the commit point), for every BRANCH_CTRL other than INC.
  *    VexRiscv sets BRANCH_DO = prediction != outcome, so predicted = BRANCH_DO xor outcome.
  *  - stage/retire/flush: decode, execute, memory, write-back occupancy with an ID assigned
  *    once per decoded instruction; flush when a valid stage is removed.
  *  - stall: stage stuck levels. Causes are attributed from the halt kind and the instruction
  *    class, so their evidence is `inferred`.
  *  - counters and interrupt-taken entries, from the same arbitration and CSR signals. */
class ProbePlugin extends Plugin[VexRiscv] {
  object PROBE_ID extends Stageable(UInt(32 bits))
  object PROBE_TARGET extends Stageable(UInt(32 bits))

  override def build(pipeline: VexRiscv): Unit = if (Probe.isEnabled) {
    import pipeline._
    import pipeline.config._
    val bp = pipeline.config.get(classOf[BranchPlugin])
    val csr = pipeline.config.get(classOf[CsrPlugin])
    val dbus = pipeline.config.get(classOf[DBusSimplePlugin])
    val stagesWithNames = Seq(decode -> "D", execute -> "X", memory -> "M", writeBack -> "W")

    // One ID per instruction that leaves decode (moves on or is removed).
    val nextId = Reg(UInt(32 bits)) init(0)
    when(decode.arbitration.isValid && (decode.arbitration.isFiring || decode.arbitration.removeIt)) { nextId := nextId + 1 }
    decode.insert(PROBE_ID) := nextId

    // Actual branch target, computed from the operands the branch unit uses.
    execute plug new Area {
      import execute._
      val imm = IMM(input(INSTRUCTION))
      val jalr = input(BRANCH_CTRL) === BranchCtrlEnum.JALR
      val base = jalr ? input(RS1).asUInt | input(PC)
      val offset = jalr ? imm.i_sext | ((input(BRANCH_CTRL) === BranchCtrlEnum.JAL) ? imm.j_sext | imm.b_sext)
      insert(PROBE_TARGET) := ((base + offset.asUInt)(31 downto 1) @@ U"0")
    }

    val wb = writeBack
    val retire = wb.arbitration.isFiring
    val isBranch = wb.input(BRANCH_CTRL) =/= BranchCtrlEnum.INC
    val taken = wb.input(bp.BRANCH_COND_RESULT)
    val predicted = wb.input(bp.BRANCH_DO) ^ taken
    Probe.branch("vex_static", retire && isBranch, wb.input(PC), taken, wb.input(PROBE_TARGET),
      predictedTaken = Some(predicted), semantics = "final-prediction")

    for ((s, name) <- stagesWithNames) {
      Probe.stage(name, s.arbitration.isValid, s.input(PROBE_ID), pc = Some(s.input(PC)))
      Probe.flush(s"${name}_remove", s.arbitration.isValid && s.arbitration.removeIt, s.input(PROBE_ID))
    }
    Probe.retire("wb", retire, wb.input(PROBE_ID))

    // Stall levels. Stuck by itself (haltItself) is the stage's own wait.
    val memWait = memory.arbitration.isValid && memory.arbitration.haltItself
    val memIsLoad = memory.input(dbus.MEMORY_ENABLE)
    Probe.stall("memory", "load_miss", memWait && memIsLoad, evidence = "inferred")
    Probe.stall("memory", "structural", memWait && !memIsLoad, evidence = "inferred")
    Probe.stall("execute", "structural", execute.arbitration.isValid && execute.arbitration.haltItself, evidence = "inferred")
    Probe.stall("decode", "operand_wait", decode.arbitration.isValid && decode.arbitration.haltByOther &&
      !execute.arbitration.isStuck, evidence = "inferred")
    Probe.stall("fetch", "empty", !decode.arbitration.isValid, evidence = "inferred")

    // Event counters (names are the calibration plan's RTL event names).
    Probe.counter("cycles", True)
    Probe.counter("retired", retire)
    Probe.counter("branches", retire && isBranch)
    Probe.counter("cond_branches", retire && wb.input(BRANCH_CTRL) === BranchCtrlEnum.B)
    Probe.counter("mispredicts", retire && isBranch && wb.input(bp.BRANCH_DO), hpm = Some(3))
    Probe.counter("loads", retire && wb.input(dbus.MEMORY_ENABLE) && !wb.input(dbus.MEMORY_STORE), hpm = Some(4))
    Probe.counter("stores", retire && wb.input(dbus.MEMORY_ENABLE) && wb.input(dbus.MEMORY_STORE), hpm = Some(5))
    Probe.counter("memory_wait_cycles", memWait && memIsLoad)
    Probe.counter("decode_stall_cycles", decode.arbitration.isValid && decode.arbitration.isStuck)
    Probe.counter("fetch_empty_cycles", !decode.arbitration.isValid)
    Probe.counter("flushes", stagesWithNames.map { case (s, _) => s.arbitration.isValid && s.arbitration.removeIt }.reduce(_ || _))

    // Accepted bus requests at the core ports. The data bus has no cache in this config.
    val ibus = pipeline.config.get(classOf[IBusSimplePlugin]).iBus
    Probe.bus("ibus", ibus.cmd.fire, ibus.cmd.pc)
    val dcmd = dbus.dBus.cmd
    Probe.bus("dbus", dcmd.fire, dcmd.address, write = Some(dcmd.wr), data = Some(dcmd.data),
      mask = Some(dcmd.mask), size = Some(dcmd.size))

    // CSR writes: the plugin's own write strobe (any address), the instruction's CSR field and
    // the data it writes. Unimplemented bits are dropped by the CSR storage, not here.
    val csrWriting = Bool()
    csrWriting := False
    csr.csrMapping.onAnyWrite { csrWriting := True }
    Probe.csrWrite("csr", csrWriting, execute.input(INSTRUCTION)(31 downto 20), csr.csrMapping.writeDataSignal)

    // Interrupt-taken: the registered trap strobe and actual mcause/mepc storage.
    def readCsr(address: Int): Bits = csr.csrMapping.mapping(address).collect {
      case r: CsrRead => (r.that.asBits.resize(32) << r.bitOffset).resize(32)
    }.foldLeft(B(0, 32 bits))(_ | _)
    val returning = wb.arbitration.isValid && wb.input(csr.ENV_CTRL) === csr.EnvCtrlEnum.XRET
    val trap = RegNext(csr.jumpInterface.valid && !returning) init(False)
    val cause = readCsr(0x342)
    Probe.interruptTaken("irq", trap && cause.msb, cause, readCsr(0x341))
  }
}
