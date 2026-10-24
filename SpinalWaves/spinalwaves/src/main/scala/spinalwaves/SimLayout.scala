package spinalwaves

import java.io.File
import java.nio.file.{Path, Paths}
import scala.collection.mutable
import scala.io.Source

object SimLayout {
  /** Complete VCD scope prefix above top-level signals, including the DUT scope itself.
    * Pass this sequence unchanged to tywaves-rs / Surfer's --extra-scopes option.
    */
  def extraScopes(vcd: Path, topModule: String): Seq[String] = {
    val source = Source.fromFile(vcd.toFile)
    val scopes = mutable.ArrayBuffer.empty[String]
    val candidates = mutable.LinkedHashSet.empty[Vector[String]]
    try source.getLines().takeWhile(!_.contains("$enddefinitions")).foreach { line =>
      val fields = line.trim.split("\\s+")
      if (fields.headOption.contains("$scope") && fields.length >= 3) {
        scopes += fields(2)
        if (fields(2) == topModule) candidates += scopes.toVector
      } else if (fields.headOption.contains("$upscope") && scopes.nonEmpty) scopes.remove(scopes.size - 1)
    } finally source.close()
    require(candidates.size == 1,
      s"Expected one VCD scope named '$topModule' in $vcd, found ${candidates.size}: ${candidates.mkString(", ")}")
    candidates.head
  }
  def extraScopes(vcd: File, topModule: String): Seq[String] = extraScopes(vcd.toPath, topModule)
  def extraScopes(vcd: String, topModule: String): Seq[String] = extraScopes(Paths.get(vcd), topModule)
}
