package rvwvexii

import java.io.File
import java.nio.file.Files
import java.security.MessageDigest
import java.util.zip.{ZipEntry, ZipFile, ZipOutputStream}
import spinal.core.sim._
import riscvsim._
import vexiiriscv.fetch.FetchCachelessPlugin
import vexiiriscv.execute.lsu.LsuCachelessPlugin
import vexiiriscv.misc.PrivilegedPlugin
import vexiiriscv.test.WhiteboxerPlugin

/** Explicit single-clock loop: no scheduler threads or upstream probe state to restore. */
object BootSlices {
  def main(args: Array[String]): Unit = {
    require(args.length == 7, "ELF PAYLOADS MAP OUT CHECKPOINT fresh|restore STOP-CYCLE")
    val elf = new ElfFile(new File(args(0)))
    val boot = BootImage.fromManifest(elf, new File(args(1)))
    val map = SimMap.load(new File(args(2)))
    val out = new File(args(3)); require(!out.exists(), "output already exists"); out.mkdirs()
    val checkpoint = new File(args(4)); val restore = args(5) == "restore"
    require(restore || args(5) == "fresh", "unknown mode")
    val stop = args(6).toLong
    def window(name: String, maximum: Long): Option[(Long,Long)] = sys.env.get(name).map { text =>
      val fields = text.split(":"); require(fields.length == 2, s"$name needs FROM:TO cycles")
      val from = fields(0).toLong; val to = fields(1).toLong
      require(from >= 0 && to > from && to-from <= maximum, s"$name exceeds its bounded window")
      (from,to)
    }
    val traceWindow = window("RVW_BOOT_TRACE", 65536)
    val waveWindow = window("RVW_BOOT_WAVE", 4096)
    val maskTimer = window("RVW_BOOT_MASK_TIMER", Long.MaxValue)
    val ram = map.regions.filter(_.kind == "ram"); require(ram.size == 1)
    val base = ram.head.base.toLong; val size = ram.head.size.toInt
    require(size > 0 && size <= 128 * 1024 * 1024)
    val memory = new ByteMemory(base, size)
    boot.load { (a, bytes) => bytes.indices.foreach(i => memory(a + i) = bytes(i) & 255) }
    val devices = new LiveDevices(map)
    sys.props("rvwvexii.bootMap") = new File(args(2)).getCanonicalPath
    val bridge = new BridgeState
    val config = bridge.instrument(VexiiTop.spinalConfig.copy(headerWithDate = false, headerWithRepoHash = false))
    val sim = SimConfig.withConfig(config).withVerilator
      .workspacePath(sys.env.getOrElse("RVW_BOOT_WORK", new File(out.getParentFile, "boot-native").getPath))
    if (waveWindow.nonEmpty) sim.withFstWave
    val compiled = sim.compile(VexiiTop("rv64imacsu_linux", probeTap = false, bootTrace = true))
    def hash(bytes: Array[Byte]) = MessageDigest.getInstance("SHA-256").digest(bytes).map(b => f"${b & 255}%02x").mkString
    val rtl = new File(compiled.compiledPath, "rtl").listFiles().filter(_.getName.endsWith(".v")).sortBy(_.getName)
    val identity = ujson.Obj("rtl" -> hash(rtl.flatMap(f => Files.readAllBytes(f.toPath))),
      "inputs" -> ujson.Arr.from(boot.identities.map { case (_, digest) => ujson.Str(digest) }),
      "map" -> map.sha256, "base" -> base.toString, "size" -> size,
      "harness" -> hash(getClass.getResourceAsStream("BootSlices$.class").readAllBytes()),
      "memory" -> hash(classOf[ByteMemory].getResourceAsStream("ByteMemory.class").readAllBytes()),
      "bridge" -> hash(classOf[BridgeState].getResourceAsStream("BridgeState.class").readAllBytes()),
      "trace" -> hash(classOf[BootTrace].getResourceAsStream("BootTrace.class").readAllBytes()),
      "reference_inputs" -> hash(classOf[BootInputs].getResourceAsStream("BootInputs.class").readAllBytes()),
      "devices" -> hash(Seq("LiveDevices", "LiveDevices$Device", "LiveDevices$Uart", "LiveDevices$Clint", "LiveDevices$Plic", "LiveDevices$Poweroff").flatMap(n =>
        classOf[LiveDevices].getResourceAsStream(n + ".class").readAllBytes()).toArray))
    val saved = if (restore) {
      val zip = new ZipFile(checkpoint)
      try {
        val bytes = zip.getInputStream(zip.getEntry("state.json")).readAllBytes()
        val envelope = ujson.read(bytes)
        val s = envelope("state")
        require(hash(ujson.write(s).getBytes("UTF-8")) == envelope("sha256").str, "state digest mismatch")
        require(s("schema").str == "rvw.vexii-boot-slice/1" && s("identity") == identity, "checkpoint identity mismatch")
        val image = zip.getInputStream(zip.getEntry("ram.bin"))
        try memory.restore(image) finally image.close()
        require(memory.sha256 == s("ram_sha256").str, "RAM digest mismatch")
        Some(s)
      } finally zip.close()
    } else None
    var cycle = saved.map(_("cycle").str.toLong).getOrElse(0L)
    var retired = saved.map(_("retired").str.toLong).getOrElse(0L)
    require(stop > cycle, "stop must follow restored cycle")
    var lastLevels = BigInt(0)
    var lastDeviceLevels = BigInt(0)
    var waveCycleOne = 0L
    var waveOriginTime = 0L
    var traceRecords = 0L
    val byMode = saved.map(_("retired_by_mode").arr.map(_.str.toLong).toArray).getOrElse(Array.fill(4)(0L))
    var lastMode = saved.map(_("mode").num.toInt).getOrElse(3)
    def address(value: BigInt, width: Int): BigInt = if (width < 64 && value.testBit(width-1)) value | (((BigInt(1)<<64)-1) ^ ((BigInt(1)<<width)-1)) else value
    var lastPc = saved.map(_("pc").str).getOrElse("0x0")
    var lastTrap: ujson.Value = saved.map(_("trap")).getOrElse(ujson.Null)
    var reservation = saved.flatMap(s => if (s("reservation") == ujson.Null) None else Some(s("reservation").str.toLong))
    // One-cycle response policy, including a response for every LSU command.
    type Response = Option[(BigInt, Boolean, Int, Boolean)]
    def decode(v: ujson.Value): Response = if (v == ujson.Null) None else Some((BigInt(v(0).str), v(1).bool, v(2).num.toInt, v(3).bool))
    def encode(v: Response): ujson.Value = v.map { case (d,e,id,sc) => ujson.Arr(d.toString,e,id,sc) }.getOrElse(ujson.Null)
    var ip: Response = saved.flatMap(s => decode(s("ibus")))
    var dp: Response = saved.flatMap(s => decode(s("dbus")))
    def inRam(a: Long, n: Int) = a >= base && a <= base + size - n
    def read(a: Long, n: Int): BigInt = (0 until n).foldLeft(BigInt(0))((v,i) => v | (BigInt(memory.getOrElse(a+i,0)) << (8*i)))
    val wallLimit = sys.env.get("RVW_BOOT_SECONDS").map(_.toDouble)
    require(wallLimit.forall(v => v > 0 && !v.isInfinity && !v.isNaN), "invalid wall limit")
    var wallExpired = false
    val startCycle = cycle; val startRetired = retired; val startTime = System.nanoTime()
    compiled.doSim(seed = 1) { dut =>
      if (waveWindow.nonEmpty) disableSimWave()
      val cd = dut.clockDomain
      val ib = dut.host[FetchCachelessPlugin].logic.bus
      val db = dut.host[LsuCachelessPlugin].logic.bus
      val priv = dut.host[PrivilegedPlugin].logic.harts(0)
      val tap = dut.host[TrapTapPlugin].logic
      val commits = dut.host[WhiteboxerPlugin].logic.commits.ports
      val referenceInputs = new BootInputs(saved.map(_("reference_inputs")),
        sys.env.get("RVW_BOOT_REFERENCE_INPUTS").map { flag => require(Set("0","1")(flag)); flag == "1" })
      val trace = new BootTrace(dut.host[BootTraceTap].logic.port, out,
        ujson.Obj("xlen" -> 64, "isa" -> "rv64imac_zicsr_zifencei_zicntr", "core" -> "vexiiriscv",
          "config" -> "rv64imacsu_linux", "elf" -> elf.file.getPath, "elf_sha256" -> boot.identities.head._2,
          "external_interrupts" -> ujson.Obj("schema" -> "rvw.external-interrupts/1", "map_sha256" -> map.sha256),
          "rtl_sha256" -> identity("rtl"), "seed" -> 1, "mem_latency" -> 1),
        traceWindow, saved.map(_("trace_memory")), referenceInputs)
      def inputs(): Unit = {
        val observed = devices.tick(cycle)
        lastDeviceLevels = observed
        val levels = if (maskTimer.exists { case (from,to) => cycle >= from && cycle < to }) observed.clearBit(7) else observed
        lastLevels = levels
        priv.int.m.timer #= levels.testBit(7); priv.int.m.software #= levels.testBit(3)
        priv.int.m.external #= levels.testBit(11); priv.int.s.external #= levels.testBit(9)
        dut.host[PrivilegedPlugin].logic.rdtime #= cycle
        ib.cmd.ready #= true; ib.rsp.valid #= ip.nonEmpty
        ib.rsp.word #= ip.map(_._1).getOrElse(BigInt(0)); ib.rsp.error #= ip.exists(_._2); ib.rsp.id #= ip.map(_._3.toLong).getOrElse(0L)
        db.cmd.ready #= true; db.rsp.valid #= dp.nonEmpty
        db.rsp.data #= dp.map(_._1).getOrElse(BigInt(0)); db.rsp.error #= dp.exists(_._2)
        db.rsp.id #= dp.map(_._3.toLong).getOrElse(0L); db.rsp.scMiss #= dp.exists(_._4)
      }
      cd.clockSim #= false; cd.resetSim #= true; inputs(); sleep(5)
      for (_ <- 0 until 5) { cd.clockSim #= true; sleep(5); cd.clockSim #= false; sleep(5) }
      cd.resetSim #= false; sleep(1)
      saved.foreach { s => devices.restore(s("devices")); bridge.restore(s("rtl")); inputs(); sleep(1)
        require(bridge.capture() == s("rtl"), "RTL restore readback mismatch") }
      // A restored process starts its simulator clock near zero. Debug tools
      // need this offset to map cumulative logical cycles to FST time.
      waveOriginTime = simTime() + 1
      waveCycleOne = waveOriginTime + (1-cycle) * 11
      while (cycle < stop && !wallExpired && !devices.poweroff) {
        waveWindow.foreach { case (from,to) =>
          if (cycle == from) enableSimWave()
          if (cycle == to) disableSimWave()
        }
        inputs(); sleep(1)
        val ni: Response = if (ib.cmd.valid.toBoolean) {
          val n = ib.p.dataWidth / 8; val a = ib.cmd.address.toLong & ~(n-1L)
          Some((read(a,n), !inRam(a,n), ib.cmd.id.toInt, false))
        } else None
        val nd: Response = if (db.cmd.valid.toBoolean) {
          val c = db.cmd; val n = db.p.dataWidth / 8; val address = c.address.toLong
          val a = address & ~(n-1L); val width = 1 << c.size.toInt; val shift = (address-a).toInt*8
          val mask = (BigInt(1) << (width*8))-1
          val atomic = c.amoEnable.toBoolean; val op = if (atomic) c.amoOp.toInt else -1
          val old = read(a,n); val miss = op == 3 && !reservation.contains(a)
          val write = if (atomic) op != 2 && !miss else c.write.toBoolean
          val data = if (atomic && op != 2 && op != 3)
            (BigInt(vexiiriscv.test.VexiiRiscvProbe.amoWriteValue(op,width,(c.data.toBigInt>>shift).toLong,(old>>shift).toLong)) & mask) << shift
            else c.data.toBigInt
          val device = devices.contains(address,width)
          require(!device || !atomic, "device atomic unsupported")
          if (write && inRam(a,n)) {
            for (i <- 0 until n if (c.mask.toInt & (1<<i)) != 0) memory(a+i) = ((data>>(8*i))&255).toInt
            reservation = None
          }
          if (op == 2 && inRam(a,n)) reservation = Some(a)
          if (op == 3) reservation = None
          if (device && write) devices.write(address,width,(data>>shift)&mask)
          val result = if (device && !write) devices.read(address,width)<<shift else if (atomic || !write) old else BigInt(0)
          if (c.fromHart.toBoolean) trace.observe(c.uopId.toLong,address,
            if ((!atomic && !write) || (atomic && op != 3)) (result >> shift) & mask else BigInt(0),
            if (write) (data >> shift) & mask else BigInt(0),
            if ((!atomic && !write) || (atomic && op != 3)) (1<<width)-1 else 0,
            if (write) (1<<width)-1 else 0, !inRam(a,n) && !device, device)
          Some((result, !inRam(a,n) && !device, c.id.toInt, miss))
        } else None
        trace.sample(cycle, lastLevels, if (tap.fire.toBoolean) Some((tap.epc.toBigInt,tap.cause.toBigInt,tap.tval.toBigInt)) else None)
        commits.foreach(p => if (p.valid.toBoolean) { retired += 1; lastPc = Hex(address(p.pc.toBigInt,p.pc.getBitsWidth)); lastMode = tap.privilege.toInt & 3; byMode(lastMode) += 1 })
        if (tap.fire.toBoolean) lastTrap = ujson.Obj("cycle" -> cycle.toString, "epc" -> Hex(tap.epc.toBigInt), "tval" -> Hex(tap.tval.toBigInt), "cause" -> Hex(tap.cause.toBigInt))
        cd.clockSim #= true; sleep(5); cd.clockSim #= false; sleep(5)
        cycle += 1; ip = ni; dp = nd
        if ((cycle & 1023) == 0) wallExpired = wallLimit.exists((System.nanoTime()-startTime)/1e9 >= _)
      }
      trace.finish(cycle); traceRecords = trace.count
      if (waveWindow.nonEmpty) { sleep(1); disableSimWave() }
      // No edge follows capture. A fresh process reconstructs all inputs before its first edge.
      val state = ujson.Obj("schema" -> "rvw.vexii-boot-slice/1", "identity" -> identity,
        "cycle" -> cycle.toString, "retired" -> retired.toString, "pc" -> lastPc, "trap" -> lastTrap,
        "mode" -> lastMode, "retired_by_mode" -> ujson.Arr.from(byMode.map(_.toString)), "irq_levels" -> Hex(lastLevels),
        "reservation" -> reservation.map(v => ujson.Str(v.toString)).getOrElse(ujson.Null),
        "ram_sha256" -> memory.sha256, "ibus" -> encode(ip), "dbus" -> encode(dp), "devices" -> devices.snapshot(),
        "trace_memory" -> trace.state, "reference_inputs" -> referenceInputs.snapshot, "rtl" -> bridge.capture())
      val temp = new File(checkpoint.getPath + ".partial")
      val zip = new ZipOutputStream(Files.newOutputStream(temp.toPath))
      try {
        zip.putNextEntry(new ZipEntry("state.json"))
        zip.write(ujson.write(ujson.Obj("state" -> state, "sha256" -> hash(ujson.write(state).getBytes("UTF-8")))).getBytes("UTF-8")); zip.closeEntry()
        zip.putNextEntry(new ZipEntry("ram.bin")); memory.save(zip); zip.closeEntry()
      } finally zip.close()
      Files.move(temp.toPath, checkpoint.toPath, java.nio.file.StandardCopyOption.REPLACE_EXISTING)
    }
    val seconds = (System.nanoTime()-startTime)/1e9
    val result = ujson.Obj("schema" -> "rvw.vexii-boot-slice-result/1", "status" -> (if (devices.poweroff) "shutdown" else "bounded"),
      "cycle" -> cycle.toString, "retired" -> retired.toString, "pc" -> lastPc, "trap" -> lastTrap,
        "mode" -> lastMode, "retired_by_mode" -> ujson.Arr.from(byMode.map(_.toString)), "irq_levels" -> Hex(lastLevels),
      "slice_cycles" -> (cycle-startCycle).toString, "slice_retired" -> (retired-startRetired).toString,
      "wall_seconds" -> seconds, "cycles_per_second" -> ((cycle-startCycle)/seconds),
      "instructions_per_second" -> ((retired-startRetired)/seconds), "console" -> devices.outputs,
      "trace_records" -> traceRecords.toString, "wave_time_of_cycle_1" -> waveCycleOne.toString,
      "wave_cycle_origin" -> startCycle.toString, "wave_time_origin" -> waveOriginTime.toString,
      "device_irq_levels" -> Hex(lastDeviceLevels),
      "timer_mask" -> maskTimer.map { case (from,to) => ujson.Arr(from.toString,to.toString) }.getOrElse(ujson.Null))
    Files.writeString(new File(out,"result.json").toPath, ujson.write(result,indent=2))
    println(ujson.write(result))
  }
}
