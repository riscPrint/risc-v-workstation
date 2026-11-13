package riscvsim

import java.io.File
import spinal.core._
import spinal.core.sim._
import scala.collection.mutable

/** One top-level port of a Verilog core. */
case class MappedPort(name: String, input: Boolean, width: Int)

/** A memory port of the core, by top-level port names.
  *
  * `req-rsp`: the core presents a request (`cmd_valid`, optional `cmd_ready`, `address`,
  * optional `write`, `wdata`, `mask`). Responses come back in request order on `rsp_valid`,
  * `rdata` and optional `error`, after the selected latency. Writes get a response only with
  * `write_response`. A missing `cmd_ready` means the core needs no ready.
  *
  * `valid-ready`: one handshake per access (PicoRV32 `mem_*` style). The core holds `valid`,
  * `address`, `wdata` and `mask` (`wstrb`) until the model raises `ready` for one cycle with
  * `rdata`. A nonzero mask is a write. */
case class MappedBus(name: String, protocol: String, signals: Map[String, String], writeResponse: Boolean)

/** Project-owned description of a core for [[MappedAdapter]]: `rvw.core-map/1`. */
case class CoreMap(file: File, core: String, config: String, isa: String, xlen: Int,
                   topClass: Option[String], verilog: Option[CoreMap.Verilog],
                   resetPc: Long, ramBase: Long, ramSize: Long, buses: Seq[MappedBus],
                   rvfiPrefix: Option[String], irq: Map[Int, String], constants: Map[String, BigInt]) {
  def dir: File = file.getAbsoluteFile.getParentFile
}

object CoreMap {
  case class Verilog(module: String, files: Seq[File], defines: Map[String, String],
                     parameters: Map[String, Any], ports: Seq[MappedPort],
                     clock: String, reset: String, resetActiveLow: Boolean)

  val protocols = Map(
    "req-rsp" -> (Set("cmd_valid", "address", "rsp_valid", "rdata"),
      Set("cmd_ready", "write", "wdata", "mask", "error", "rsp_ready")),
    "valid-ready" -> (Set("valid", "ready", "address", "rdata"), Set("wdata", "mask")))

  private def num(v: ujson.Value): BigInt = v match {
    case ujson.Str(s) if s.startsWith("0x") || s.startsWith("0X") => BigInt(s.drop(2), 16)
    case ujson.Str(s) => BigInt(s)
    case ujson.Num(n) => BigInt(n.toLong)
    case other => throw new IllegalArgumentException(s"core map: expected a number, got $other")
  }

  def parse(file: File, text: String): CoreMap = {
    val j = ujson.read(text).obj
    def need(k: String) = j.getOrElse(k, throw new IllegalArgumentException(s"core map: missing '$k'"))
    require(need("schema").str == "rvw.core-map/1", "core map: schema must be rvw.core-map/1")
    val known = Set("schema", "core", "config", "isa", "xlen", "top", "reset_pc", "ram", "buses", "rvfi", "irq", "constants")
    val unknown = j.keySet.toSet -- known
    require(unknown.isEmpty, s"core map: unknown fields ${unknown.toSeq.sorted.mkString(", ")}")
    val dir = file.getAbsoluteFile.getParentFile
    val top = need("top").obj
    val (topClass, verilog) = top("kind").str match {
      case "spinal" => (Some(top("class").str), None)
      case "verilog" =>
        val ports = top("ports").arr.map { p =>
          val dir = p("dir").str
          require(dir == "in" || dir == "out", s"core map: port ${p("name").str} has direction $dir; only in and out are supported")
          MappedPort(p("name").str, dir == "in", p("width").num.toInt)
        }.toSeq
        val v = Verilog(top("module").str, top("files").arr.map(f => new File(dir, f.str).getCanonicalFile).toSeq,
          top.get("defines").map(_.obj.map { case (k, v) => k -> v.str }.toMap).getOrElse(Map.empty),
          top.get("parameters").map(_.obj.map { case (k, v) => k -> (v match {
            case ujson.Num(n) => BigInt(n.toLong): Any
            case ujson.Str(s) => s: Any
            case ujson.Bool(b) => b: Any
            case other => throw new IllegalArgumentException(s"core map: parameter $k has value $other")
          }) }.toMap).getOrElse(Map.empty),
          ports, top("clock").str, top("reset").str, top.get("reset_active").forall(_.str == "low"))
        require(v.files.forall(_.isFile), s"core map: missing Verilog file in ${v.files.mkString(", ")}")
        for (n <- Seq(v.clock, v.reset)) require(ports.exists(p => p.name == n && p.input && p.width == 1),
          s"core map: clock/reset $n must be a 1-bit input port")
        (None, Some(v))
      case other => throw new IllegalArgumentException(s"core map: top kind must be spinal or verilog, not $other")
    }
    val buses = need("buses").arr.map { b =>
      val protocol = b("protocol").str
      val (required, optional) = protocols.getOrElse(protocol,
        throw new IllegalArgumentException(s"core map: bus protocol must be one of ${protocols.keys.mkString(", ")}"))
      val signals = b("signals").obj.collect { case (k, ujson.Str(v)) => k -> v }.toMap
      val missing = required -- signals.keySet
      require(missing.isEmpty, s"core map: bus ${b("name").str} lacks ${missing.mkString(", ")}")
      val extra = signals.keySet -- required -- optional
      require(extra.isEmpty, s"core map: bus ${b("name").str} has unknown signals ${extra.mkString(", ")}")
      MappedBus(b("name").str, protocol, signals, b.obj.get("write_response").exists(_.bool))
    }.toSeq
    require(buses.nonEmpty, "core map: at least one bus is required")
    val ram = need("ram").obj
    val xlen = need("xlen").num.toInt
    require(xlen == 32 || xlen == 64, "core map: xlen must be 32 or 64")
    CoreMap(file, need("core").str, j.get("config").map(_.str).getOrElse("default"), need("isa").str, xlen,
      topClass, verilog, num(need("reset_pc")).toLong, num(ram("base")).toLong, num(ram("size")).toLong, buses,
      j.get("rvfi").flatMap(r => if (r.isNull) None else Some(r("prefix").str)),
      j.get("irq").map(_.obj.map { case (k, v) => k.toInt -> v.str }.toMap).getOrElse(Map.empty),
      j.get("constants").map(_.obj.map { case (k, v) => k -> num(v) }.toMap).getOrElse(Map.empty))
  }

