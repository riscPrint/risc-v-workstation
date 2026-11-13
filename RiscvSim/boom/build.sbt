ThisBuild / scalaVersion := "2.13.14"
val spinalVersion = "1.15.0"

// Separate build: only explicit BOOM launches load the core project.
val spinalBoomDir = file(sys.env.getOrElse("SPINAL_BOOM", "../../../spinal-boom-eda")).getCanonicalFile
lazy val boom = (project in file("."))
  .dependsOn(ProjectRef(file("..").getCanonicalFile, "riscvsim"), ProjectRef(spinalBoomDir, "root") % "compile->compile;compile->test")
  .settings(
    name := "riscvsim-boom",
    libraryDependencies += "org.scalatest" %% "scalatest" % "3.2.19" % Test,
    libraryDependencies += compilerPlugin("com.github.spinalhdl" %% "spinalhdl-idsl-plugin" % spinalVersion),
    scalacOptions ++= Seq("-deprecation", "-feature", "-language:reflectiveCalls"),
    fork := true,
    // BoomSim-style relative paths (formal/, tests) resolve against the BOOM checkout
    run / baseDirectory := spinalBoomDir,
    run / javaOptions ++= Seq("-Xss64m", "-Xmx8g", s"-Driscvsim.boom.dir=$spinalBoomDir")
  )
