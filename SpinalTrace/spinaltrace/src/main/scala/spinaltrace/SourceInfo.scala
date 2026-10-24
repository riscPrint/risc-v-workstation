package spinaltrace

import java.io.File

import spinalwaves.SourceLocator

/** Single adapter over `spinalwaves.SourceLocator` so a contract change touches one place. */
object SourceInfo {
  def locate(frame: StackTraceElement, extraRoots: Seq[File]): (String, Int, Int) = {
    val l = SourceLocator.fromFrame(frame, extraRoots.map(_.toPath) ++ SourceLocator.defaultRoots)
    (l.absPath, l.line, l.col)
  }
}