  def load(file: File): CoreMap = parse(file, new String(java.nio.file.Files.readAllBytes(file.toPath), "UTF-8"))
}

/** A Spinal top level that wraps one Verilog module and exposes its ports under the same names. */
class VerilogCoreTop(v: CoreMap.Verilog) extends Component {
  private def hw(p: MappedPort): Data = if (p.width == 1) Bool() else Bits(p.width bits)
  class Core extends BlackBox {
    setDefinitionName(v.module)
    for ((k, value) <- v.parameters) value match {
      case i: BigInt if i.isValidInt => addGeneric(k, i.toInt)
      case i: BigInt => addGeneric(k, B(i, math.max(32, i.bitLength) bits))
      case s: String => addGeneric(k, s)
      case b: Boolean => addGeneric(k, b)
    }
    val ports: Map[String, Data] = v.ports.map(p => p.name -> (if (p.input) in(hw(p)) else out(hw(p))).setName(p.name)).toMap
    v.files.foreach(f => addRTLPath(f.getPath))
  }
  val core = new Core
  val reset = ClockDomain.current.readResetWire
  core.ports(v.clock).asInstanceOf[Bool] := ClockDomain.current.readClockWire
  core.ports(v.reset).asInstanceOf[Bool] := (if (v.resetActiveLow) !reset else reset)
  val io: Map[String, Data] = v.ports.filterNot(p => p.name == v.clock || p.name == v.reset).map { p =>
    val port = (if (p.input) in(hw(p)) else out(hw(p))).setName(p.name)
    if (p.input) core.ports(p.name) := port else port := core.ports(p.name)
    p.name -> port
  }.toMap
}

/** Reads one riscv-formal RVFI channel (NRET 1) from named signals. `mem_fault`
  * and `ixl` are optional. */
