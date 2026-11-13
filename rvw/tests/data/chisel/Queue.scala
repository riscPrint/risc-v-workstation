//> using scala "2.13.14"
//> using dep "org.chipsalliance::chisel:6.5.0"
//> using plugin "org.chipsalliance:::chisel-plugin:6.5.0"
//> using options "-Ymacro-annotations"
import chisel3._
import chisel3.util._
class QueueTop extends Module {
  val io = IO(new Bundle {
    val in = Flipped(Decoupled(UInt(8.W)))
    val out = Decoupled(UInt(8.W))
  })
  io.out <> Queue(io.in, entries=4)
}
object GenerateQueue extends App {
  java.nio.file.Files.writeString(java.nio.file.Paths.get("QueueTop.fir"),
    _root_.circt.stage.ChiselStage.emitCHIRRTL(new QueueTop))
}
