package riscvsim

import java.util.concurrent.CopyOnWriteArrayList

import com.sun.jna.{Library, Native, NativeLong}

/**
 * Captures the process's stdout and stderr at the file-descriptor level, so text printed by
 * native code (a Verilator model's `$display`, e.g. an HDL assertion message) can be read
 * back by the JVM. Each fd is redirected into a pipe; a reader thread copies everything to
 * the original fd (so the console output is unchanged), keeps the recent lines, and hands
 * each line to the current subscribers (per-run logs).
 *
 * Lines are not tied to the thread that printed them: with several simulations running in
 * one process, a subscriber also sees the other simulations' lines.
 */
object NativeOutput {
  private trait LibC extends Library {
    def pipe(fds: Array[Int]): Int
    def dup(fd: Int): Int
    def dup2(from: Int, to: Int): Int
    def read(fd: Int, buf: Array[Byte], n: NativeLong): NativeLong
    def write(fd: Int, buf: Array[Byte], n: NativeLong): NativeLong
  }

  /** A captured line; `seq` increases across both streams. */
  case class Line(seq: Long, stream: Int, text: String, nanos: Long)

  private val subscribers = new CopyOnWriteArrayList[Line => Unit]()
  private val recent = new java.util.ArrayDeque[Line]()
  private val maxRecent = 4096
  private var seqCounter = 0L
  @volatile private var started = false
  @volatile var available = false

  private var libc: LibC = null
  private var origOut = 1

  /**
   * Starts capturing (idempotent). Returns false if the platform has no usable libc.
   * With `stdoutToStderr`, everything printed on stdout is shown on stderr instead, so the
   * real stdout carries only what `writeStdout` writes (e.g. a JSON result).
   */
  def start(stdoutToStderr: Boolean = false): Boolean = synchronized {
    if (started) return available
    started = true
    try {
      libc = Native.load("c", classOf[LibC])
      System.out.flush(); System.err.flush()
      origOut = libc.dup(1)
      val origErr = libc.dup(2)
      require(origOut >= 0 && origErr >= 0, "dup failed")
      for (fd <- Seq(1, 2)) {
        val fds = new Array[Int](2)
        require(libc.pipe(fds) == 0 && libc.dup2(fds(1), fd) >= 0, s"cannot redirect fd $fd")
        val target = if (fd == 2 || stdoutToStderr) origErr else origOut
        val t = new Thread(() => pump(libc, fds(0), target, fd), s"native-output-$fd")
        t.setDaemon(true)
        t.start()
      }
      available = true
    } catch {
      case e: Throwable =>
        System.err.println(s"[riscvsim] native output capture unavailable: $e")
        available = false
    }
    available
  }

  private def pump(libc: LibC, in: Int, out: Int, stream: Int): Unit = {
    val buf = new Array[Byte](65536)
    val pending = new java.io.ByteArrayOutputStream()
    while (true) {
      val n = libc.read(in, buf, new NativeLong(buf.length.toLong)).intValue()
      if (n <= 0) return
      var off = 0
      while (off < n) off += math.max(0, libc.write(out, java.util.Arrays.copyOfRange(buf, off, n), new NativeLong((n - off).toLong)).intValue())
      var start = 0
      for (i <- 0 until n) if (buf(i) == '\n') {
        pending.write(buf, start, i - start)
        emit(stream, pending.toString("UTF-8"))
        pending.reset()
        start = i + 1
      }
      pending.write(buf, start, n - start)
    }
  }

  private def emit(stream: Int, text: String): Unit = {
    val line = synchronized {
      seqCounter += 1
      val l = Line(seqCounter, stream, text, System.nanoTime())
      recent.addLast(l)
      if (recent.size > maxRecent) recent.removeFirst()
      notifyAll()
      l
    }
    subscribers.forEach(s => s(line))
  }

  /** Writes to the process's real stdout (bypassing the capture). */
  def writeStdout(text: String): Unit = {
    if (!available) { System.out.print(text); System.out.flush(); return }
    val b = text.getBytes("UTF-8")
    var off = 0
    while (off < b.length) {
      val n = libc.write(origOut, java.util.Arrays.copyOfRange(b, off, b.length), new NativeLong((b.length - off).toLong)).intValue()
      if (n <= 0) return
      off += n
    }
  }

  /** Gives the reader threads a moment to pass on what was just printed. */
  def drain(): Unit = {
    System.out.flush(); System.err.flush()
    if (available) Thread.sleep(50)
  }

  def subscribe(f: Line => Unit): Unit = subscribers.add(f)
  def unsubscribe(f: Line => Unit): Unit = subscribers.remove(f)

  /** Sequence number of the last captured line (lines after it are "new"). */
  def mark(): Long = synchronized(seqCounter)

  /** Lines captured after `mark`, oldest first (at most the last 4096 lines are kept). */
  def since(mark: Long): Seq[Line] = synchronized {
    import scala.jdk.CollectionConverters._
    recent.asScala.filter(_.seq > mark).toSeq
  }

  /**
   * Waits up to `timeoutMs` for a line after `mark` that satisfies `p` (output printed just
   * before an event may still be in the pipe).
   */
  def await(mark: Long, timeoutMs: Long)(p: Line => Boolean): Option[Line] = {
    System.out.flush(); System.err.flush()
    val deadline = System.nanoTime() + timeoutMs * 1000000
    synchronized {
      var found = since(mark).reverse.find(p)
      while (found.isEmpty && available && System.nanoTime() < deadline) {
        wait(math.max(1, (deadline - System.nanoTime()) / 1000000))
        found = since(mark).reverse.find(p)
      }
      found
    }
  }
}