class MappedRvfi(prefix: String, lookup: String => Option[Data]) {
  private def need(n: String): Data = lookup(n).getOrElse(
    throw new IllegalArgumentException(s"core map RVFI prefix '$prefix' has no port $prefix$n"))
  private val names = Seq("order", "insn", "trap", "halt", "intr", "mode", "rs1_addr", "rs2_addr", "rs1_rdata",
    "rs2_rdata", "rd_addr", "rd_wdata", "pc_rdata", "pc_wdata", "mem_addr", "mem_rmask", "mem_wmask", "mem_rdata",
    "mem_wdata")
  private val valid = need("valid")
  private val f: Map[String, Data] = names.map(n => n -> need(n)).toMap
  private val memFault = lookup("mem_fault")
  private val ixl = lookup("ixl")
  private def big(d: Data): BigInt = d match {
    case b: Bool => if (b.toBoolean) 1 else 0
    case v: BitVector => v.toBigInt
  }
  private def n(k: String) = big(f(k))
  def sample(cycle: Long): Option[RvfiRecord] = if (big(valid) == 0) None else Some(RvfiRecord(
    order = n("order"), cycle = cycle, insn = n("insn").toLong, trap = n("trap") != 0, halt = n("halt") != 0,
    intr = n("intr") != 0, mode = n("mode").toInt, ixl = ixl.map(big(_).toInt).getOrElse(0),
    rs1 = n("rs1_addr").toInt, rs1Rdata = n("rs1_rdata"), rs2 = n("rs2_addr").toInt, rs2Rdata = n("rs2_rdata"),
    rd = n("rd_addr").toInt, rdWdata = n("rd_wdata"), pc = n("pc_rdata"), pcNext = n("pc_wdata"),
    memAddr = n("mem_addr"), memRmask = n("mem_rmask").toInt, memWmask = n("mem_wmask").toInt,
    memRdata = n("mem_rdata"), memWdata = n("mem_wdata"), memFault = memFault.exists(big(_) != 0)))
}

/** A generic C1 adapter for a core described by a [[CoreMap]]. It names no core signals itself. */
class MappedAdapter(val map: CoreMap) extends CoreAdapter {
  override def freshInstancePerRun = true
  type Model = SimCompiled[Component]
  def core: String = map.core
  def configs: Seq[String] = Seq(map.config)
  def isa(config: String): String = map.isa
  def xlen: Int = map.xlen
  override def irqInputMask: BigInt = map.irq.keys.foldLeft(BigInt(0))((m, b) => m.setBit(b))
  def sourceDir: File = new File(sys.env.getOrElse("RVW_CORE_SOURCE", map.dir.getParent)).getCanonicalFile
  override def replayEnv: Seq[(String, String)] = Seq("RVW_CORE_SOURCE" -> sourceDir.getPath)

  private def top(): Component = map.verilog match {
    case Some(v) => new VerilogCoreTop(v)
    case None => Class.forName(map.topClass.get).getDeclaredConstructor().newInstance().asInstanceOf[Component]
  }
  private def check(key: ModelKey): Unit = {
    require(!key.konata, "mapped adapter does not support Konata")
    require(!key.spinaltrace, "mapped adapter does not support SpinalTrace models")
  }
  private def report(key: ModelKey, work: File): SpinalReport[Component] = {
    check(key)
    val roots = if (map.verilog.isEmpty) Seq(new File(sourceDir, "src/main/scala")).filter(_.isDirectory) else Nil
    RiscvSimConfig.elaborate(key, work, SpinalConfig(), sourceRoots = roots)(top())
  }
  /** One file for the C1 RTL identity: the generated wrapper, then (for a Verilog top) the
    * defines and each source file, in map order. `identity` and the compiled model use the same rule. */
  private def combined(dir: File, generated: Seq[File]): Seq[File] = {
    val own = generated.filter(f => f.getName.endsWith(".v") || f.getName.endsWith(".sv"))
      .filterNot(f => map.verilog.exists(_.files.exists(_.getName == f.getName))).sortBy(_.getName)
    map.verilog match {
      case None => own
      case Some(v) =>
        val out = new File(dir, "rvw-mapped-rtl.v")
        val text = new StringBuilder
        for (f <- own) text ++= new String(java.nio.file.Files.readAllBytes(f.toPath), "UTF-8")
        text ++= v.defines.toSeq.sorted.map { case (k, d) => s"// rvw define $k=$d\n" }.mkString
        for (f <- v.files) text ++= s"// rvw source ${f.getName}\n" ++= new String(java.nio.file.Files.readAllBytes(f.toPath), "UTF-8")
        dir.mkdirs()
        java.nio.file.Files.write(out.toPath, text.toString.getBytes("UTF-8"))
        Seq(out)
    }
  }
  override def elaborate(key: ModelKey, work: File): Seq[File] =
    combined(new File(work, key.name + "-identity"), report(key, work).generatedSourcesPaths.toSeq.map(new File(_)))
  def compile(key: ModelKey, work: File, cache: File): Model = {
    val cfg = RiscvSimConfig(key, work, cache, SpinalConfig())
    for (v <- map.verilog; (k, value) <- v.defines)
      cfg.addSimulatorFlag(if (value.isEmpty) s"+define+$k" else s"+define+$k=$value")
    cfg.compile(report(key, work))
  }
  override def generatedVerilog(model: Model): Seq[File] =
    combined(new File(model.compiledPath.toString), Option(new File(model.compiledPath, "rtl").listFiles()).toSeq.flatten)

