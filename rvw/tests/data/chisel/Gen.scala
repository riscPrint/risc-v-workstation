//> using scala "2.13.14"
//> using dep "org.chipsalliance::chisel:6.5.0"
//> using plugin "org.chipsalliance:::chisel-plugin:6.5.0"
//> using options "-Ymacro-annotations"
import chisel3._
import chisel3.util._

class Acc(w: Int) extends Module {
  val io = IO(new Bundle {
    val in = Flipped(Valid(UInt(w.W)))
    val out = Output(UInt(w.W))
  })
  val acc = RegInit(0.U(w.W))
  when(io.in.valid) {
    acc := acc + io.in.bits
  }
  io.out := acc
}

class Top extends Module {
  val io = IO(new Bundle {
    val a = Flipped(Valid(UInt(8.W)))
    val b = Input(Bool())
    val sel = Input(UInt(2.W))
    val y = Output(Vec(2, UInt(8.W)))
    val r = Output(UInt(8.W))
  })
  val units = Seq.fill(2)(Module(new Acc(8)))
  for ((u, i) <- units.zipWithIndex) {
    u.io.in := io.a
    io.y(i) := u.io.out
  }
  val mem = Mem(4, UInt(8.W))
  when(io.a.valid) { mem.write(io.sel, io.a.bits) }
  io.r := mem.read(io.sel)
}

object Gen extends App {
  java.nio.file.Files.writeString(java.nio.file.Paths.get("Top.fir"),
    _root_.circt.stage.ChiselStage.emitCHIRRTL(new Top))
}
