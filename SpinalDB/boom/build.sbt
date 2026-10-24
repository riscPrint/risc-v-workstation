ThisBuild / scalaVersion := "2.13.14"
ThisBuild / organization := "spinaldb"
ThisBuild / version := "0.1.0-SNAPSHOT"

// Design database of the spinal-boom cores: `sbt "run small out.db"`. A separate build from
// ../spinaldb so generic use never loads (or compiles) a spinal-boom checkout. Uses SPINAL_BOOM,
// by default the private clone next to the repository. Compiling it touches that checkout: run
// under `scripts/with-lock.sh boom`.
val spinalBoomDir = file(sys.env.getOrElse("SPINAL_BOOM", "../../../spinal-boom-eda")).getCanonicalFile

lazy val spinaldb = ProjectRef(file("../spinaldb"), "spinaldb")

lazy val boom = (project in file("."))
  .dependsOn(spinaldb, ProjectRef(spinalBoomDir, "root") % "compile->compile;compile->test")
  .settings(
    name := "spinaldb-boom",
    libraryDependencies += compilerPlugin("com.github.spinalhdl" %% "spinalhdl-idsl-plugin" % "1.15.0"),
    scalacOptions ++= Seq("-deprecation", "-feature", "-language:reflectiveCalls"),
    fork := true,
    javaOptions ++= Seq("-Xss64m", "-Xmx8g", s"-Dspinal.boom=$spinalBoomDir")
  )
