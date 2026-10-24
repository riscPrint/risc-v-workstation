package spinaldb

import java.nio.file.{Files, Paths}
import spinal.core._

class CaptureBox(template: String) extends BlackBox {
  setDefinitionName("CaptureBox"); noIoPrefix()
  val y = out Bool()
  setInline(new BlackBoxImpl {
    private var reads = 0
    override def getVerilog(): String = {
      reads += 1
      Files.writeString(Paths.get(template).resolveSibling("inline-reads"), reads.toString)
      Files.readString(Paths.get(template))
    }
  })
}
class CaptureTop(template: String) extends Component {
  setDefinitionName("CaptureTop")
  val y = out Bool()
  val box = new CaptureBox(template)
  y := box.y
}

/** Test-only stdin boundary, used by the shared Python race fixture after RTL emission. */
object CaptureFixtures {
  def main(args: Array[String]): Unit = {
    val root = Paths.get(args(0))
    SpinalDB.generate(SpinalConfig(targetDirectory = root.resolve("rtl").toString),
      root.resolve("design.db").toFile, DbOptions(pdg = false, blocks = false, hgldd = false,
        sourceRoots = Nil, log = message => {
          if (message.startsWith("elaborated ")) {
            println("CAPTURE_EMITTED")
            System.out.flush()
            require(System.in.read() >= 0, "test input closed")
          }
        }))(new CaptureTop(root.resolve("template.v").toString))
  }
}

object CaptureDepsFixtures {
  def main(args: Array[String]): Unit = {
    val root = Paths.get(args(0))
    val result = HdlDeps.captureAll(Seq(HdlDeps.Request("Box", Seq("body" -> root.resolve("Box.v").toFile), Nil, Nil)), Nil)._1.head
    Files.writeString(root.resolve("scan.json"), ujson.write(ujson.Obj(
      "chunks" -> ujson.Arr.from(result.chunks.map { case (label, bytes) =>
        ujson.Arr(label, java.util.Base64.getEncoder.encodeToString(bytes)) }),
      "problems" -> ujson.Arr.from(result.problems))))
  }
}
