package rvwsmp
import java.io.File
import spinal.core.SpinalConfig
import spinaldb.{DbOptions, SpinalDB}
object CachedDatabase {
  def main(args: Array[String]): Unit = {
    require(args.length == 2,"ELF and database path required")
    val out = new File(args(1)).getCanonicalFile
    SpinalDB.generate(SpinalConfig(inlineRom=true,targetDirectory=new File(out.getParentFile,"rtl").getPath),
      out,DbOptions(meta=Seq("core"->"cached-smp","profile"->"selected handoff line")))(new CachedSmpTop(new File(args(0))))
  }
}
