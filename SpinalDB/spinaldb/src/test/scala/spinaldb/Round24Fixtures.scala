package spinaldb

import java.nio.file.{Files, Paths}
import spinal.core._

/** Ordinary bidirectional pads, including partial attachments and a real register boundary. */
object Round24Fixtures {
  class PadBox extends BlackBox {
    setDefinitionName("Round24PadBox")
    noIoPrefix()
    val pad = inout(Analog(Bool()))
    val en, d = in Bool()
    val q = out Bool()
    setInlineVerilog("module Round24PadBox(inout pad,input en,input d,output q); " +
      "assign pad=en?d:1'bz; assign q=pad; endmodule")
  }
  class PadTop extends Component {
    val pad = inout(Analog(Bool()))
    val en, d = in Bool()
    val q, delayed = out Bool()
    val bb = new PadBox
    bb.pad <> pad
    bb.en := en
    bb.d := d
    q := bb.q
    delayed := RegNext(bb.q) init False
  }
  class PartialTop extends Component {
    val pads = inout(Analog(Bits(2 bits)))
    val en, d = in Bool()
    val q = out Bool()
    val bb = new PadBox
    bb.pad <> pads(1)
    when(en) { pads(0) := d }
    bb.en := en
    bb.d := d
    q := bb.q
  }
  class DigitalBox extends BlackBox {
    setDefinitionName("Round24DigitalBox")
    noIoPrefix()
    val a = in Bool()
    val q = out Bool()
    setInlineVerilog("module Round24DigitalBox(input a,output q); assign q=a; endmodule")
  }
  class DigitalTop extends Component {
    val a = in Bool()
    val q = out Bool()
    val bb = new DigitalBox
    bb.a := a
    q := bb.q
  }
  def main(args: Array[String]): Unit = {
    val root = Paths.get(args(0))
    for ((name, gen) <- Seq[(String, () => Component)](
      "pad" -> (() => new PadTop), "partial" -> (() => new PartialTop),
      "digital" -> (() => new DigitalTop))) {
      val dir = root.resolve(name)
      Files.createDirectories(dir)
      SpinalDB.generate(SpinalConfig(targetDirectory = dir.resolve("rtl").toString),
        dir.resolve("design.db").toFile,
        DbOptions(pdg = false, blocks = false, hgldd = false, sourceRoots = Nil))(gen())
    }
  }
}
