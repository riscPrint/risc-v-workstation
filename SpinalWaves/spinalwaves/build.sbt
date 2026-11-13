ThisBuild / scalaVersion := "2.13.14"
ThisBuild / organization := "spinalwaves"
ThisBuild / version := "0.1.0-SNAPSHOT"
lazy val spinalwaves = (project in file("."))
  .dependsOn(SpinalAxis.projects("core", "lib"): _*)
  .settings(SpinalAxis.settings("core", "lib"))
  .settings(
    name := "spinalwaves",
    libraryDependencies ++= Seq(
      "org.scala-lang" % "scala-reflect" % scalaVersion.value,
      "com.lihaoyi" %% "ujson" % "3.3.1",
      "org.scalatest" %% "scalatest" % "3.2.19" % Test
    ),
    fork := true,
    Test / parallelExecution := false
  )
