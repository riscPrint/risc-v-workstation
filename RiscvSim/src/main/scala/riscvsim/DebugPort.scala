package riscvsim

import java.io.{BufferedReader, File, InputStreamReader}
import java.net.{InetAddress, ServerSocket}
import java.util.concurrent.LinkedBlockingQueue

import spinal.core._
import spinal.core.sim._

/** Top-level port names of a core's debug transport, from project data (`rvw.debug-binding/1`). */
case class DmiPins(cmdValid: String, cmdReady: Option[String], cmdWrite: String, cmdAddress: String,
                   cmdData: String, rspValid: String, rspError: Option[String], rspData: String, abits: Int,
                   timeoutCycles: Int)
case class JtagPins(tck: String, tms: String, tdi: String, tdo: String, trst: Option[String], cyclesPerByte: Int,
                    idleTimeoutS: Int)
case class DebugBinding(file: File, dmi: Option[DmiPins], jtag: Option[JtagPins])

object DebugBinding {
  val schema = "rvw.debug-binding/1"

  def load(file: File): DebugBinding = {
    val doc = ujson.read(java.nio.file.Files.readString(file.toPath)).obj
    if (!doc.get("schema").exists(_.str == schema)) throw new Cli.UsageError(s"--debug-binding: schema must be $schema")
    def opt(o: collection.Map[String, ujson.Value], k: String) = o.get(k).filterNot(_.isNull).map(_.str)
    val dmi = doc.get("dmi").filterNot(_.isNull).map(_.obj).map(o => DmiPins(o("cmd_valid").str, opt(o, "cmd_ready"),
      o("cmd_write").str, o("cmd_address").str, o("cmd_data").str, o("rsp_valid").str, opt(o, "rsp_error"),
      o("rsp_data").str, o.get("abits").map(_.num.toInt).getOrElse(7),
      o.get("timeout_cycles").map(_.num.toInt).getOrElse(10000)))
    val jtag = doc.get("jtag").filterNot(_.isNull).map(_.obj).map(o => JtagPins(o("tck").str, o("tms").str,
      o("tdi").str, o("tdo").str, opt(o, "trst"), o.get("cycles_per_byte").map(_.num.toInt).getOrElse(1),
      o.get("idle_timeout_s").map(_.num.toInt).getOrElse(300)))
    if (dmi.isEmpty && jtag.isEmpty) throw new Cli.UsageError("--debug-binding: declare dmi or jtag")
    DebugBinding(file, dmi, jtag)
  }
}

/** `--debug dmi` (C1 line protocol on stdin/stdout) or `--debug jtag:PORT` (remote_bitbang). */
case class DebugMode(text: String, binding: DebugBinding) {
  val dmi: Boolean = text == "dmi"
  val port: Option[Int] = if (text.startsWith("jtag:")) Some(text.drop(5).toInt) else None
  require(dmi || port.exists(p => p >= 0 && p < 65536), "--debug must be dmi or jtag:PORT")
  require(!dmi || binding.dmi.nonEmpty, "--debug dmi needs a dmi binding")
  require(port.isEmpty || binding.jtag.nonEmpty, "--debug jtag needs a jtag binding")
}

/**
 * Serves a core's simulated debug transport while the adapter's run loop runs the core.
 * Simulation time advances only inside requests (DMI operations, `t`, JTAG pin writes), so a
 * session is deterministic. The session ends the run with status `timeout` and message
 * "debug session ended" when the client quits; that status is never a pass.
 */
class DebugPort(mode: DebugMode, ctx: RunContext) {
  @volatile var requests = 0L
  @volatile var clients = 0L
  @volatile var ended: Option[String] = None
  var listenPort: Option[Int] = None

  private def io(dut: Component, name: String): BaseType =
    dut.getAllIo.find(_.getName() == name).getOrElse(throw new IllegalArgumentException(s"debug binding: no top-level port '$name'"))

  private def set(bt: BaseType, v: BigInt): Unit = setBigInt(bt, v)

  def attach(dut: Component, ctl: SimControl): Unit = {
    val cd = dut.clockDomain
    mode.binding.dmi.filter(_ => mode.dmi).foreach(p => serveDmi(dut, cd, ctl, p))
    for (port <- mode.port; p <- mode.binding.jtag) serveJtag(dut, cd, ctl, p, port)
  }

  private def finish(ctl: SimControl, why: String): Unit = {
    ended = Some(why)
    ctl.finish(Status.Timeout, message = Some(s"debug session ended: $why"))
  }

