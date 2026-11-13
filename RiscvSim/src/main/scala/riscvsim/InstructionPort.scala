package riscvsim

import java.io.{File, PrintWriter}
import java.nio.file.Files
import java.security.MessageDigest
import spinal.core._
import spinal.core.sim._

/** A source supplies bus words. None applies request backpressure. */
trait InstructionSource {
  def response(address: BigInt): Option[(BigInt, Boolean)]
  def accepted(address: BigInt): Unit = ()
}

case class InstructionBinding(file: File, text: String, config: String, wordBytes: Int,
                              signals: Map[String, String], latency: Int)
case class InstructionFeed(file: File, text: String, wordBytes: Int, referenceElf: String,
                           words: Map[BigInt, (BigInt, Boolean)]) extends InstructionSource {
  // Missing addresses return a fetch fault. Never substitute instructions from RAM.
  def response(address: BigInt): Option[(BigInt, Boolean)] = Some(words.getOrElse(address, (BigInt(0), true)))
}
case class InstructionMode(binding: InstructionBinding, feed: InstructionFeed)

object InstructionMode {
  def sha(text: String): String = MessageDigest.getInstance("SHA-256").digest(text.getBytes("UTF-8"))
    .map(b => f"${b & 0xff}%02x").mkString
  def number(v: ujson.Value): BigInt = v match {
    case ujson.Str(s) if s.startsWith("0x") => BigInt(s.drop(2), 16)
    case ujson.Str(s) => BigInt(s)
    case ujson.Num(n) if n.isWhole && math.abs(n) <= 9007199254740991d => BigInt(n.toLong)
    case _ => throw new IllegalArgumentException("instruction feed requires exact integer values")
  }
  def load(port: File, instructions: File, config: String): InstructionMode = {
    val pt = Files.readString(port.toPath); val ft = Files.readString(instructions.toPath)
    val p = ujson.read(pt); val f = ujson.read(ft)
    require(p("schema").str == "rvw.instruction-port/1", "expected rvw.instruction-port/1")
    require(f("schema").str == "rvw.instruction-feed/1", "expected rvw.instruction-feed/1")
    require(p("config").str == config, "instruction port config differs from the selected config")
    val bytes = p("word_bytes").num.toInt
    require(p("word_bytes").num == bytes && Set(4, 8)(bytes) && f("word_bytes").num == bytes, "instruction port/feed word widths differ")
    val signals = p("signals").obj.map { case (k, v) => k -> v.str }.toMap
    val required = Set("cmd_valid", "cmd_ready", "address", "rsp_valid", "rdata")
    val optional = Set("rsp_ready", "error", "cmd_id", "rsp_id")
    require(required.subsetOf(signals.keySet) && (signals.keySet -- required -- optional).isEmpty,
      "instruction port needs a split request/response binding")
    require(signals.contains("cmd_id") == signals.contains("rsp_id"), "instruction IDs need both command and response bindings")
    require(signals.values.toSet.size == signals.size, "instruction port pins must be distinct")
    val latency = p.obj.get("latency_cycles").map(_.num.toInt).getOrElse(1)
    require(p.obj.get("latency_cycles").forall(_.num == latency) && latency >= 1 && latency <= 10000, "instruction latency must be 1..10000 cycles")
    val rows = f("words").arr.toSeq.map { row =>
      val address = number(row("address")); val data = number(row("data"))
      require(address >= 0 && address % bytes == 0 && data >= 0 && data < (BigInt(1) << (bytes * 8)),
        "instruction word exceeds its address or data domain")
      address -> (data, row.obj.get("error").exists(_.bool))
    }
    require(rows.nonEmpty && rows.map(_._1).distinct.size == rows.size, "instruction feed needs unique words")
    val reference = f("reference_elf_sha256").str
    require(reference.matches("[0-9a-f]{64}"), "instruction feed needs the reference ELF hash")
    InstructionMode(InstructionBinding(port, pt, config, bytes, signals, latency),
      InstructionFeed(instructions, ft, bytes, reference, rows.toMap))
  }
}

/** One outstanding split fetch request. The project binds the actual core pins. */
class InstructionPort(binding: InstructionBinding, source: InstructionSource, out: File) {
  var attached = false
  var requests = 0L
  var responses = 0L
  var faults = 0L
  private val writer = new PrintWriter(new File(out, "instruction-requests.jsonl"))

