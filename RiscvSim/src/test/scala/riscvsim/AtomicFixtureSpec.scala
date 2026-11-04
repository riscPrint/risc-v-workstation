package riscvsim

import java.nio.file.{Files, Paths}
import org.scalatest.funsuite.AnyFunSuite
import org.scalatest.BeforeAndAfterAll
import spinal.core.sim._

class AtomicFixtureSpec extends AnyFunSuite with BeforeAndAfterAll {
  private val work = Files.createTempDirectory("atomic-fixture").toFile
  private lazy val compiled = SimConfig.withVerilator.workspacePath(work.getPath).compile(new AtomicFixture)
  override def afterAll(): Unit = org.apache.commons.io.FileUtils.deleteDirectory(work)
  private val mask = 0xffffffffL
  private def add(rd: Int, value: Int): Long = ((value.toLong & 4095) << 20) | (rd << 7) | 0x13
  private def load(rd: Int, address: Int = 0): Long = (address << 20) | (2 << 12) | (rd << 7) | 3
  private def store(rs: Int, address: Int = 0): Long = ((address & 31) << 7) | (rs << 20) | (2 << 12) | 35
  private def amo(op: Int, rd: Int, rs: Int, flags: Int = 0): Long =
    (op.toLong << 27) | (flags << 25) | (rs << 20) | (2 << 12) | (rd << 7) | 47
  private def effect(op: Int, old: Long, arg: Long): Long = (op match {
    case 0 => old + arg; case 1 => arg; case 4 => old ^ arg; case 8 => old | arg; case 12 => old & arg
    case 16 => if (old.toInt < arg.toInt) old else arg
    case 20 => if (old.toInt > arg.toInt) old else arg
    case 24 => old.min(arg); case 28 => old.max(arg)
  }) & mask

