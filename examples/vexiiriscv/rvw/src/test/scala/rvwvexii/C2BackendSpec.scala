package rvwvexii

import org.scalatest.funsuite.AnyFunSuite
import riscvsim.RvfiRecord
import scala.collection.mutable.ArrayBuffer

class C2BackendSpec extends AnyFunSuite {
  test("late RTL FP flag writeback belongs to its FP retirement only") {
    val rows = ArrayBuffer.empty[RvfiRecord]
    val backend = new C2Backend(64, () => 1L, () => 3, () => (BigInt(0), BigInt(0)),
      r => rows += r, (_, _, _, _) => (), (_, _, _) => (),
      fpSnapshot = Some(() => (BigInt(0x60), BigInt(0x1800))), lateFlags = () => BigInt(1))
    backend.commit(0, 0x80000000L, 0x00000053L)
    backend.commit(0, 0x80000004L, 0x13L)
    backend.drain()
    assert(rows.head.fpState.get.fcsr == 0x61)
    assert(rows(1).fpState.get.fcsr == 0x60)
  }

  test("mret CSR state comes from the later observed return apply edge") {
    val rows = ArrayBuffer.empty[RvfiRecord]
    val backend = new C2Backend(64, () => 1L, () => 3, () => (BigInt(0), BigInt(0)),
      r => rows += r, (_, _, _, _) => (), (_, _, _) => (),
      fpSnapshot = Some(() => (BigInt(0), BigInt(0x1800))))
    backend.commit(0, 0x80000000L, 0x30200073L)
    backend.returnStatus(BigInt(0x1880))
    backend.commit(0, 0x80000004L, 0x13L)
    assert(rows.head.csrState(0x300) == 0x1880)
    assertThrows[IllegalStateException](backend.returnStatus(BigInt(0)))
  }

  test("compressed encoding keeps the expanded probe destination and raw instruction length") {
    val rows = ArrayBuffer.empty[RvfiRecord]
    val backend = new C2Backend(64, () => 1L, () => 3, () => (BigInt(0), BigInt(0)),
      r => rows += r, (_, _, _, _) => (), (_, _, _) => (), instructionAt = Some(_ => 0x4085L))
    backend.writeRf(0, 0, 32, Array[Byte](1, 0, 0, 0, 0, 0, 0, 0))
    backend.commit(0, 0x80000000L, 0x00100093L)
    backend.drain()
    assert(rows.head.insn == 0x4085 && rows.head.rd == 1 && rows.head.rdWdata == 1)
    assert(rows.head.pcNext == BigInt("80000002", 16))
  }

  test("FP writes include f0 and keep boxed 64-bit values on RV32") {
    val rows = ArrayBuffer.empty[RvfiRecord]
    var fcsr = BigInt(0x61)
    val backend = new C2Backend(32, () => 1L, () => 3, () => (BigInt(0), BigInt(0)),
      r => rows += r, (_, _, _, _) => (), (_, _, _) => (),
      fpSnapshot = Some(() => (fcsr, BigInt(0x6000))))
    backend.writeRf(0, 1, 32, Array[Byte](0, 0, -128, 63, -1, -1, -1, -1))
    backend.commit(0, 0x80000000L, 0x00000053L)
    fcsr = 0
    backend.commit(0, 0x80000004L, 0x13L)
    backend.drain()
    val fp = rows.head.fpState.get
    assert(fp.valid && fp.destination == 0 && fp.data == BigInt("ffffffff3f800000", 16))
    assert(fp.flags == 1 && fp.fcsr == 0x61)
    assert(rows.head.rd == 0 && rows.head.csrState(0x300) == 0x6000)
    assert(!rows(1).fpState.get.valid && rows(1).fpState.get.fcsr == 0)
  }