  def attach(dut: Component, ctl: SimControl): Unit = {
    def pin(key: String, input: Boolean, width: Option[Int] = None): BaseType = {
      val name = binding.signals(key)
      val bt = dut.getAllIo.find(_.getName() == name).getOrElse(
        throw new IllegalArgumentException(s"instruction binding: no top-level port '$name'"))
      require(if (input) bt.isInput else bt.isOutput, s"instruction binding: wrong direction for '$name'")
      require(width.forall(_ == bt.getBitsWidth), s"instruction binding: wrong width for '$name'")
      bt
    }
    val valid = pin("cmd_valid", false, Some(1)); val address = pin("address", false)
    val ready = binding.signals.get("cmd_ready").map(_ => pin("cmd_ready", true, Some(1)))
    val rspValid = pin("rsp_valid", true, Some(1)); val data = pin("rdata", true, Some(binding.wordBytes * 8))
    val rspReady = binding.signals.get("rsp_ready").map(_ => pin("rsp_ready", false, Some(1)))
    val error = binding.signals.get("error").map(_ => pin("error", true, Some(1)))
    val cmdId = binding.signals.get("cmd_id").map(_ => pin("cmd_id", false))
    val rspId = binding.signals.get("rsp_id").map(_ => pin("rsp_id", true))
    require(cmdId.isEmpty || cmdId.get.getBitsWidth == rspId.get.getBitsWidth, "instruction ID widths differ")
    require(ready.nonEmpty, "instruction injection requires command backpressure")
    def set(bt: BaseType, value: BigInt): Unit = setBigInt(bt, value)
    ready.foreach(set(_, 0)); set(rspValid, 0); set(data, 0); error.foreach(set(_, 0)); rspId.foreach(set(_, 0))
    attached = true
    fork {
      val cd = dut.clockDomain
      var cycle = 0L
      var pending = Option.empty[(Long, BigInt, BigInt, Boolean, BigInt)]
      while (true) {
        cd.waitFallingEdge()
        val reset = cd.isResetAsserted
        if (reset) pending = None
        val pc = FaultInjector.raw(address) & ~(BigInt(binding.wordBytes) - 1)
        val offered = if (!reset && pending.isEmpty) source.response(pc) else None
        ready.foreach(set(_, if (offered.nonEmpty) 1 else 0))
        val responding = !reset && pending.exists(_._1 <= cycle)
        set(rspValid, if (responding) 1 else 0)
        pending.foreach { case (_, _, word, fault, id) =>
          require(!fault || error.nonEmpty, "instruction port cannot represent a fetch fault")
          set(data, word); error.foreach(set(_, if (fault) 1 else 0)); rspId.foreach(set(_, id))
        }
        cd.waitSampling()
        cycle += 1
        if (responding && rspReady.forall(FaultInjector.raw(_) == 1)) {
          val (_, acceptedPc, word, fault, id) = pending.get
          responses += 1; if (fault) faults += 1
          writer.println(ujson.write(ujson.Obj("cycle" -> RvwJson.num(ctl.cycle), "address" -> Hex(acceptedPc),
            "data" -> Hex(word), "error" -> fault, "id" -> Hex(id))))
          pending = None
        }
        if (!reset && offered.nonEmpty && FaultInjector.raw(valid) == 1 && ready.forall(FaultInjector.raw(_) == 1)) {
          val acceptedPc = FaultInjector.raw(address) & ~(BigInt(binding.wordBytes) - 1)
          val (word, fault) = source.response(acceptedPc).getOrElse(
            throw new IllegalStateException("instruction source withdrew an accepted word"))
          source.accepted(acceptedPc)
          requests += 1
          pending = Some((cycle + binding.latency - 1, acceptedPc, word, fault, cmdId.map(FaultInjector.raw).getOrElse(BigInt(0))))
        }
      }
    }
  }
  def close(): Unit = writer.close()
}

object InstructionPort {
  private val active = new java.util.concurrent.ConcurrentHashMap[String, InstructionPort]()
  def forRun(job: RunJob): Option[InstructionPort] = job.instructionPort.map { mode =>
    active.computeIfAbsent(job.out.getAbsolutePath, _ => {
      val elfHash = MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(job.elf.toPath))
        .map(b => f"${b & 0xff}%02x").mkString
      require(elfHash == mode.feed.referenceElf, "instruction feed reference ELF differs from the job")
      Files.writeString(new File(job.out, "instruction-port.json").toPath, mode.binding.text)
      Files.writeString(new File(job.out, "instruction-feed.json").toPath, mode.feed.text)
      new InstructionPort(mode.binding, mode.feed, job.out)
    })
  }
  def finish(job: RunJob): Option[ujson.Obj] = job.instructionPort.map { mode =>
    val port = Option(active.remove(job.out.getAbsolutePath)); port.foreach(_.close())
    ujson.Obj("attached" -> port.exists(_.attached), "requests" -> RvwJson.num(port.map(_.requests).getOrElse(0L)),
      "responses" -> RvwJson.num(port.map(_.responses).getOrElse(0L)), "faults" -> RvwJson.num(port.map(_.faults).getOrElse(0L)),
      "binding_sha256" -> InstructionMode.sha(mode.binding.text), "feed_sha256" -> InstructionMode.sha(mode.feed.text),
      "reference_elf_sha256" -> mode.feed.referenceElf, "instruction_source" -> "bound fetch port")
  }
}