  /** Expected bytes and registers depend only on programs, not DUT read data. */
  private def run(programs: Seq[Seq[Long]], seed: Int = 0, fault: Int = 0, checkValues: Boolean = true, invalidate: Boolean = false, scBound: Int = 0): Seq[Array[Long]] = {
    val regs = Seq.fill(2)(Array.fill[Long](32)(0))
    val actual = Seq.fill(2)(Array.fill[Long](32)(0))
    compiled.doSim(seed = seed) { dut =>
      dut.io.enable #= 0; dut.io.fault #= fault; dut.io.evict #= false
      dut.io.instructions.foreach(_ #= 0)
      dut.clockDomain.forkStimulus(10); dut.clockDomain.waitSampling(5)
      val mem = Array.fill[Long](2)(0)
      val reservation = Array.fill(2)(-1)
      val pcs = Array(0, 0)
      val attempts = Array(0, 0)
      val succeeded = Array(false, false)
      val pending = Array.fill[Option[String]](2)(None)
      val progress = new ProgressMonitor(32, 2, "round-robin slot every 8 cycles; enable within 3 cycles; immediate memory response")
      val fairness = new FairnessMonitor(Set("0","1"), 2, 32)
      val coherence = new CoherenceMonitor(4, Set(0, 1))
      val rng = new scala.util.Random(seed)
      var cycle = 0L
      while ((pcs.indices.exists(i => pcs(i) < programs(i).size) || pending.exists(_.nonEmpty)) && cycle < 400) {
        dut.clockDomain.waitFallingEdge()
        for (i <- 0 until 2) {
          assert(dut.harts(i).io.pc.toLong == pcs(i)*4, "fixture PC")
          dut.io.instructions(i) #= programs(i).lift(pcs(i)).getOrElse(0L)
        }
        // Fixed, bounded environment stalls, separate from the arbiter under test.
        dut.io.enable #= (0 until 2).filter(i =>
          // Reservation test barriers: LR first, then external store, then SC.
          (!invalidate || (if (i == 1) pcs(0) > 0 else pcs(0) < programs(0).size-1 || pcs(1) >= programs(1).size-1)) &&
          (cycle%3 == 2 || rng.nextBoolean())).map(1 << _).sum
        sleep(1); cycle += 1
        for (i <- 0 until 2) {
          val h = dut.harts(i)
          if (h.io.request.toBoolean && pending(i).isEmpty) {
            val id = s"$i:${pcs(i)}"; progress.request(id, cycle); pending(i) = Some(id)
          }
          if (fault == 6) pending(i).foreach(progress.retry(_, cycle))
          if (h.io.retired.toBoolean) {
            val insn = programs(i)(pcs(i)); val op = (insn & 127).toInt
            val rd = ((insn >> 7)&31).toInt; val rs1 = ((insn >> 15)&31).toInt; val rs2 = ((insn >> 20)&31).toInt
            val r = regs(i)
            if (Set(3,35,47)(op)) {
              val imm = if (op == 35) ((insn >> 25)<<5) | ((insn>>7)&31) else if (op == 3) insn>>20 else 0L
              val addr = r(rs1) + imm; assert(addr == 0 || addr == 4)
              assert(h.io.address.toLong == addr, "memory address")
              val word = (addr/4).toInt; val old = mem(word); val arg = r(rs2)
              val fn = (insn >>> 27).toInt
              val isSc = op == 47 && fn == 3
              // SC may fail spuriously. Its result chooses the legal branch;
              // the independent memory oracle still checks every byte effect.
              val scResult = if (isSc) h.io.rdata.toLong else 1L
              if (isSc && scResult == 0) assert(reservation(i) == word, "reservation invalidation: SC success without reservation")
              val success = isSc && scResult == 0
              if (isSc && scBound > 0) {
                attempts(i) += 1; succeeded(i) ||= success
                assert(success || attempts(i) < scBound, "constrained SC service bound exceeded")
              }
              val result = if (op == 47 && fn == 3) { if (success) 0L else 1L } else old
              if (op != 35 && checkValues) assert(h.io.rdata.toLong == result, "atomic/load returned value or reservation invalidation")
              val writes = op == 35 || (op == 47 && fn != 2 && (fn != 3 || success))
              if (writes) {
                mem(word) = if (op == 35 || fn == 3) arg else effect(fn, old, arg)
                if (reservation(1-i) == word) reservation(1-i) = -1
              }
              if (op == 47 && fn == 2) reservation(i) = word
              if (op == 47 && fn == 3) reservation(i) = -1
              if (op != 35 && rd != 0) r(rd) = result
              pending(i).foreach(progress.complete(_, cycle)); pending(i) = None
            } else if (op == 19 && rd != 0) r(rd) = (r(rs1) + (insn.toInt >> 20)) & mask
            else if (op == 99) {
              val imm = (((insn >> 31)&1)<<12) | (((insn>>7)&1)<<11) | (((insn>>25)&63)<<5) | (((insn>>8)&15)<<1)
              val offset = (imm.toInt << 19) >> 19
              val equal = r(rs1) == r(rs2)
              if (equal != (((insn >> 12)&1) == 1)) pcs(i) += offset/4 - 1
            } else assert(op == 19 || op == 15, "unsupported fixture instruction")
            pcs(i) += 1
          }
        }
        if (fault == 0) {
          val offered = (0 until 2).filter { i =>
            val h = dut.harts(i)
            val op = (h.io.insn.toLong & 127).toInt
            !h.io.done.toBoolean && Set(3,35,47)(op) &&
              (!invalidate || (if (i == 1) pcs(0) > 0 else pcs(0) < programs(0).size-1 || pcs(1) >= programs(1).size-1))
          }.map(_.toString).toSet
          val enabled = (0 until 2).filter(i => (dut.io.enable.toInt & (1 << i)) != 0).map(_.toString).toSet
          val granted = (0 until 2).filter(i => dut.harts(i).io.request.toBoolean && dut.harts(i).io.ready.toBoolean).map(_.toString).toSet
          fairness.sample(cycle, offered, enabled, granted)
        }
        progress.check(cycle)
        dut.clockDomain.waitRisingEdge(); sleep(1)
        // Independent continuous memory observer catches partial or missing writes.
        for (w <- 0 until 2) assert(dut.io.memory(w).toLong == mem(w), "indivisible memory effect")
        for (i <- 0 until 2; r <- 0 until 32 if checkValues) assert(dut.harts(i).io.registers(r).toLong == regs(i)(r), "register effect")
        val observed = (0 until 4).map(n => Seq("N","B","T")(dut.io.permissions(n).toInt))
        // Completed downgrades must precede conflicting grants at this fixture boundary.
        for (i <- 0 until 2; w <- 0 until 2) {
          val from = coherence.state(i,w*4); val to = observed(i*2+w)
          if (from != to && (to == "N" || (from == "T" && to == "B")))
            coherence.shrink(i,w*4,from,to,from == "T",dut.io.transfer.toBoolean)
        }
        for (i <- 0 until 2; w <- 0 until 2) {
          val to = observed(i*2+w)
          if (coherence.state(i,w*4) != to) coherence.grant(i,w*4,to)
        }
      }
      assert(pcs.indices.forall(i => pcs(i) == programs(i).size), "bounded campaign incomplete")
      for (i <- 0 until 2; r <- 0 until 32) actual(i)(r) = dut.harts(i).io.registers(r).toLong
      if (scBound > 0) assert(succeeded(0), "constrained loop did not complete SC")
      progress.finish(cycle)
      if (fault == 0) fairness.finish(programs.indices.filter(i =>
        programs(i).exists(insn => Set(3,35,47)((insn & 127).toInt))).map(_.toString).toSet)
      dut.io.enable #= 0; dut.io.evict #= true
      dut.clockDomain.waitSampling(); sleep(1)
      for (i <- 0 until 2; w <- 0 until 2) {
        val from = coherence.state(i,w*4)
        if (from != "N") coherence.shrink(i,w*4,from,"N",from == "T",dut.io.transfer.toBoolean)
        assert(dut.io.permissions(i*2+w).toInt == 0, "eviction permission")
        assert(dut.io.memory(w).toLong == mem(w), "eviction/writeback data")
      }
    }
    actual
  }
  private def reservationPrograms = Seq(
    Seq(amo(2,2,0)) ++ Seq.fill(12)(add(10,0)) ++ Seq(add(3,9),amo(3,4,3)),
    Seq(add(3,7)) ++ Seq.fill(4)(add(10,0)) ++ Seq(store(3),load(5)))
  private def atomicPrograms(op: Int, flags: Int) = Seq(
    Seq(add(3,-1),amo(op,4,3,flags),load(5)),
    Seq(load(6),add(3,1),amo(0,7,3,flags),load(8)))

