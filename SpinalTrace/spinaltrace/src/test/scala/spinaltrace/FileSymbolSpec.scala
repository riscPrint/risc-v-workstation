package spinaltrace

import java.nio.file.Files

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._

class FileSymbolSpec extends AnyFunSuite {
  test("probe names from a file with a hyphen in its name are legal Verilog") {
    val dir    = Files.createTempDirectory("st-filesym").toFile
    val report = SpinalTrace.elaborate(SpinalConfig(targetDirectory = dir.getPath))(new HyphenFileDesign)
    val names  = report.toplevel.getAllIo.map(_.getName()) ++ {
      val b = scala.collection.mutable.ArrayBuffer[String]()
      report.toplevel.dslBody.walkDeclarations { case bt: BaseType => b += bt.getName(); case _ => }
      b
    }
    assert(names.exists(_.startsWith("mux_sel_filesymboldesign_l")), names.mkString(", "))
  }
}
