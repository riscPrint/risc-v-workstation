// Run with `sbt '++2.13.14!' ...` and RVW_SPINAL_SOURCE=$NAXRISCV/ext/SpinalHDL (run.sh sets both).
// NaxRiscv pins its own SpinalHDL source (ext/SpinalHDL) and declares Scala 2.12.18. This build
// compiles that SpinalHDL source and the NaxRiscv sources with Scala 2.13.14, and selects the source
// axis of the workstation libraries (scripts/sbt/SpinalAxis.scala), so RiscvSim, SpinalProbes,
// SpinalChecks and SpinalDB are compiled against the same SpinalHDL source as the core.
ThisBuild / scalaVersion := "2.12.18"
ThisBuild / version := "0.1.0"
val workstation = file(sys.env("RVW_HOME")).getCanonicalFile
val nax = file(sys.env.getOrElse("NAXRISCV", "..")).getCanonicalFile
val spinal = (nax / "ext/SpinalHDL").getCanonicalFile
val axisChecked = {
  require(SpinalAxis.source.contains(spinal),
    s"Set RVW_SPINAL_SOURCE=$spinal: the workstation libraries must use NaxRiscv's pinned SpinalHDL source.")
  true
}

lazy val root = (project in file("."))
  .dependsOn(ProjectRef(workstation / "RiscvSim", "riscvsim"))
  .dependsOn(SpinalAxis.projects("core", "lib", "sim"): _*)
  .settings(SpinalAxis.settings("core", "lib", "sim"))
  .settings(
    name := { require(axisChecked); "rvw-naxriscv" },
    // The core sources are compiled here; NaxRiscv's own build files stay unused.
    Compile / unmanagedSourceDirectories ++= Seq(nax / "src/main/scala", nax / "ext/rvls/bindings/jni"),
    // Sandboxes and board/ASIC generators are not part of the core and are not compiled.
    Compile / unmanagedSources / excludeFilter := HiddenFileFilter || new SimpleFileFilter(f => {
      val p = f.getPath
      p.contains("/naxriscv/sandbox/") || p.contains("/naxriscv/platform/asic/") || p.contains("/riscv/model/") || p.contains("/platform/tilelinkdemo/")
    }),
    libraryDependencies ++= Seq(
      "org.scalatest" %% "scalatest" % "3.2.17",
      "org.yaml" % "snakeyaml" % "1.8",
      "net.fornwall" % "jelf" % "0.7.0",
      "com.lihaoyi" %% "ujson" % "3.3.1"),
    scalacOptions ++= Seq("-feature", "-language:reflectiveCalls", "-language:postfixOps"),
    fork := true,
    run / javaOptions ++= Seq("-Xss64m", "-Xmx3g")
  )

lazy val db = (project in file("db"))
  .dependsOn(root, ProjectRef(workstation / "SpinalDB/spinaldb", "spinaldb"))
  .settings(SpinalAxis.settings("core", "lib", "sim"))
  .settings(
    name := "rvw-naxriscv-db",
    fork := true,
    run / javaOptions ++= Seq("-Xss64m", "-Xmx3g"))

// Reuse the pinned upstream simulation observer without changing the core checkout.
// Its supervisor interrupt checker assumes S exists. Guard that optional pin for M-only RTL.
root / Compile / sourceGenerators += Def.task {
  val source = IO.read(nax / "src/main/scala/naxriscv/platform/NaxriscvProbe.scala")
  val header = source.substring(0, source.indexOf("class NaxriscvTilelinkProbe"))
    .replace("package naxriscv.platform", "package rvwnax\nimport naxriscv.platform.{TraceBackend, TraceIo}")
  val pin = "val intSupervisorExternal = new InterruptChecker(ioInt.supervisor.external, 9)"
  val check = "intSupervisorExternal.check()"
  require(source.contains(pin) && source.contains(check), "pinned commit observer changed")
  val body0 = source.substring(source.indexOf("class NaxriscvProbe("))
    .replace("class NaxriscvProbe(", "class CommitProbe(")
    .replace(pin, "val intSupervisorExternal = if (privPlugin.p.withSupervisor) Some(new InterruptChecker(ioInt.supervisor.external, 9)) else None")
    .replace(check, "intSupervisorExternal.foreach(_.check())")
  // The pinned UInt simulation API rejects toLong on a 64-bit wire.
  val wires = Seq("port.data", "csrAccess.write", "csrAccess.read",
    "trapWb.trap.tval", "ioBus.cmd.address", "ioBus.cmd.data", "ioBus.rsp.data",
    "lsuWb.address", "lsuWb.readData", "aguWb.data", "amoLoadWb.readData", "amoStoreWb.storeData")
  val body1 = wires.foldLeft(body0.replace("commitRobToPcValue(i).toLong", "riscvsim.SimEncoding.longBits(commitWb.robToPc.pc(i))")) { (text, wire) =>
    text.replace(wire + ".toLong", "riscvsim.SimEncoding.longBits(" + wire + ")")
  }
  val body = body1
    .replace("    var pc = -1l;", "    var pc = -1l;\n    var instruction = Option.empty[Long]\n    var mode = Option.empty[Int]\n    var physicalAddress = 0L")
    .replace("  var cycleSinceLastCommit = 0", """  var trapValue = Option.empty[() => Long]
  var instructionAt = Option.empty[Int => Long]
  var modeAtAllocation = Option.empty[() => Int]
  var virtualAddress = Option.empty[() => Long]
  var currentInstruction = Option.empty[Long]
  var currentMode = Option.empty[Int]
  var currentPhysicalAddress = Option.empty[Long]
  var cycleSinceLastCommit = 0""")
    .replace("        ctx.pc = pc", "        ctx.pc = pc\n        ctx.instruction = instructionAt.map(f => f(i))\n        ctx.mode = modeAtAllocation.map(f => f())")
    .replace("        backends.foreach(_.commit(hartId, robCtx.pc))", """        currentInstruction = robCtx.instruction
        currentMode = robCtx.mode
        currentPhysicalAddress = if (robCtx.loadValid || robCtx.storeValid) Some(robCtx.physicalAddress) else None
        backends.foreach(_.commit(hartId, robCtx.pc))""")
    .replace("val tval : Long = riscvsim.SimEncoding.longBits(trapWb.trap.tval)", "val tval : Long = trapValue.map(f => f()).getOrElse(riscvsim.SimEncoding.longBits(trapWb.trap.tval))")
    .replace("      ctx.lsuAddress = riscvsim.SimEncoding.longBits(lsuWb.address)", """      ctx.physicalAddress = riscvsim.SimEncoding.longBits(lsuWb.address)
      ctx.lsuAddress = virtualAddress.map(f => f()).getOrElse(ctx.physicalAddress)""")
  val out = (root / Compile / sourceManaged).value / "rvwnax" / "CommitProbe.scala"
  IO.write(out, header + body)
  Seq(out)
}.taskValue
