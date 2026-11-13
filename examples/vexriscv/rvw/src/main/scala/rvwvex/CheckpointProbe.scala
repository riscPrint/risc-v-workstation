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
    require(args.length >= 5 && args.length <= 7, "ELF OUT CHECKPOINT save|restore|replay|bootstrap RETIREMENT [BOOT-IMAGE|-] [SIM-MAP]")
    val elfFile = new File(args(0)); val out = new File(args(1)); out.mkdirs()
    val checkpoint = new File(args(2)); val mode = args(3); val at = args(4).toLong
    require(Set("save", "restore", "replay", "bootstrap")(mode) && at > 0)
    val map = if (args.length == 7) Some(SimMap.load(new File(args(6)))) else None
    val devices = map.map(new LiveDevices(_))
    val maxCycles = sys.env.getOrElse("RVW_BOOT_MAX_CYCLES", "5000").toLong
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
    identity("device_map") = map.map(m => ujson.Str(m.sha256)).getOrElse(ujson.Null)
    if (devices.nonEmpty) identity("device_code") = hash(Seq("LiveDevices", "LiveDevices$Device", "LiveDevices$Uart", "LiveDevices$Clint", "LiveDevices$Plic").flatMap { name =>
      classOf[LiveDevices].getResourceAsStream(name + ".class").readAllBytes().toSeq
    }.toArray)
    val saved = if (mode == "restore" || mode == "replay") Some({
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
    val header = ujson.Obj("xlen" -> 32, "core" -> "vexriscv", "config" -> "rv32im", "elf" -> elfFile.getCanonicalPath, "isa" -> "rv32im_zicsr_zifencei")
    val writer = new RvfiTraceWriter(new File(out, "rvfi.jsonl"), header, resume = saved.map(_("writer")))
    def read(a: Long): BigInt = (0 until 4).foldLeft(BigInt(0))((v, i) => v | (BigInt(memory.getOrElse(a + i, 0)) << (8*i)))
    def mapped(a: Long): Boolean = a >= 0x80000000L && a < 0x81000000L
    def pending(p: Option[(BigInt, Boolean)]): ujson.Value = p.map { case (v, e) => ujson.Arr(v.toString, e) }.getOrElse(ujson.Null)
    def decode(v: ujson.Value): Option[(BigInt, Boolean)] = if (v == ujson.Null) None else Some(BigInt(v(0).str) -> v(1).bool)
    var captured = false
    val boot = if (mode == "bootstrap") Some(ujson.read(Files.readString(new File(args(5)).toPath))) else None
    boot.foreach { b =>
      require(b("schema").str == "rvw.vex-bootstrap-image/1")
      b("memory").arr.foreach { row =>
        val a = row("address").num.toLong
        val bytes = row("hex").str.grouped(2).map(Integer.parseInt(_, 16)).toSeq
        require(mapped(a) && mapped(a + bytes.size - 1), "bootstrap memory outside RAM")
        bytes.indices.foreach(i => memory(a + i) = bytes(i))
      }
    }
    var transferred = boot.isEmpty
    var nativeOrder = saved.map(_("retired").str.toLong).getOrElse(0L)
    try compiled.doSim(seed = 1) { dut =>
      val cd = dut.clockDomain
      cd.clockSim #= false; cd.resetSim #= true
      dut.csr.timerInterrupt #= false; dut.csr.softwareInterrupt #= false
      dut.csr.externalInterrupt #= false; Option(dut.csr.externalInterruptS).foreach(_ #= false)
      def inputs(): Unit = {
        val levels = devices.map(_.tick(cycle)).getOrElse(BigInt(0))
        dut.csr.timerInterrupt #= levels.testBit(7)
        dut.csr.softwareInterrupt #= levels.testBit(3)
        dut.csr.externalInterrupt #= levels.testBit(11)
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
        devices.foreach(_.restore(s("devices")))
        bridge.restore(s("rtl")); inputs(); sleep(1)
        val restored = bridge.capture()
        val changed = restored("registers").arr.zip(s("rtl")("registers").arr).zipWithIndex.collect {
          case ((a, b), i) if a != b => s"${restored("layout")("registers")(i)(0).str}: $a != $b"
        }
        require(restored == s("rtl"), "restore readback mismatch: " + changed.mkString(", "))
      }
      var finished = false
      while (!finished && cycle < maxCycles) {
        inputs(); sleep(1)
        cycle += 1
        val ni = if (dut.ibus.cmd.valid.toBoolean) {
          val a = dut.ibus.cmd.pc.toLong & ~3L; Some(read(a) -> !mapped(a))
        } else None
        val nd = if (dut.dbus.cmd.valid.toBoolean) {
          val address = dut.dbus.cmd.address.toLong
          val a = address & ~3L
          val bytes = 1 << dut.dbus.cmd.size.toInt
          val lane = (address & 3).toInt
          val device = devices.filter(_.contains(address, bytes))
          if (dut.dbus.cmd.wr.toBoolean) {
            device match {
              case Some(d) => d.write(address, bytes, (dut.dbus.cmd.data.toBigInt >> (8*lane)) & ((BigInt(1) << (8*bytes)) - 1))
              case None =>
                require(mapped(a), "store outside RAM")
                for (i <- 0 until 4 if (dut.dbus.cmd.mask.toInt & (1 << i)) != 0)
                  memory(a + i) = ((dut.dbus.cmd.data.toBigInt >> (8*i)) & 255).toInt
            }
            None
          } else Some(device.map(_.read(address, bytes) << (8*lane)).getOrElse(read(a)) -> (!mapped(a) && device.isEmpty))
        } else None
        if (dut.traps.valid.toBoolean) {
          val cause = dut.traps.cause.toBigInt
          writer.trap(cycle, cause, dut.traps.tval.toBigInt, cause.testBit(31)); handler = true
        }
        if (dut.rvfi.valid.toBoolean) {
          val r = VexAdapter.record(dut.rvfi, cycle, handler); handler = false
          require(r.order == nativeOrder, s"order ${r.order} expected $nativeOrder"); nativeOrder += 1
          if (boot.exists(b => BigInt(b("pc").str) == r.pc)) transferred = true
          if (transferred) {
            require(boot.nonEmpty || r.order == retired, s"order ${r.order} expected $retired")
            writer.write(r.copy(order = BigInt(retired))); retired += 1
          }
          if (r.memWmask != 0 && r.memAddr == BigInt(ToHost.find(elf).get)) {
            require(r.memWdata == 1, "program failed"); finished = true
          }
        }
        cd.clockSim #= true; sleep(5); cd.clockSim #= false; sleep(5)
        ip = ni; dp = nd
        if ((mode == "save" || mode == "replay") && !captured && retired == at) {
          val state = ujson.Obj("schema" -> "rvw.vex-bridge-probe/1", "identity" -> identity,
            "cycle" -> cycle.toString, "retired" -> retired.toString, "handler" -> handler,
            "ibus" -> pending(ip), "dbus" -> pending(dp), "rtl" -> bridge.capture(),
            "memory" -> ujson.Arr.from(memory.toSeq.sortBy(_._1).map { case (a, v) => ujson.Arr(a.toString, v) }),
            "writer" -> writer.checkpoint(), "devices" -> devices.map(_.snapshot()).getOrElse(ujson.Null))
          Files.writeString(checkpoint.toPath, ujson.write(ujson.Obj("state" -> state,
            "sha256" -> hash(ujson.write(state).getBytes("UTF-8"))))); captured = true
        }
      }
      require(finished && transferred, "core did not finish after transfer")
      require(!Set("save", "replay")(mode) || captured, "checkpoint retirement not reached")
      writer.end(cycle, "pass")
      devices.foreach(d => Files.writeString(new File(out, "devices.json").toPath, d.outputs.render()))
    } finally writer.close()
  }
}
