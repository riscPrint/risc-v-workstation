package rvwvex

import java.io.File
import java.nio.file.Files
import java.security.MessageDigest
import spinal.core._
import spinal.core.sim._
import riscvsim._
import scala.collection.mutable

/** Bounded real-core checkpoint probe. No JVM threads or reset replay are saved. */
object CheckpointProbe {
  def main(args: Array[String]): Unit = {
    require(args.length == 5, "ELF OUT CHECKPOINT save|restore RETIREMENT")
    val elfFile = new File(args(0)); val out = new File(args(1)); out.mkdirs()
    val checkpoint = new File(args(2)); val mode = args(3); val at = args(4).toLong
    require(Set("save", "restore")(mode) && at > 0)
    val bridge = new BridgeState
    val config = bridge.instrument(VexTop.spinalConfig.copy(headerWithDate = false, headerWithRepoHash = false))
    val compiled = SimConfig.withConfig(config).withVerilator
      .workspacePath(new File(out, "native").getAbsolutePath).compile(new VexTop)
    def hash(bytes: Array[Byte]): String = MessageDigest.getInstance("SHA-256").digest(bytes).map(b => f"${b & 255}%02x").mkString
    val rtl = new File(compiled.compiledPath, "rtl")
    val rtlBytes = rtl.listFiles().filter(_.getName.endsWith(".v")).sortBy(_.getName).flatMap(f => Files.readAllBytes(f.toPath))
    val identity = ujson.Obj("rtl" -> hash(rtlBytes), "elf" -> hash(Files.readAllBytes(elfFile.toPath)),
      "harness" -> hash(getClass.getResourceAsStream("CheckpointProbe$.class").readAllBytes()),
      "bridge" -> hash(classOf[BridgeState].getResourceAsStream("BridgeState.class").readAllBytes()))
    val saved = if (mode == "restore") Some({
      val envelope = ujson.read(Files.readString(checkpoint.toPath))
      require(hash(ujson.write(envelope("state")).getBytes("UTF-8")) == envelope("sha256").str,
        "checkpoint digest mismatch")
      val state = envelope("state")
      require(state("schema").str == "rvw.vex-bridge-probe/1", "unsupported checkpoint schema")
      state
    }) else None
    saved.foreach(s => require(s("identity") == identity, "checkpoint input identity mismatch"))
    val elf = new ElfFile(elfFile)
    val memory = mutable.LongMap.empty[Int]
    elf.load { (address, bytes) => bytes.indices.foreach(i => memory(address + i) = bytes(i) & 255) }
    var cycle = 0L; var retired = 0L; var handler = false
    var ip = Option.empty[(BigInt, Boolean)]; var dp = Option.empty[(BigInt, Boolean)]
    val header = ujson.Obj("xlen" -> 32, "core" -> "vexriscv", "isa" -> "rv32im_zicsr_zifencei")
    val writer = new RvfiTraceWriter(new File(out, "rvfi.jsonl"), header, resume = saved.map(_("writer")))
    def read(a: Long): BigInt = (0 until 4).foldLeft(BigInt(0))((v, i) => v | (BigInt(memory.getOrElse(a + i, 0)) << (8*i)))
    def mapped(a: Long): Boolean = a >= 0x80000000L && a < 0x81000000L
    def pending(p: Option[(BigInt, Boolean)]): ujson.Value = p.map { case (v, e) => ujson.Arr(v.toString, e) }.getOrElse(ujson.Null)
    def decode(v: ujson.Value): Option[(BigInt, Boolean)] = if (v == ujson.Null) None else Some(BigInt(v(0).str) -> v(1).bool)
    var captured = false
    try compiled.doSim(seed = 1) { dut =>
      val cd = dut.clockDomain
      cd.clockSim #= false; cd.resetSim #= true
      dut.csr.timerInterrupt #= false; dut.csr.softwareInterrupt #= false
      dut.csr.externalInterrupt #= false; Option(dut.csr.externalInterruptS).foreach(_ #= false)
      def inputs(): Unit = {
        dut.ibus.cmd.ready #= true; dut.ibus.rsp.valid #= ip.nonEmpty
        dut.ibus.rsp.inst #= ip.map(_._1).getOrElse(BigInt(0)); dut.ibus.rsp.error #= ip.exists(_._2)
        dut.dbus.cmd.ready #= true; dut.dbus.rsp.ready #= dp.nonEmpty
        dut.dbus.rsp.data #= dp.map(_._1).getOrElse(BigInt(0)); dut.dbus.rsp.error #= dp.exists(_._2)
      }
      inputs(); sleep(5)
      for (_ <- 0 until 5) { cd.clockSim #= true; sleep(5); cd.clockSim #= false; sleep(5) }
      cd.resetSim #= false; sleep(1)
      saved.foreach { s =>
        memory.clear(); s("memory").arr.foreach(r => memory(r(0).str.toLong) = r(1).num.toInt)
        cycle = s("cycle").str.toLong; retired = s("retired").str.toLong; handler = s("handler").bool
        ip = decode(s("ibus")); dp = decode(s("dbus"))
        bridge.restore(s("rtl")); inputs(); sleep(1)
      }
      var finished = false
      while (!finished && cycle < 5000) {
        inputs(); sleep(1)
        cycle += 1
        val ni = if (dut.ibus.cmd.valid.toBoolean) {
          val a = dut.ibus.cmd.pc.toLong & ~3L; Some(read(a) -> !mapped(a))
        } else None
        val nd = if (dut.dbus.cmd.valid.toBoolean) {
          val a = dut.dbus.cmd.address.toLong & ~3L
          if (dut.dbus.cmd.wr.toBoolean) {
            require(mapped(a), "store outside RAM")
            for (i <- 0 until 4 if (dut.dbus.cmd.mask.toInt & (1 << i)) != 0)
              memory(a + i) = ((dut.dbus.cmd.data.toBigInt >> (8*i)) & 255).toInt
            None
          } else Some(read(a) -> !mapped(a))
        } else None
        if (dut.traps.valid.toBoolean) {
          val cause = dut.traps.cause.toBigInt
          writer.trap(cycle, cause, dut.traps.tval.toBigInt, cause.testBit(31)); handler = true
        }
        if (dut.rvfi.valid.toBoolean) {
          val r = VexAdapter.record(dut.rvfi, cycle, handler); handler = false
          require(r.order == retired, s"order ${r.order} expected $retired")
          retired += 1; writer.write(r)
          if (r.memWmask != 0 && r.memAddr == BigInt(ToHost.find(elf).get)) {
            require(r.memWdata == 1, "program failed"); finished = true
          }
        }
        cd.clockSim #= true; sleep(5); cd.clockSim #= false; sleep(5)
        ip = ni; dp = nd
        if (mode == "save" && !captured && retired == at) {
          val state = ujson.Obj("schema" -> "rvw.vex-bridge-probe/1", "identity" -> identity,
            "cycle" -> cycle.toString, "retired" -> retired.toString, "handler" -> handler,
            "ibus" -> pending(ip), "dbus" -> pending(dp), "rtl" -> bridge.capture(),
            "memory" -> ujson.Arr.from(memory.toSeq.sortBy(_._1).map { case (a, v) => ujson.Arr(a.toString, v) }),
            "writer" -> writer.checkpoint())
          Files.writeString(checkpoint.toPath, ujson.write(ujson.Obj("state" -> state,
            "sha256" -> hash(ujson.write(state).getBytes("UTF-8"))))); captured = true
        }
      }
      require(finished, "core did not finish")
      require(mode != "save" || captured, "checkpoint retirement not reached")
      writer.end(cycle, "pass")
    } finally writer.close()
  }
}