  def run(model: Model, job: RunJob, ctx: RunContext): RunOutcome = {
    require(!job.rvfiCheck, "mapped adapter has no riscv-formal monitor; use --rvfi-trace")
    require(job.socMap.isEmpty, "mapped adapter does not support --soc-map")
    require(!job.rvfiTrace || map.rvfiPrefix.nonEmpty, "core map has no RVFI ports; --rvfi-trace is unavailable")
    require(ctx.elf.entry == map.resetPc, f"ELF entry must equal reset PC 0x${map.resetPc}%x")
    val tohost = new ToHost(ToHost.find(ctx.elf).getOrElse(
      throw new IllegalArgumentException("ELF has no tohost symbol")), busBytes)
    val memory = mutable.LongMap.empty[Int]
    def inRam(a: Long, n: Long): Boolean = a >= map.ramBase && n >= 0 && a + n <= map.ramBase + map.ramSize
    ctx.elf.load { (addr, bytes) =>
      require(inRam(addr, bytes.length), "ELF segment outside RAM")
      bytes.indices.foreach(i => memory(addr + i) = bytes(i) & 255)
    }
    def read(addr: Long, n: Int): BigInt = (0 until n).foldLeft(BigInt(0)) { (v, i) =>
      v | (BigInt(memory.getOrElse(addr + i, 0)) << (8 * i))
    }
    def write(addr: Long, n: Int, data: BigInt, mask: BigInt): Unit =
      for (i <- 0 until n if mask.testBit(i)) memory(addr + i) = ((data >> (8 * i)) & 255).toInt
    val writer = if (job.rvfiTrace) Some(new RvfiTraceWriter(new File(job.out, "rvfi.jsonl"), ctx.rvfiHeader)) else None
    var retired, traps = 0L
    val (status, code, message, cycles) = try {
      val result = SimSession.run(model, job, ctx) { (dut, ctl) =>
        val ports: Map[String, Data] = dut.getAllIo.map(d => d.getName() -> d).toMap
        def port(n: String): Data = ports.getOrElse(n, throw new IllegalArgumentException(
          s"core map names port '$n', but the top level has no such port"))
        def set(n: String, v: BigInt): Unit = port(n) match {
          case b: Bool => b #= v != 0
          case b: BitVector => b #= v
          case other => throw new IllegalArgumentException(s"port $n is not a Bool or bit vector")
        }
        def get(n: String): BigInt = port(n) match {
          case b: Bool => if (b.toBoolean) 1 else 0
          case b: BitVector => b.toBigInt
          case other => throw new IllegalArgumentException(s"port $n is not a Bool or bit vector")
        }
        for ((n, v) <- map.constants) set(n, v)
        for (n <- map.irq.values) set(n, 0)
        val random = new scala.util.Random(job.seed)
        def latency(): Long = job.memLatency.map(_.toLong).getOrElse(random.nextInt(4).toLong)
        def onStore(addr: BigInt, sizeLog2: Int, data: BigInt): Unit =
          tohost.onStore(addr, sizeLog2, data) match {
            case Some(ToHost.Pass) => ctl.finish(Status.Pass)
            case Some(f: ToHost.Fail) => ctl.finish(Status.Fail, Some(f.code), Some(s"tohost = ${Hex(f.raw)}"))
            case None =>
          }
        val models = map.buses.map { b =>
          val s = b.signals
          val bytes = widthOf(port(s("rdata"))) / 8
          for (k <- Seq("cmd_ready", "rsp_valid", "ready")) s.get(k).foreach(set(_, 0))
          def access(addrRaw: BigInt, isWrite: Boolean, data: => BigInt, mask: => BigInt): (BigInt, Boolean) = {
            val addr = addrRaw.toLong & ~(bytes - 1L)
            val ok = inRam(addr, bytes)
            if (isWrite) {
              if (ok) write(addr, bytes, data, mask)
              // Without RVFI the bus store is the completion evidence.
              if (map.rvfiPrefix.isEmpty && ok) {
                val lane = mask.lowestSetBit
                val count = mask.bitCount
                if (lane >= 0 && Set(1, 2, 4, 8)(count)) onStore(addr + lane, Integer.numberOfTrailingZeros(count), data >> (8 * lane))
              }
              (BigInt(0), !ok)
            } else (if (ok) read(addr, bytes) else BigInt(0), !ok)
          }
          b.protocol match {
            case "req-rsp" =>
              val queue = mutable.Queue.empty[(Long, BigInt, Boolean)]
              var driven = false
              s.get("cmd_ready").foreach(set(_, 1))
              (cycle: Long) => {
                val rspReady = s.get("rsp_ready").forall(get(_) != 0)
                if (driven && rspReady) { queue.dequeue(); driven = false }
                if (get(s("cmd_valid")) != 0 && s.get("cmd_ready").forall(get(_) != 0)) {
                  val isWrite = s.get("write").exists(get(_) != 0)
                  val (rdata, error) = access(get(s("address")), isWrite, get(s("wdata")),
                    s.get("mask").map(get).getOrElse((BigInt(1) << bytes) - 1))
                  if (!isWrite || b.writeResponse) queue.enqueue((cycle + latency(), rdata, error))
                }
                queue.headOption.filter(_._1 <= cycle) match {
                  case Some((_, d, e)) =>
                    driven = true; set(s("rsp_valid"), 1); set(s("rdata"), d); s.get("error").foreach(set(_, if (e) 1 else 0))
                  case None => if (!driven) set(s("rsp_valid"), 0)
                }
              }
            case "valid-ready" =>
              var due = -1L
              var answered = false
              (cycle: Long) => {
                if (answered) { set(s("ready"), 0); answered = false; due = -1 }
                else if (get(s("valid")) != 0) {
                  if (due < 0) due = cycle + latency()
                  if (cycle >= due) {
                    val mask = s.get("mask").map(get).getOrElse(BigInt(0))
                    val (rdata, _) = access(get(s("address")), mask != 0, get(s("wdata")), mask)
                    set(s("rdata"), rdata); set(s("ready"), 1); answered = true
                  }
                }
              }
          }
        }
        val rvfi = map.rvfiPrefix.map(prefix => new MappedRvfi(prefix, n => ports.get(prefix + n)))
        val cd = dut.clockDomain
        cd.forkStimulus(10)
        // forkStimulus holds reset while the clock is stopped. A synchronous reset needs edges:
        // assert it again for 16 clocked cycles.
        fork { cd.waitSampling(); cd.assertReset(); cd.waitRisingEdge(16); cd.deassertReset() }
        var irqLevels = BigInt(-1)
        cd.onSamplings {
          ctl.tick()
          val cycle = ctl.cycle
          val levels = job.irqSchedule.map(_.levelsAt(cycle)).getOrElse(BigInt(0))
          for ((bit, n) <- map.irq) set(n, if (levels.testBit(bit)) 1 else 0)
          if (writer.nonEmpty && levels != irqLevels) { writer.foreach(_.irq(cycle, levels)); irqLevels = levels }
          // RVFI outputs are not defined while reset is asserted.
          for (r <- rvfi.toSeq.filter(_ => !cd.isResetAsserted).flatMap(_.sample(cycle))) {
            retired += 1
            if (r.trap) traps += 1
            writer.foreach(_.write(r))
            if (r.memWmask != 0 && !r.trap) {
              val lane = Integer.numberOfTrailingZeros(r.memWmask)
              val count = Integer.bitCount(r.memWmask)
              require(Set(1, 2, 4, 8)(count), "unsupported RVFI store mask")
              onStore(r.memAddr + lane, Integer.numberOfTrailingZeros(count), r.memWdata >> (8 * lane))
            }
          }
          models.foreach(_(cycle))
        }
        cd.waitSamplingWhere(false)
      }
      writer.foreach(_.end(result._4, result._1.name))
      result
    } finally writer.foreach(_.close())
    RunOutcome(status, cycles, retired, code, message,
      ujson.Obj("traps" -> RvwJson.num(traps), "rvfi_records" -> RvwJson.num(retired), "tohost" -> Hex(tohost.value),
        "rvfi_monitor" -> false, "memory_bytes" -> RvwJson.num(map.ramSize), "core_map" -> map.file.getPath))
  }
}

/** Launcher entry: `RVW_CORE_MAP` names the project's `rvw.core-map/1` file. */
object MappedMain {
  def main(args: Array[String]): Unit = {
    val file = new File(sys.env.getOrElse("RVW_CORE_MAP", throw new IllegalArgumentException("Set RVW_CORE_MAP")))
    new Driver(new MappedAdapter(CoreMap.load(file))).main(args)
  }
}
