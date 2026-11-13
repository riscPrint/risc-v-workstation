package riscvsim

import java.io.{BufferedReader, InputStreamReader, PrintWriter}
import java.net.Socket

/** Block each C2 observation until the reference has checked it. */
class Lockstep(port: Int) extends AutoCloseable {
  private val socket = new Socket("127.0.0.1", port)
  socket.setSoTimeout(120000)
  private val input = new BufferedReader(new InputStreamReader(socket.getInputStream, "UTF-8"))
  private val output = new PrintWriter(socket.getOutputStream, true)
  def observe(line: String): Unit = {
    output.println(line)
    val response = input.readLine()
    require(response != null, "lockstep reference disconnected")
    val result = ujson.read(response)
    val status = result("status").str
    if (status != "continue" && !(status == "match" && result("trace_complete").bool))
      throw new IllegalStateException("lockstep stopped: " + response)
  }
  def close(): Unit = socket.close()
}