  private def serveDmi(dut: Component, cd: ClockDomain, ctl: SimControl, p: DmiPins): Unit = {
    val valid = io(dut, p.cmdValid); val write = io(dut, p.cmdWrite)
    val address = io(dut, p.cmdAddress); val data = io(dut, p.cmdData)
    val ready = p.cmdReady.map(io(dut, _)); val rspValid = io(dut, p.rspValid)
    val rspError = p.rspError.map(io(dut, _)); val rspData = io(dut, p.rspData)
    set(valid, 0); set(write, 0); set(address, 0); set(data, 0)
    val lines = new LinkedBlockingQueue[Option[String]]()
    val reader = new Thread(() => {
      val in = new BufferedReader(new InputStreamReader(System.in))
      var line = in.readLine()
      while (line != null) { lines.put(Some(line.trim)); line = in.readLine() }
      lines.put(None)
    }, "riscvsim-dmi-stdin")
    reader.setDaemon(true)
    reader.start()
    def reply(text: String): Unit = NativeOutput.writeStdout(text + "\n")
    def response(): Option[(Boolean, BigInt)] = {
      sleep(1)
      if (FaultInjector.raw(rspValid) == 1) Some((rspError.exists(FaultInjector.raw(_) == 1), FaultInjector.raw(rspData)))
      else None
    }
    def transfer(isWrite: Boolean, a: BigInt, d: BigInt): String = {
      cd.waitFallingEdge()
      set(valid, 1); set(write, if (isWrite) 1 else 0); set(address, a); set(data, d)
      var waited = 0
      var accepted = false
      var rsp: Option[(Boolean, BigInt)] = None
      while (!accepted && waited < p.timeoutCycles) {
        sleep(1)
        accepted = ready.forall(FaultInjector.raw(_) == 1)
        if (accepted) rsp = response()
        cd.waitFallingEdge(); waited += 1
      }
      set(valid, 0)
      if (!accepted) return "busy"
      while (rsp.isEmpty && waited < p.timeoutCycles) {
        rsp = response()
        if (rsp.isEmpty) { cd.waitFallingEdge(); waited += 1 }
      }
      rsp match {
        case Some((false, v)) => "ok " + Hex(v & 0xffffffffL)
        case _ => "fail"
      }
    }
    fork {
      cd.waitSampling()
      reply(s"ready ${p.abits}")
      ctx.log(s"debug: DMI line protocol ready (abits ${p.abits})")
      var open = true
      while (open) {
        lines.take() match {
          case None => open = false; finish(ctl, "stdin closed")
          case Some("q") => open = false; finish(ctl, "client quit")
          case Some(line) =>
            requests += 1
            line.split("\\s+").toSeq match {
              case Seq("r", a) => reply(transfer(isWrite = false, Hex.parse(a), 0))
              case Seq("w", a, d) => reply(transfer(isWrite = true, Hex.parse(a), Hex.parse(d)))
              case Seq("t", n) => cd.waitSampling(Hex.parse(n).toInt max 1); reply("ok 0x0")
              case _ => ctx.log(s"debug: bad request '$line'"); reply("fail")
            }
        }
      }
    }
  }

  private def serveJtag(dut: Component, cd: ClockDomain, ctl: SimControl, p: JtagPins, port: Int): Unit = {
    val tck = io(dut, p.tck); val tms = io(dut, p.tms); val tdi = io(dut, p.tdi); val tdo = io(dut, p.tdo)
    val trst = p.trst.map(io(dut, _))
    set(tck, 0); set(tms, 1); set(tdi, 0); trst.foreach(set(_, 0))
    val server = new ServerSocket(port, 1, InetAddress.getLoopbackAddress)
    listenPort = Some(server.getLocalPort)
    val portFile = new File(ctx.job.out, "debug-port")
    java.nio.file.Files.writeString(portFile.toPath, server.getLocalPort.toString + "\n")
    ctx.log(s"debug: remote_bitbang listening on 127.0.0.1:${server.getLocalPort}")
    fork {
      cd.waitSampling()
      server.setSoTimeout(p.idleTimeoutS * 1000)
      val buffer = new Array[Byte](4096)
      var serving = true
      while (serving) {
        // One client at a time. 'Q' or a closed connection ends that client; the session
        // ends when no client connects within the idle timeout.
        val socket = try Some(server.accept()) catch { case _: java.net.SocketTimeoutException => None }
        socket match {
          case None =>
            serving = false; server.close(); finish(ctl, s"no JTAG client for ${p.idleTimeoutS} s")
          case Some(s) =>
            clients += 1
            s.setTcpNoDelay(true)
            val in = s.getInputStream
            val out = s.getOutputStream
            var open = true
            while (open) {
              out.flush()
              val n = in.read(buffer)
              if (n < 0) open = false
              var i = 0
              while (open && i < n) {
                val b = buffer(i).toChar
                i += 1
                b match {
                  case c if c >= '0' && c <= '7' =>
                    val v = c - '0'
                    set(tck, (v >> 2) & 1); set(tms, (v >> 1) & 1); set(tdi, v & 1)
                    requests += 1
                    cd.waitSampling(p.cyclesPerByte)
                  case 'R' => sleep(1); out.write(if (FaultInjector.raw(tdo) == 1) '1' else '0')
                  case c if c >= 'r' && c <= 'u' =>
                    trst.foreach(set(_, if (c == 't' || c == 'u') 1 else 0)) // r..u: trst (bit 1), srst (bit 0); 1 asserts
                    cd.waitSampling(p.cyclesPerByte)
                  case 'Q' => open = false
                  case _ =>
                }
              }
            }
            s.close()
        }
      }
    }
  }

  def details: ujson.Obj = ujson.Obj("mode" -> mode.text, "binding" -> mode.binding.file.getPath,
    "requests" -> RvwJson.num(requests), "clients" -> RvwJson.num(clients), "ended" -> ended.map(ujson.Str).getOrElse(ujson.Null),
    "port" -> listenPort.map(p => ujson.Num(p)).getOrElse(ujson.Null))
}

object DebugPort {
  private val active = new java.util.concurrent.ConcurrentHashMap[String, DebugPort]()
  def forRun(job: RunJob, ctx: RunContext): Option[DebugPort] =
    job.debug.map(m => active.computeIfAbsent(job.out.getAbsolutePath, _ => new DebugPort(m, ctx)))
  def finish(job: RunJob): Option[DebugPort] = job.debug.flatMap(_ => Option(active.remove(job.out.getAbsolutePath)))
}
