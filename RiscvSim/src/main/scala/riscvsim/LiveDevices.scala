package riscvsim

import scala.collection.mutable

/** Deterministic MMIO devices. Maps, input bytes and pin routing are project data.
  * One instance belongs to one run. No host I/O or wall clock is used. */
final class LiveDevices(map: SimMap) {
  private val config = ujson.read(map.bytes).obj.get("devices").map(_.arr.toSeq).getOrElse(Seq.empty)
  val interruptMask: BigInt = config.foldLeft(BigInt(0)) { (mask, c) =>
    val fields = c("model").str match {
      case "clint" => Seq("software_bit", "timer_bit")
      case "plic" => Seq("interrupt_bit")
      case _ => Seq.empty
    }
    fields.foldLeft(mask) { (bits, field) =>
      val bit = SimMap.number(c(field))
      require(bit >= 0 && bit < 64, "invalid device interrupt bit")
      bits | (BigInt(1) << bit.toInt)
    }
  }
  private trait Device {
    def save: ujson.Value
    def restore(v: ujson.Value): Unit
    def read(offset: Long): Long
    def write(offset: Long, value: Long): Unit
    def tick(cycle: Long): Unit = ()
    def irq: Boolean = false
    def output: String = ""
  }
  private class Uart(c: ujson.Value) extends Device {
    val rx = mutable.Queue.empty[Int]
    val tx = new StringBuilder
    val input = c.obj.get("rx").map(_.arr.toSeq).getOrElse(Seq.empty)
    require(input.map(e => SimMap.number(e("cycle"))).sliding(2).forall(p => p.size < 2 || p.head <= p.last), "unordered UART input")
    var position = 0
    var ier, divisorLow, divisorHigh, lcr, scratch, mcr = 0L
    var fifo = false
    var overrun = false
    override def tick(cycle: Long): Unit = {
      while (position < input.size && SimMap.number(input(position)("cycle")) <= cycle) {
        val raw = SimMap.number(input(position)("byte"))
        require(raw >= 0 && raw <= 255, "invalid UART byte")
        val b = raw.toInt
        if (rx.size < (if (fifo) 16 else 1)) rx.enqueue(b) else overrun = true
        position += 1
      }
    }
    def save: ujson.Value = ujson.Obj("rx" -> ujson.Arr.from(rx), "tx" -> tx.toString,
      "position" -> position, "ier" -> ier, "dl" -> divisorLow, "dh" -> divisorHigh,
      "lcr" -> lcr, "scratch" -> scratch, "mcr" -> mcr, "fifo" -> fifo, "overrun" -> overrun)
    def restore(v: ujson.Value): Unit = {
      rx.clear(); v("rx").arr.foreach(b => rx.enqueue(b.num.toInt))
      tx.clear(); tx.append(v("tx").str); position = v("position").num.toInt
      ier = SimMap.number(v("ier")).toLong; divisorLow = SimMap.number(v("dl")).toLong; divisorHigh = SimMap.number(v("dh")).toLong
      mcr = v.obj.get("mcr").map(SimMap.number).getOrElse(BigInt(0)).toLong
      lcr = SimMap.number(v("lcr")).toLong; scratch = SimMap.number(v("scratch")).toLong
      fifo = v("fifo").bool; overrun = v("overrun").bool
    }
    override def irq = (ier & 1) != 0 && rx.nonEmpty || (ier & 2) != 0
    override def output = tx.toString
    def read(o: Long): Long = o match {
      case 0 if (lcr & 128) != 0 => divisorLow
      case 1 if (lcr & 128) != 0 => divisorHigh
      case 0 => if (rx.nonEmpty) rx.dequeue().toLong else 0L
      case 1 => ier
      case 2 => (if (fifo) 0xc0 else 0) | (if ((ier & 1) != 0 && rx.nonEmpty) 4 else if ((ier & 2) != 0) 2 else 1)
      case 3 => lcr
      case 4 => mcr
      case 5 => val v = 0x60L | (if (rx.nonEmpty) 1 else 0) | (if (overrun) 2 else 0); overrun = false; v
      case 7 => scratch
      case _ => throw new IllegalArgumentException(s"unsupported UART read $o")
    }
    def write(o: Long, v: Long): Unit = o match {
      case 0 if (lcr & 128) != 0 => divisorLow = v & 255
      case 1 if (lcr & 128) != 0 => divisorHigh = v & 255
      case 0 => tx.append((v & 255).toChar)
      case 1 => require((v & ~3L) == 0, "unsupported UART interrupt enable"); ier = v
      case 2 => require((v & ~7L) == 0, "unsupported UART FIFO control"); fifo = (v & 1) != 0; if ((v & 2) != 0) rx.clear()
      case 3 => lcr = v & 255
      case 4 => require((v & ~15L) == 0, "unsupported UART modem control"); mcr = v
      case 7 => scratch = v & 255
      case _ => throw new IllegalArgumentException(s"unsupported UART write $o")
    }
  }
  private class Clint(c: ujson.Value) extends Device {
    val period = SimMap.number(c("cycles_per_tick")).toLong
    require(period > 0, "invalid timer period")
    var time = BigInt(0)
    var compare = (BigInt(1) << 64) - 1
    var software = 0L
    def save: ujson.Value = ujson.Obj("time" -> time.toString, "compare" -> compare.toString, "software" -> software)
    def restore(v: ujson.Value): Unit = {
      time = BigInt(v("time").str); compare = BigInt(v("compare").str); software = SimMap.number(v("software")).toLong
    }
    override def tick(cycle: Long): Unit = { time = BigInt(cycle / period) }
    def levels: BigInt = (if (software != 0) BigInt(1) << SimMap.number(c("software_bit")).toInt else BigInt(0)) |
      (if (time >= compare) BigInt(1) << SimMap.number(c("timer_bit")).toInt else BigInt(0))
    def read(o: Long): Long = o match {
      case 0 => software
      case 0x4000 => (compare & 0xffffffffL).toLong
      case 0x4004 => (compare >> 32).toLong
      case 0xbff8 => (time & 0xffffffffL).toLong
      case 0xbffc => (time >> 32).toLong
      case _ => throw new IllegalArgumentException(s"unsupported CLINT read $o")
    }
    def write(o: Long, v: Long): Unit = o match {
      case 0 => software = v & 1
      case 0x4000 => compare = (compare & (BigInt(0xffffffffL) << 32)) | BigInt(v & 0xffffffffL)
      case 0x4004 => compare = (compare & 0xffffffffL) | (BigInt(v & 0xffffffffL) << 32)
      case 0xbff8 => throw new IllegalArgumentException("mtime writes unsupported")
      case _ => throw new IllegalArgumentException(s"unsupported CLINT write $o")
    }
  }
  private class Plic(c: ujson.Value) extends Device {
    val priority = mutable.Map.empty[Int, Long].withDefaultValue(0L)
    val claimed = mutable.Set.empty[Int]
    var enable, threshold = 0L
    var active = Set.empty[Int]
    def save: ujson.Value = ujson.Obj("priority" -> ujson.Obj.from(priority.toSeq.map { case (k, v) => k.toString -> ujson.Num(v) }),
      "claimed" -> ujson.Arr.from(claimed.toSeq.sorted), "enable" -> enable, "threshold" -> threshold,
      "active" -> ujson.Arr.from(active.toSeq.sorted))
    def restore(v: ujson.Value): Unit = {
      priority.clear(); v("priority").obj.foreach { case (k, value) => priority(k.toInt) = SimMap.number(value).toLong }
      claimed.clear(); v("claimed").arr.foreach(n => claimed += n.num.toInt)
      enable = SimMap.number(v("enable")).toLong; threshold = SimMap.number(v("threshold")).toLong
      active = v("active").arr.map(_.num.toInt).toSet
    }
    def winner: Int = active.filter(s => !claimed(s) && (enable & (1L << s)) != 0 && priority(s) > threshold)
      .toSeq.sortBy(s => (-priority(s), s)).headOption.getOrElse(0)
    override def irq = winner != 0
    def read(o: Long): Long = o match {
      case 0x1000 => active.filterNot(claimed).foldLeft(0L)((v, s) => v | (1L << s))
      case 0x2000 => enable
      case 0x200000 => threshold
      case 0x200004 => val w = winner; if (w != 0) claimed += w; w.toLong
      case n if n >= 4 && n < 128 && n % 4 == 0 => priority((n / 4).toInt)
      case _ => throw new IllegalArgumentException(s"unsupported PLIC read $o")
    }
    def write(o: Long, v: Long): Unit = o match {
      case 0x2000 => enable = v & 0xfffffffeL
      case 0x200000 => threshold = v
      case 0x200004 => require(claimed(v.toInt), "completion without claim"); claimed -= v.toInt
      case n if n >= 4 && n < 128 && n % 4 == 0 => priority((n / 4).toInt) = v
      case _ => throw new IllegalArgumentException(s"unsupported PLIC write $o")
    }
  }
  private val entries = config.map { c =>
    val name = c("region").str
    val r = map.regions.find(_.name == name).getOrElse(throw new IllegalArgumentException(s"unknown device region $name"))
    require(r.kind == "mmio" && !r.cacheable, "device requires uncached MMIO")
    val d: Device = c("model").str match {
      case "ns16550" => new Uart(c)
      case "clint" => new Clint(c)
      case "plic" => new Plic(c)
      case m => throw new IllegalArgumentException(s"unsupported device $m")
    }
    (r, c, d)
  }
  require(entries.map(_._1.name).distinct.size == entries.size, "duplicate device region")
  require(map.regions.filter(_.kind == "mmio").forall(r => entries.exists(_._1 == r)), "MMIO region without model")
  private val byName = entries.map { case (r, _, d) => r.name -> d }.toMap
  entries.foreach { case (_, c, d) => d match {
    case _: Plic => c("sources").arr.foreach { s =>
      require(byName.contains(s("device").str), "unknown PLIC source")
      require(SimMap.number(s("id")) > 0 && SimMap.number(s("id")) < 32, "PLIC source outside 1..31")
    }
    case _ =>
  }}
  private def selected(address: Long, bytes: Int, permission: Char) =
    entries.find { case (r, _, _) => r.contains(BigInt(address), bytes) && r.permissions.contains(permission) }
      .getOrElse(throw new IllegalArgumentException(f"unmapped device address 0x$address%x"))
  def contains(address: Long, bytes: Int): Boolean = entries.exists(_._1.contains(BigInt(address), bytes))
  def read(address: Long, bytes: Int): BigInt = {
    val (r, _, d) = selected(address, bytes, 'r')
    val offset = (BigInt(address) - r.base).toLong
    if (bytes == 8 && d.isInstanceOf[Clint] && Set(0x4000L, 0xbff8L)(offset))
      (BigInt(d.read(offset)) & 0xffffffffL) | ((BigInt(d.read(offset + 4)) & 0xffffffffL) << 32)
    else {
      require(bytes == (if (d.isInstanceOf[Uart]) 1 else 4), "unsupported device read width")
      BigInt(d.read(offset))
    }
  }
  def write(address: Long, bytes: Int, value: BigInt): Unit = {
    val (r, _, d) = selected(address, bytes, 'w')
    val offset = (BigInt(address) - r.base).toLong
    if (bytes == 8 && d.isInstanceOf[Clint] && Set(0x4000L, 0xbff8L)(offset)) {
      d.write(offset, (value & 0xffffffffL).toLong)
      d.write(offset + 4, ((value >> 32) & 0xffffffffL).toLong)
    } else {
      require(bytes == (if (d.isInstanceOf[Uart]) 1 else 4), "unsupported device write width")
      d.write(offset, value.toLong)
    }
  }
  def tick(cycle: Long): BigInt = {
    entries.foreach(_._3.tick(cycle))
    entries.foreach { case (_, c, d) => d match {
      case p: Plic => p.active = c("sources").arr.filter(s => byName(s("device").str).irq).map(s => SimMap.number(s("id")).toInt).toSet
      case _ =>
    }}
    entries.foldLeft(BigInt(0)) { case (levels, (_, c, d)) => levels | (d match {
      case t: Clint => t.levels
      case p: Plic if p.irq => BigInt(1) << SimMap.number(c("interrupt_bit")).toInt
      case _ => BigInt(0)
    }) }
  }
  def snapshot(): ujson.Value = ujson.Obj("schema" -> "rvw.live-devices/1", "map_sha256" -> map.sha256,
    "state" -> ujson.Obj.from(entries.map { case (r, _, d) => r.name -> d.save }))
  /** Trusted same-build state. Discard the instance if restore fails. */
  def restore(v: ujson.Value): Unit = {
    require(v("schema").str == "rvw.live-devices/1" && v("map_sha256").str == map.sha256, "device snapshot identity mismatch")
    require(v("state").obj.keySet == byName.keySet, "device snapshot inventory mismatch")
    entries.foreach { case (r, _, d) => d.restore(v("state")(r.name)) }
  }
  private val resetState = snapshot()
  /** Reset the complete device set for a new run whose cycle origin is zero. */
  def reset(): Unit = restore(resetState)

  def outputs: ujson.Value = ujson.Obj.from(entries.collect { case (r, _, u: Uart) => r.name -> ujson.Str(u.output) })
}
