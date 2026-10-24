package riscvsim

import java.io.File
import scala.io.Source

/**
 * Maps the text an HDL assertion prints back to the Scala source line that declared it.
 * Spinal emits each assertion as `$display("FAILURE msg", args); // File.scala:L123`; this
 * reads those lines from the generated Verilog and turns each format string into a pattern.
 */
class AssertIndex(entries: Seq[AssertIndex.Entry]) {
  def size: Int = entries.size

  /** Source locations ("File.scala:L123") whose message format matches `line`. */
  def locate(line: String): Seq[String] = {
    val t = line.trim
    entries.filter(_.pattern.matches(t)).map(_.location).distinct
  }
}

object AssertIndex {
  case class Entry(format: String, pattern: scala.util.matching.Regex, location: String)

  private val Display = """.*\$(?:display|fatal|error|warning|info)\("((?:[^"\\]|\\.)*)".*//\s*(\S+\.scala:L\d+)\s*$""".r

  def fromVerilog(files: Seq[File]): AssertIndex = new AssertIndex(files.filter(_.isFile).flatMap { f =>
    val src = Source.fromFile(f)
    try src.getLines().collect { case Display(fmt, loc) => Entry(fmt, toPattern(fmt), loc) }.toVector
    finally src.close()
  })

  /** A Verilog format string as a regex: `%x`, `%0d`, `%m`... match anything. */
  def toPattern(fmt: String): scala.util.matching.Regex = {
    val unescaped = fmt.replace("\\n", "\n").replace("\\t", "\t").replace("\\\"", "\"").replace("\\\\", "\\")
    val parts = unescaped.split("%[0-9]*[a-zA-Z]", -1).map(java.util.regex.Pattern.quote)
    ("(?s)" + parts.mkString(".*")).r
  }

  /** True for lines Spinal prints for a failing assertion of severity FAILURE or ERROR. */
  def isFailureLine(text: String): Boolean = {
    val t = text.trim
    t.startsWith("FAILURE") || t.startsWith("ERROR") || t.startsWith("[FAILURE]") || t.startsWith("[ERROR]") ||
      t.contains("Assertion failed") || t.startsWith("%Error")
  }
}
