package riscvsim

import spinal.core._
import spinal.core.sim._

/** Optional mailbox into the DPI client linked with the Verilator model.
  * The adapter sends C2 while the core clock is stopped at a sample boundary. */
class LockstepDpi extends Area {
  private class Mailbox extends BlackBox {
  setDefinitionName("LockstepDpi")
  val io = new Bundle {
    val request = in Bool()
    val length = in UInt(14 bits)
    val payload = in Vec(Bits(4096 bits), 16)
    val status = out SInt(32 bits)
  }
  noIoPrefix()
  private val ports = (0 until 16).map(i => s"input [4095:0] payload_$i").mkString(", ")
  private val words = (0 until 16).reverse.map(i => s"payload_$i").mkString(", ")
  setInlineVerilog(s"""
module LockstepDpi(input request, input [13:0] length,
                   ${ports}, output integer status);
  wire [65535:0] payload = {${words}};
  import "DPI-C" function int rvw_cosim_observe(input string line);
  string line;
  integer i;
  bit armed = 0;
  initial status = -1;
  always @(request) begin
    if (length == 0) armed = 1;
    else if (armed && length <= 8192) begin
      line = "";
      for (i = 0; i < length; i = i + 1)
        line = {line, payload[i*8 +: 8]};
      status = rvw_cosim_observe(line);
    end
  end
endmodule
""")
  }
  private val mailbox = new Mailbox
  val io = mailbox.io.toIo()

  def initialize(): Unit = {
    io.length #= 0
    io.payload.foreach(_ #= 0)
    io.request #= false
    sleep(1)
    io.request #= true
    request = true
    sleep(1)
  }
  private var request = false
  def observe(line: String): Unit = {
    val bytes = line.getBytes("UTF-8")
    require(bytes.length <= 8192, "DPI C2 line exceeds mailbox capacity")
    for (i <- 0 until 16) {
      val chunk = bytes.slice(i * 512, (i + 1) * 512)
      io.payload(i) #= (if (chunk.isEmpty) BigInt(0) else BigInt(1, chunk.reverse))
    }
    io.length #= bytes.length
    request = !request
    io.request #= request
    sleep(1)
    val result = io.status.toInt
    val end = ujson.read(line).obj.get("event").contains(ujson.Str("end"))
    require(result == 0 || (end && result == 1), s"DPI lockstep stopped: status $result")
  }
}
