ThisBuild / scalaVersion := "2.13.14"
ThisBuild / version := "0.1.0"
val spinalVersion = "1.15.0"
val workstation = file(sys.env("RVW_HOME")).getCanonicalFile
val vex = file(sys.env.getOrElse("VEXRISCV", "..")).getCanonicalFile

// Compile external core sources here; consume the generic simulator as a library.
lazy val root = (project in file("."))
  .dependsOn(ProjectRef(workstation / "RiscvSim", "riscvsim"),
    ProjectRef(workstation / "SpinalChecks", "spinalchecks"))
  .settings(
    name := "rvw-vexriscv",
    Compile / unmanagedSourceDirectories ++= Seq(
      vex / "src/main/scala"),
    libraryDependencies ++= Seq(
      "com.github.spinalhdl" %% "spinalhdl-core" % spinalVersion,
      "com.github.spinalhdl" %% "spinalhdl-lib" % spinalVersion,
      "com.github.spinalhdl" %% "spinalhdl-sim" % spinalVersion,
      compilerPlugin("com.github.spinalhdl" %% "spinalhdl-idsl-plugin" % spinalVersion),
      "org.yaml" % "snakeyaml" % "1.8",
      "com.lihaoyi" %% "ujson" % "3.3.1"),
    scalacOptions ++= Seq("-feature", "-language:reflectiveCalls"),
    fork := true,
    run / javaOptions ++= Seq("-Xss64m", "-Xmx3g")
  )

lazy val db = (project in file("db"))
  .dependsOn(root, ProjectRef(workstation / "SpinalDB/spinaldb", "spinaldb"))
  .settings(
    name := "rvw-vexriscv-db",
    libraryDependencies += compilerPlugin("com.github.spinalhdl" %% "spinalhdl-idsl-plugin" % spinalVersion),
    fork := true,
    run / javaOptions ++= Seq("-Xss64m", "-Xmx3g"))
