ThisBuild / scalaVersion := "2.13.14"
ThisBuild / organization := "spinalwaves"
ThisBuild / version := "0.1.0-SNAPSHOT"
lazy val spinalwaves = (project in file("."))
  .settings(
    name := "spinalwaves",
    libraryDependencies ++= Seq(
      "com.github.spinalhdl" %% "spinalhdl-core" % "1.15.0",
      "com.github.spinalhdl" %% "spinalhdl-lib" % "1.15.0",
      compilerPlugin("com.github.spinalhdl" %% "spinalhdl-idsl-plugin" % "1.15.0"),
      "org.scala-lang" % "scala-reflect" % scalaVersion.value,
      "com.lihaoyi" %% "ujson" % "3.3.1",
      "org.scalatest" %% "scalatest" % "3.2.19" % Test
    ),
    fork := true,
    Test / parallelExecution := false
  )
