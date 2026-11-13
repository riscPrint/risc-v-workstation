package spinalprobes

import java.nio.file.Files
import java.security.MessageDigest
import org.scalatest.funsuite.AnyFunSuite
import spinal.core._

/** A small seeded pipeline (fetch, execute, write-back) with a register file, a one-entry TLB,
  * a direct-mapped cache tag and a branch unit. `withProbes` adds one call of every probe kind.
  * Synthesis safety: with probes disabled the Verilog must equal the design without the calls. */
class SeededPipe(withProbes: Boolean) extends Component {
  val io = new Bundle {
    val insn = in Bits(32 bits)
    val valid = in Bool()
    val irq = in Bool()
    val mem = in Bits(32 bits)
    val result = out UInt(32 bits)
  }
  val pc = Reg(UInt(32 bits)) init(0x80000000L)
  val seq = Reg(UInt(8 bits)) init(0)
  val ex = new Area {
    val valid = RegNext(io.valid) init(False)
    val insn = RegNext(io.insn)
    val id = RegNext(seq)
    val taken = valid && insn(0)
    val target = pc + (insn(15 downto 4).asUInt << 1).resize(32)
    val stall = valid && insn(1)
  }
  val wb = new Area {
    val valid = RegNext(ex.valid && !ex.stall) init(False)
    val id = RegNext(ex.id)
    val value = RegNext(ex.insn.asUInt + pc)
  }
  val regs = Vec.fill(4)(Reg(UInt(32 bits)) init(0))
  when(wb.valid) { regs(wb.value(1 downto 0)) := wb.value }
  val tlbVa = Reg(UInt(20 bits)) init(0)
  val tlbHit = io.mem(31 downto 12).asUInt === tlbVa
  val tagHit = io.mem(11 downto 4) === regs(0)(11 downto 4).asBits
  val csr = Reg(Bits(32 bits)) init(0)
  when(io.valid && io.insn(6 downto 0) === B"1110011") { csr := io.mem }
  when(io.valid) { seq := seq + 1 }
  pc := ex.taken ? ex.target | (pc + 4)
  when(!tlbHit && io.valid) { tlbVa := io.mem(31 downto 12).asUInt }
  io.result := regs.reduce(_ + _) ^ pc

  if (withProbes) {
    Probe.branch("bu", ex.valid, pc, ex.taken, ex.target, predictedTaken = Some(False))
    Probe.cacheAccess("d", "read", io.valid, io.mem, hit = Some(tagHit), data = Some(io.mem))
    Probe.tlb("dtlb", "fill", io.valid && !tlbHit, va = Some(io.mem), pa = Some(io.mem))
    Probe.pageWalk("ptw", "response", io.valid && !tlbHit, io.mem, data = Some(io.mem), level = Some(U(0, 2 bits)))
    Probe.walkResult("ptw", "sv32", io.valid && !tlbHit, io.mem, U(0, 2 bits), U(0, 34 bits), U(0, 2 bits), io.mem)
    Probe.stage("X", ex.valid, ex.id, pc = Some(pc))
    Probe.retire("wb", wb.valid, wb.id)
    Probe.flush("x", ex.valid && ex.taken, ex.id)
    Probe.stall("execute", "structural", ex.stall)
    Probe.csrWrite("csr", io.valid && io.insn(6 downto 0) === B"1110011", io.insn(31 downto 20), io.mem)
    Probe.interruptTaken("irq", io.irq, io.mem, pc)
    Probe.traceIngress("te", wb.valid, U(0, 4 bits), pc, U(1, 2 bits), U(1, 1 bits), U(3, 2 bits))
    Probe.bus("dbus", io.valid, io.mem, write = Some(io.insn(5)), data = Some(io.mem))
    Probe.counter("retired", wb.valid, hpm = Some(3))
    Probe.faultSite("pc", pc)
    Probe.custom("seq", io.valid, "seq" -> seq)
  }
}

class ProbeSafetySpec extends AnyFunSuite {
  private def verilog(withProbes: Boolean, enable: Boolean): String = {
    val dir = Files.createTempDirectory("spinalprobes-safety").toFile
    Probe.enabled(enable) {
      SpinalConfig(targetDirectory = dir.getPath).generateVerilog(new SeededPipe(withProbes).setDefinitionName("SeededPipe"))
    }
    new String(Files.readAllBytes(new java.io.File(dir, "SeededPipe.v").toPath))
  }
  private def sha(s: String) = MessageDigest.getInstance("SHA-256").digest(s.getBytes("UTF-8")).map(b => f"${b & 255}%02x").mkString

  test("probes disabled: Verilog equals the design without probe calls") {
    val plain = verilog(withProbes = false, enable = false)
    val disabled = verilog(withProbes = true, enable = false)
    assert(sha(disabled) == sha(plain))
    assert(disabled == plain)
  }

  test("probes enabled: every kind adds named wires, so the comparison can fail") {
    val enabled = verilog(withProbes = true, enable = true)
    assert(enabled != verilog(withProbes = false, enable = false))
    for (k <- Seq("branch", "cache", "tlb", "walk", "stage", "retire", "flush", "stall", "csr", "interrupt", "trace",
        "bus", "counter", "custom"))
      assert(enabled.contains(s"rvwprobe__${k}__"), k)
  }
}