  test("LR/SC external invalidation, absent reservation and constrained success") {
    for (flags <- 0 until 4) {
      val programs = reservationPrograms.map(_.map(insn =>
        if ((insn & 127) == 47) insn | (flags.toLong << 25) else insn))
      assert(run(programs, seed=flags, invalidate=true)(0)(4) == 1)
    }
    val r = run(Seq(Seq(add(3,9),amo(3,4,3),amo(2,2,0),amo(3,5,3)),Seq(load(6))))
    assert(r(0)(4) == 1 && r(0)(5) == 0)
  }
  // LR; SC; BNE x4,x0,-8. No loads, stores or forbidden instructions
  // occur in the retry path. The loop fits in 16 consecutive instructions.
  private def constrainedPrograms = Seq(
    Seq(add(3,9), amo(2,2,0), amo(3,4,3), 0xfe021ce3L, load(5)),
    Seq(add(10,1)))
  test("constrained LR/SC retries legal spurious failures under bounded service") {
    for (flags <- 0 until 4; seed <- 0 until 4) {
      val programs = constrainedPrograms.map(_.map(insn =>
        if ((insn & 127) == 47) insn | (flags.toLong << 25) else insn))
      val r = run(programs, seed=seed, fault=10, scBound=4)
      assert(r(0)(4) == 0 && r(0)(5) == 9)
    }
  }
  test("fault: constrained LR/SC service never permits success") {
    val e = intercept[org.scalatest.exceptions.TestFailedException](
      run(constrainedPrograms, fault=11, scBound=4))
    assert(e.getMessage.contains("constrained SC service bound exceeded"))
  }
  test("all word AMOs and aq/rl encodings with concurrent observers") {
    for (op <- Seq(0,1,4,8,12,16,20,24,28); flags <- 0 until 4)
      run(atomicPrograms(op,flags),seed = flags)
  }
  test("fault: external store fails to invalidate reservation") {
    val e = intercept[org.scalatest.exceptions.TestFailedException](run(reservationPrograms, fault=1, invalidate=true))
    assert(e.getMessage.contains("reservation invalidation"))
  }
  test("fault: torn AMO effect") {
    val e = intercept[org.scalatest.exceptions.TestFailedException](run(atomicPrograms(1,0),fault=2))
    assert(e.getMessage.contains("indivisible memory effect"))
  }
  test("fault: wrong returned old value") {
    val e = intercept[org.scalatest.exceptions.TestFailedException](run(atomicPrograms(0,0),fault=3))
    assert(e.getMessage.contains("returned value"))
  }
  test("fault: conflicting ownership grant") {
    val e = intercept[IllegalArgumentException](run(reservationPrograms,fault=4, invalidate=true))
    assert(e.getMessage.contains("exclusive grant before invalidation"))
  }
  test("fault: dirty intervention omits data") {
    val e = intercept[IllegalArgumentException](run(atomicPrograms(1,0),fault=7))
    assert(e.getMessage.contains("dirty owner lost data"))
  }
  for ((fault,name) <- Seq(5 -> "starvation despite other-hart completion", 6 -> "retry livelock")) {
    test(s"fault: $name") {
      val e = intercept[IllegalArgumentException](run(atomicPrograms(0,0),fault=fault))
      assert(e.getMessage.contains("bounded forward progress exceeded"))
    }
  }
  test("pinned official litmus programs with concurrent observers") {
    val input = sys.env.getOrElse("RVW_FIXTURE_PLAN", fail("set RVW_FIXTURE_PLAN; missing litmus plan is not a pass"))
    val plan = ujson.read(Files.readString(Paths.get(input)))
    def samples(fault: Int) = plan.arr.map { row =>
      val programs = row("programs").arr.map(_.arr.map(_.num.toLong).toSeq).toSeq
      val observations = (0 until 32).map { seed =>
        val regs = run(programs, seed, fault, checkValues = fault == 0)
        val state = ujson.Obj.from(row("projection").arr.map { key =>
          val Array(h,r) = key.str.split(":x"); key.str -> ujson.Num(regs(h.toInt)(r.toInt).toDouble)
        })
        ujson.Obj("state" -> state,"count" -> 1)
      }
      ujson.Obj("test" -> row("test"),"harts" -> 2,"complete" -> true,"observations" -> ujson.Arr.from(observations))
    }
    Files.writeString(Paths.get(sys.env("RVW_FIXTURE_OUT")),ujson.write(ujson.Arr.from(samples(0)),indent=2))
    Files.writeString(Paths.get(sys.env("RVW_FIXTURE_OUT") + ".fault.json"),ujson.write(ujson.Arr.from(samples(9)),indent=2))
  }
}
