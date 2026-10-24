ThisBuild / scalaVersion := "2.13.14"
val spinalBoomDir = file(sys.env.getOrElse("SPINAL_BOOM", "../../../spinal-boom-eda"))
lazy val root = (project in file("."))
  .dependsOn(ProjectRef(file(".."), "root"), ProjectRef(spinalBoomDir, "root") % "compile->compile;compile->test")
  .settings(
    name := "spinalkonata-boom",
    Compile / unmanagedSources += baseDirectory.value.getParentFile.getParentFile /
      "RiscvSim/src/main/scala/riscvsim/ElfFile.scala",
    libraryDependencies += "com.lihaoyi" %% "ujson" % "3.3.1",
    libraryDependencies += compilerPlugin("com.github.spinalhdl" %% "spinalhdl-idsl-plugin" % "1.15.0"),
    fork := true,
    // Keep generated RTL and native simulation work inside the tool worktree.
    run / baseDirectory := baseDirectory.value,
    javaOptions += s"-Dspinalkonata.repo=${baseDirectory.value.getParentFile.getParentFile.getAbsolutePath}",
    javaOptions ++= Seq("-Xss64m", "-Xmx6g", "-XX:ActiveProcessorCount=4")
  )
