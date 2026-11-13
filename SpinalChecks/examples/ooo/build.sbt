ThisBuild / scalaVersion := "2.13.14"
lazy val fixture = (project in file("."))
  .dependsOn(ProjectRef(file("../.."), "spinalchecks"), ProjectRef(file("../../../SpinalProbes"), "spinalprobes"))
  .settings(
    Compile / unmanagedSources ++= Seq(baseDirectory.value / "TinyOoo.scala", baseDirectory.value / "Run.scala"),
    libraryDependencies += compilerPlugin("com.github.spinalhdl" %% "spinalhdl-idsl-plugin" % "1.15.0"),
    fork := true,
    run / javaOptions ++= Seq("-Xmx2g", "-XX:ActiveProcessorCount=2")
  )
