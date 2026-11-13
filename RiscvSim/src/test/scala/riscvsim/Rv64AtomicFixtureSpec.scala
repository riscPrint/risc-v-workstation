package riscvsim

import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite
import org.scalatest.BeforeAndAfterAll
import spinal.core.sim._

/** Concurrent .d effects in the bounded subset fixture, not production-core proof. */
class Rv64AtomicFixtureSpec extends AnyFunSuite with BeforeAndAfterAll {
  private val work = Files.createTempDirectory("rv64-atomic-fixture").toFile
  private lazy val compiled = SimConfig.withVerilator.workspacePath(work.getPath).compile(new AtomicFixture(64))
  override def afterAll(): Unit = org.apache.commons.io.FileUtils.deleteDirectory(work)
  private def add(value: Int): Long = ((value.toLong & 4095) << 20) | (1 << 7) | 0x13
  private def atomic(op: Int, flags: Int): Long = (op.toLong << 27) | (flags.toLong << 25) | ((if (op == 2) 0 else 1) << 20) | (3 << 12) | (2 << 7) | 47
  private val operands = Seq(BigInt(1) << 40, (BigInt(1) << 64)-1)
  private def campaign(op: Int, flags: Int, seed: Int, fault: Int = 0, reservations: Boolean = false, cas: Boolean = false): Unit = {
    compiled.doSim(seed = seed) { dut =>
      dut.io.enable #= 0; dut.io.fault #= fault; dut.io.evict #= false
      dut.io.instructions.foreach(_ #= 0)
      dut.clockDomain.forkStimulus(10); dut.clockDomain.waitSampling(5)
      val observer = new AtomicMemoryObserver(Seq.fill[Byte](16)(0), Set(0, 1), 8, 3, "fixture round robin every eight cycles")
      var serial = 0L
      var cycle = 0L
      val orders = Array(0, 0)
      val lrIds = scala.collection.mutable.Map.empty[Int, String]
      val trace = if (fault == 0 && !cas) sys.env.get("RVW_RV64_TRACE_OUT").map { root =>
        val file = new java.io.File(root, s"op-$op-flags-$flags-reservation-$reservations.jsonl")
        new MultiHartTrace(file, ujson.Obj("xlen" -> 64, "isa" -> "rv64ia", "core" -> "subset-fixture",
          "config" -> "two", "elf" -> "programmable", "memory_dependencies" -> "complete", "memory_addresses" -> "physical"), Seq(0, 1))
      } else None
      trace.foreach { t => t.reset(0, 0); t.reset(1, 0) }
      def falling(): Unit = { dut.clockDomain.waitFallingEdge(); cycle += 1 }
      def capture(h: Int, instruction: Long, old: BigInt, after: BigInt, pc: BigInt, before: BigInt): Unit = {
        val opcode = (instruction & 127).toInt
        val operation = (instruction >> 27).toInt
        val atomic = opcode == 47
        val lr = atomic && operation == 2
        val sc = atomic && operation == 3
        val write = opcode == 35 || (atomic && !lr && (!sc || old == 0))
        val read = atomic && !sc
        val rd = if (opcode == 35) 0 else ((instruction >> 7) & 31).toInt
        val rs1 = ((instruction >> 15) & 31).toInt
        val rs2 = if (atomic || opcode == 35) ((instruction >> 20) & 31).toInt else 0
        val rdData = if (opcode == 19) dut.harts(h).io.registers(rd).toBigInt else if (atomic) old else BigInt(0)
        val id = s"h$h-op${orders(h)}"
        val model = if (read || write) {
          val m = ujson.Obj("id" -> id, "hart" -> h, "order" -> orders(h),
            "kind" -> (if (lr) "LR" else if (sc) "SC" else if (atomic) "AMO" else "W"),
            "address" -> 0, "size" -> 8, "addr" -> ujson.Arr(), "data" -> ujson.Arr(), "ctrl" -> ujson.Arr())
          if (read) m("read") = ujson.Str(old.toString)
          if (write) m("write") = ujson.Str(after.toString)
          // Full-width values are decimal strings in annotations to retain precision.
          if (lr) lrIds(h) = id
          if (sc) m("rmw") = lrIds(h)
          Some(m)
        } else None
        trace.foreach(_.retire(h, RvfiRecord(orders(h), cycle, instruction, false, false, false, 3, 2,
          rs1, if (rs1 == 0) BigInt(0) else before, rs2, if (rs2 == 0) BigInt(0) else before,
          rd, rdData, pc, pc+4, 0, if (read) 255 else 0, if (write) 255 else 0,
          if (read) old else BigInt(0), if (write) after else BigInt(0), false), model))
        orders(h) += 1
      }
      def execute(hart: Int, instruction: Long)(check: (BigInt, BigInt) => Unit): Unit = {
        falling()
        dut.io.instructions(hart) #= instruction; dut.io.enable #= (1 << hart)
        sleep(1)
        var waits = 0
        while (!dut.harts(hart).io.retired.toBoolean && waits < 16) {
          falling(); sleep(1); waits += 1
        }
        assert(waits < 16, "fixture service bound")
        val pc = dut.harts(hart).io.pc.toBigInt
        val before = dut.harts(hart).io.registers(1).toBigInt
        val old = dut.harts(hart).io.rdata.toBigInt
        dut.clockDomain.waitSampling(); sleep(1)
        val after = dut.io.memory(0).toBigInt
        check(old, after)
        if (!cas) capture(hart, instruction, old, after, pc, before)
        dut.io.enable #= 0; dut.io.instructions(hart) #= 0
      }
      try {
      execute(0, add(1))((_, _) => ())
      execute(0, (40L << 20) | (1 << 15) | (1 << 12) | (1 << 7) | 0x13)((_, _) => ())
      execute(1, add(-1))((_, _) => ())
      assert(dut.harts(0).io.registers(1).toBigInt == operands(0))
      assert(dut.harts(1).io.registers(1).toBigInt == operands(1))
      if (reservations) {
        execute(0, atomic(2, flags)) { (old, _) => observer.loadReserved(serial, 0, 0, 8, old); serial += 1 }
        execute(1, (1 << 20) | (3 << 12) | 35) { (_, after) =>
          observer.store(serial, 1, 0, 8, operands(1), after); serial += 1
        }
        execute(0, atomic(3, flags)) { (status, after) =>
          observer.storeConditional(serial, 0, 0, 8, operands(0), status == 0, after, constrained = false); serial += 1
        }
      } else {
        var enabled = 3
        val compare = Array.fill[BigInt](2)(0)
        var casSuccesses = 0
        var failedHart = -1
        def referenceWord: BigInt = observer.bytes(0, 8).zipWithIndex.map { case (b, i) => BigInt(b & 255) << (8*i) }.sum
        var cycles = 0
        val random = new scala.util.Random(seed)
        while (enabled != 0 && cycles < 64) {
          falling()
          // Bounded enable gaps retain both-hart contention on most slots.
          val drive = if (cycles % 3 == 2) enabled else enabled & random.nextInt(4)
          dut.io.enable #= drive
          for (h <- 0 until 2) dut.io.instructions(h) #= atomic(op, flags)
          sleep(1)
          val accepted = (0 until 2).filter(h => (drive & (1 << h)) != 0 && dut.harts(h).io.retired.toBoolean)
            .map(h => (h, dut.harts(h).io.rdata.toBigInt, dut.harts(h).io.pc.toBigInt, dut.harts(h).io.registers(1).toBigInt))
          dut.clockDomain.waitSampling(); sleep(1)
          for ((hart, old, pc, before) <- accepted) {
            if (cas) {
              val beforeReference = referenceWord
              observer.compareSwap(serial, hart, 0, 8, compare(hart), operands(hart), old, dut.io.memory(0).toBigInt)
              if (compare(hart) == beforeReference) casSuccesses += 1 else failedHart = hart
              compare(hart) = beforeReference
            } else observer.amo(serial, hart, 0, 8,
              Map(0 -> "add", 1 -> "swap", 4 -> "xor", 8 -> "or", 12 -> "and", 16 -> "min", 20 -> "max", 24 -> "minu", 28 -> "maxu")(op),
              operands(hart), old, dut.io.memory(0).toBigInt)
            if (!cas) capture(hart, atomic(op, flags), old, dut.io.memory(0).toBigInt, pc, before)
            serial += 1; enabled &= ~(1 << hart)
          }
          dut.io.enable #= 0
          cycles += 1
        }
        assert(enabled == 0, "both RV64 harts must complete")
        if (cas) {
          assert(casSuccesses == 1 && failedHart >= 0, "one CAS must fail under contention")
          execute(failedHart, atomic(5, flags)) { (old, after) =>
            observer.compareSwap(serial, failedHart, 0, 8, compare(failedHart), operands(failedHart), old, after)
          }
        }
        assert(observer.bytes(8, 8) == Vector.fill[Byte](8)(0) && dut.io.memory(1).toBigInt == 0, "adjacent guard word")
      }
      trace.foreach { t => t.complete(0, cycle+1, Status.Pass); t.complete(1, cycle+1, Status.Pass) }
      } finally trace.foreach(_.close())
    }
  }
  test("concurrent RV64 AMOs cover all operations and aq/rl encodings") {
    for (op <- Seq(0, 1, 4, 8, 12, 16, 20, 24, 28); flags <- 0 until 4)
      campaign(op, flags, seed = 7+flags)
  }
  test("RV64 LR/SC observes external reservation invalidation") {
    for (flags <- 0 until 4) campaign(0, flags, 7, reservations = true)
  }
  test("RV64 observer rejects torn AMOs, wrong return data and lost invalidation") {
    intercept[IllegalArgumentException](campaign(0, 3, 7, fault = 2))
    intercept[IllegalArgumentException](campaign(0, 3, 7, fault = 3))
    intercept[IllegalArgumentException](campaign(0, 3, 7, fault = 1, reservations = true))
    intercept[org.scalatest.exceptions.TestFailedException](campaign(0, 3, 7, fault = 15))
  }
  test("RV64 CAS checks contention, failed-CAS byte retention and a valid retry") {
    for (flags <- 0 until 4) campaign(5, flags, seed = 7+flags, cas = true)
  }
  test("RV64 CAS rejects missing writes, torn data, failed-CAS writes and wrong old values") {
    for (fault <- Seq(12, 2, 13, 3))
      intercept[IllegalArgumentException](campaign(5, 3, 7, fault = fault, cas = true))
  }

}
