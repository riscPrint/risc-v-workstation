package riscvsim

import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._

/** Small RTL interpreter shared by the round 2 and atomic fixtures.
  * ADDI/SLLI, XLEN loads/stores/atomics, serialized FENCE and the original polling branch.
  * Not a general RISC-V core. */
class FixtureHart(program: Seq[Long], programmable: Boolean = false, xlen: Int = 32) extends Component {
  require(Set(32, 64)(xlen))
  val io = new Bundle {
    val enable = in Bool()
    val instruction = in Bits(32 bits)
    val atomic = out Bool()
    val operation = out UInt(5 bits)
    val registers = out Vec(Bits(xlen bits), 32)
    val request = out Bool()
    val write = out Bool()
    val address = out UInt(xlen bits)
    val wdata = out Bits(xlen bits)
    val rdata = in Bits(xlen bits)
    val ready = in Bool()
    val retired = out Bool()
    val pc = out UInt(32 bits)
    val insn = out Bits(32 bits)
    val value = out Bits(xlen bits)
    val done = out Bool()
  }
  val pc = Reg(UInt(32 bits)) init 0
  val regs = Vec(Reg(Bits(xlen bits)) init 0, 32)
  val x1 = regs(1)
  io.registers := regs
  val rom = Vec(program.map(i => B(BigInt(i), 32 bits)))
  val done = if (programmable) io.instruction === 0 else pc >= program.size * 4
  val insn = if (programmable) io.instruction else rom((pc >> 2).resize(log2Up(program.size)))
  val op = insn(6 downto 0)
  val load = op === B(0x03, 7 bits)
  val store = op === B(0x23, 7 bits)
  val atomic = op === B(0x2f, 7 bits)
  val rs1 = regs(insn(19 downto 15).asUInt)
  val rs2 = regs(insn(24 downto 20).asUInt)
  io.atomic := atomic
  io.operation := insn(31 downto 27).asUInt
  val immediate = insn(31 downto 20).asSInt.resize(xlen).asBits
  io.request := io.enable && !done && (load || store || atomic)
  io.write := store || (atomic && io.operation =/= 2)
  io.address := rs1.asUInt + Mux(atomic, U(0, xlen bits), Mux(store, (insn(31 downto 25) ## insn(11 downto 7)).asUInt.resize(xlen), immediate.asUInt))
  io.wdata := rs2
  io.retired := io.enable && !done && (!(load || store || atomic) || io.ready)
  io.pc := pc; io.insn := insn; io.value := x1; io.done := done
  when(io.retired) {
    pc := pc + 4
    switch(op) {
      is(B(0x13, 7 bits)) {
        when(insn(11 downto 7) =/= 0) {
          when(insn(14 downto 12) === B(1, 3 bits)) {
            regs(insn(11 downto 7).asUInt) := (rs1.asUInt |<< insn((if (xlen == 64) 25 else 24) downto 20).asUInt).resize(xlen).asBits
          } otherwise {
            regs(insn(11 downto 7).asUInt) := (rs1.asUInt + immediate.asUInt).asBits
          }
        }
      }
      is(B(0x03, 7 bits), B(0x2f, 7 bits)) {
        when(insn(11 downto 7) =/= 0) { regs(insn(11 downto 7).asUInt) := io.rdata }
      }
      is(B(0x63, 7 bits)) {
        val offset = (insn(31) ## insn(7) ## insn(30 downto 25) ## insn(11 downto 8) ## B"0").asSInt.resize(32).asUInt
        val equal = rs1 === rs2
        when(Mux(insn(12), !equal, equal)) { pc := pc + offset }
      }
    }
  }
}
class TwoHartFixture extends Component {
  // Producer stores 37 at word 0. Consumer polls, adds 1, stores 38 at word 1.
  val harts = Seq(new FixtureHart(Seq(0x02500093L, 0x00102023L, 0x00002083L)),
    new FixtureHart(Seq(0x00002083L, 0xfe008ee3L, 0x00108093L, 0x00102223L)))
  val memory = Vec(Reg(Bits(32 bits)) init 0, 2)
  val turn = Reg(Bool()) init False
  turn := !turn
  val io = new Bundle { val start = in Bool(); val result = out Bits(32 bits) }
  io.result := memory(1)
  for ((h, id) <- harts.zipWithIndex) {
    h.io.enable := io.start
    h.io.instruction := 0
    h.io.ready := (if (id == 0) !turn else turn)
    h.io.rdata := memory(h.io.address(2).asUInt)
    when(h.io.request && h.io.ready && h.io.write) { memory(h.io.address(2).asUInt) := h.io.wdata }
    h.io.simPublic()
  }
}
class TwoHartNativeSpec extends AnyFunSuite {
  test("two RTL harts exchange shared memory with round-robin backpressure and per-hart traces") {
    val work = Files.createTempDirectory("two-hart-native").toFile
    val path = new java.io.File(work, "rvfi.jsonl")
    val trace = new MultiHartTrace(path, ujson.Obj("xlen" -> 32, "isa" -> "rv32i", "fixture_subset" -> true), Seq(0, 1))
    try {
      SimConfig.withVerilator.workspacePath(work.getPath).compile(new TwoHartFixture).doSim { dut =>
        dut.io.start #= false
        dut.clockDomain.forkStimulus(10)
        dut.clockDomain.waitSampling(5)
        trace.reset(0, 0); trace.reset(1, 0)
        dut.io.start #= true
        val reference = new SerializedMemoryReference(Seq.fill[Byte](8)(0))
        val registers = Array(0L, 0L)
        var serial = 0L
        def bytes(value: BigInt) = (0 until 4).map(i => ((value >> (8*i)) & 255).toByte)
        val orders = Array(0, 0); val ended = Array(false, false)
        var cycle = 0L
        while (!ended.forall(identity) && cycle < 100) {
          // Sample accepted instructions before their state-update edge.
          dut.clockDomain.waitFallingEdge(); sleep(1)
          cycle += 1
          for ((h, id) <- dut.harts.zipWithIndex if !ended(id)) {
            if (h.io.done.toBoolean) { trace.complete(id, cycle, Status.Pass); ended(id) = true }
            else if (h.io.retired.toBoolean) {
              val insn = h.io.insn.toLong
              val load = (insn & 127) == 3; val store = (insn & 127) == 35
              val value = h.io.value.toBigInt
              val result = if (load) h.io.rdata.toBigInt else if ((insn & 127) == 19)
                (if (((insn >> 15) & 31) == 0) BigInt(0) else value) + (insn >> 20) else BigInt(0)
              val pc = h.io.pc.toBigInt
              val idKey = s"hart-$id-${orders(id)}"
              var readFrom = Vector.empty[String]
              if (load || store) {
                val address = h.io.address.toBigInt.toInt
                if (store) reference.write(serial, idKey, address,
                  bytes(BigInt(registers(id))), bytes(h.io.wdata.toBigInt), 15)
                else {
                  readFrom = reference.read(serial, idKey, address, bytes(result))
                  registers(id) = reference.expected(address,4).zipWithIndex.map {
                    case (b,i) => (b.toLong & 255) << (i*8)
                  }.sum
                }
                serial += 1
              } else if ((insn & 127) == 19) {
                val source = if (((insn >> 15)&31) == 0) 0L else registers(id)
                registers(id) = source + (insn.toInt >> 20)
                assert(result == registers(id), "independent register result")
              }
              trace.retire(id, RvfiRecord(orders(id), cycle, insn, false, false, false, 3, 1,
                ((insn >> 15) & 31).toInt, if (((insn >> 15) & 31) == 0) BigInt(0) else value, if (store) 1 else 0, if (store) value else BigInt(0),
                if (load || (insn & 127) == 19) 1 else 0, result, pc,
                if ((insn & 127) == 99 && value == 0) pc - 4 else pc + 4,
                if (load || store) h.io.address.toBigInt else BigInt(0), if (load) 15 else 0,
                if (store) 15 else 0, if (load) result else BigInt(0), if (store) value else BigInt(0), false))
              if (load || store) trace.memory(cycle, s"hart-$id-${orders(id)}",
                if (store) "write" else "read", ujson.Obj("source" -> s"hart-$id",
                  "address" -> Hex(h.io.address.toBigInt), "data" -> Hex(if (store) value else result),
                  "mask" -> "0xf", "hart" -> id, "order" -> orders(id).toString,
                  "serialization" -> (serial-1).toString, "boundary" -> "fixture-serialized-ram",
                  "read_from" -> ujson.Arr.from(readFrom)))
              orders(id) += 1
            }
          }
          dut.clockDomain.waitRisingEdge(); sleep(1)
        }
        assert(ended.forall(identity), "bounded two-hart fixture did not finish")
        assert(dut.io.result.toBigInt == 38) // Independent program expectation.
        assert(trace.outcome(cycle, orders.sum).status == Status.Pass)
      }
    } finally {
      trace.close()
      org.apache.commons.io.FileUtils.deleteDirectory(work)
    }
  }
}
