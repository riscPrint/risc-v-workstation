ThisBuild / scalaVersion := "2.13.14"
ThisBuild / organization := "spinalblocks"
ThisBuild / version := "0.1.0-SNAPSHOT"

val spinalVersion = "1.15.0"

// Source locations (two-pass elaboration, source-root lookup) come from the sibling SpinalWaves project.
lazy val spinalwaves = ProjectRef(file("../../SpinalWaves/spinalwaves"), "spinalwaves")

lazy val spinalblocks = (project in file("."))
  .dependsOn(spinalwaves)
  .settings(
    name := "spinalblocks",
    libraryDependencies ++= Seq(
      "com.github.spinalhdl" %% "spinalhdl-core" % spinalVersion,
      "com.github.spinalhdl" %% "spinalhdl-lib" % spinalVersion,
      compilerPlugin("com.github.spinalhdl" %% "spinalhdl-idsl-plugin" % spinalVersion),
      "com.lihaoyi" %% "ujson" % "3.3.1",
      "org.scalatest" %% "scalatest" % "3.2.19" % Test
    ),
    scalacOptions ++= Seq("-deprecation", "-feature", "-language:reflectiveCalls"),
    fork := true,
    Test / parallelExecution := false
  )

// Diagrams of the spinal-boom cores: `sbt "boom/run small"`. Needs a spinal-boom checkout, by default
// next to this repository; set SPINAL_BOOM to use another one.
val spinalBoomDir = file(sys.env.getOrElse("SPINAL_BOOM", "../../../spinal-boom"))
lazy val boom = (project in file("boom"))
  .dependsOn(spinalblocks, ProjectRef(spinalBoomDir, "root") % "compile->compile;compile->test")
  .settings(
    name := "spinalblocks-boom",
    libraryDependencies += compilerPlugin("com.github.spinalhdl" %% "spinalhdl-idsl-plugin" % spinalVersion),
    scalacOptions ++= Seq("-deprecation", "-feature", "-language:reflectiveCalls"),
    fork := true,
    run / baseDirectory := spinalBoomDir.getAbsoluteFile,
    javaOptions ++= Seq("-Xss64m", "-Xmx8g")
  )