  test("lookahead holds the current cycle until the observed next PC arrives") {
    var cycle = 1L
    val rows = ArrayBuffer.empty[RvfiRecord]
    val backend = new C2Backend(32, () => cycle, () => 3, () => (BigInt(0), BigInt(0)),
      r => rows += r, (_, _, _, _) => (), (_, _, _) => ())
    backend.commit(0, 0x80000000L, 0x13)
    assert(rows.isEmpty && backend.pendingCycle.contains(1))
    cycle = 4
    backend.commit(0, 0x80000004L, 0x13)
    assert(rows.size == 1 && rows.head.pcNext == BigInt("80000004", 16))
    assert(rows.head.cycle == 1 && backend.pendingCycle.contains(4))
    backend.drain()
    assert(rows.map(_.order).toSeq == Seq(BigInt(0), BigInt(1)))
    assert(backend.pendingCycle.isEmpty)
  }

  test("interrupt trap value is the observed value, without a fabricated zero") {
    val observed = ArrayBuffer.empty[BigInt]
    val backend = new C2Backend(32, () => 10L, () => 3, () => (BigInt(0), BigInt(0x123)),
      _ => (), (_, _, value, _) => observed += value, (_, _, _) => ())
    backend.trap(0, true, 7)
    assert(observed.toSeq == Seq(BigInt(0x123)))
  }
  test("AMO records keep both independently observed memory effects") {
    val rows = ArrayBuffer.empty[RvfiRecord]
    val backend = new C2Backend(64, () => 1L, () => 3, () => (BigInt(0), BigInt(0)),
      r => rows += r, (_, _, _, _) => (), (_, _, _) => ())
    backend.loadExecute(0, 0, 0x80001000L, 4, Array[Byte](1, 0, 0, 0))
    backend.storeExecute(0, 0, 0x80001000L, 4, Array[Byte](2, 0, 0, 0))
    backend.loadCommit(0, 0)
    backend.storeCommit(0, 0)
    backend.commit(0, 0x80000000L, 0x202f)
    backend.drain()
    assert(rows.head.memRmask == 15 && rows.head.memWmask == 15)
    assert(rows.head.memRdata == 1 && rows.head.memWdata == 2)
    assert(rows.head.ixl == 2)
  }

  test("I/O data comes from the observed device transaction") {
    val rows = ArrayBuffer.empty[RvfiRecord]
    val backend = new C2Backend(64, () => 1L, () => 3, () => (BigInt(0), BigInt(0)),
      r => rows += r, (_, _, _, _) => (), (_, _, _) => ())
    backend.regs(1) = BigInt("02000000", 16)
    backend.ioAccess(0, new rvls.spinal.TraceIo(false, 0x02000000L, Array[Byte](7, 0, 0, 0), 15, 4, false))
    backend.commit(0, 0x80000000L, 0x0000a103L) // lw x2, 0(x1)
    backend.drain()
    assert(rows.head.memAddr == BigInt("02000000", 16))
    assert(rows.head.memRdata == 7 && rows.head.memRmask == 15)
  }

  test("failed SC does not fabricate a memory write") {
    val rows = ArrayBuffer.empty[RvfiRecord]
    val backend = new C2Backend(64, () => 1L, () => 3, () => (BigInt(0), BigInt(0)),
      r => rows += r, (_, _, _, _) => (), (_, _, _) => ())
    backend.storeConditional(0, true)
    backend.storeCommit(0, 0)
    backend.commit(0, 0x80000000L, 0x1800202fL)
    backend.drain()
    assert(rows.head.memWmask == 0)
  }

  test("observed virtual addresses preserve physical store completion") {
    val rows = ArrayBuffer.empty[RvfiRecord]
    val writes = ArrayBuffer.empty[BigInt]
    val backend = new C2Backend(64, () => 1L, () => 3, () => (BigInt(0), BigInt(0)),
      r => rows += r, (_, _, _, _) => (), (address, _, _) => writes += address,
      (_, _, _) => -4096L)
    backend.storeExecute(0, 0, 0x80200000L, 4, Array[Byte](7, 0, 0, 0))
    backend.storeCommit(0, 0)
    backend.commit(0, 0x80000000L, 0x2023L)
    backend.drain()
    assert(rows.head.memAddr == BigInt("fffffffffffff000", 16))
    assert(writes.toSeq == Seq(BigInt("80200000", 16)))
  }

}
