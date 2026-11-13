ThisBuild / scalaVersion := "2.13.14"
val workstation = file(sys.env("RVW_HOME")).getCanonicalFile
lazy val root = (project in file("."))
  .dependsOn(ProjectRef(workstation / "RiscvSim", "riscvsim"), ProjectRef(workstation / "SpinalChecks", "spinalchecks"), ProjectRef(workstation / "SpinalDB/spinaldb", "spinaldb"))
  .settings(
    name := "ooo-mini",
    libraryDependencies += compilerPlugin("com.github.spinalhdl" %% "spinalhdl-idsl-plugin" % "1.15.0"),
    scalacOptions ++= Seq("-language:reflectiveCalls"),
    fork := true,
    run / javaOptions ++= Seq("-Xmx2g", "-XX:ActiveProcessorCount=2")
  )
