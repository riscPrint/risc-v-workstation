ThisBuild / scalaVersion := "2.13.14"
val workstation = file(sys.env("RVW_HOME")).getCanonicalFile
val vexii = file(sys.env("VEXIIRISCV")).getCanonicalFile
val spinal = vexii / "ext/SpinalHDL"
lazy val idsl = ProjectRef(spinal, "idslplugin")
lazy val root = (project in file("."))
  .dependsOn(idsl, ProjectRef(spinal, "core"), ProjectRef(spinal, "lib"), ProjectRef(spinal, "sim"))
  .settings(
    Compile / unmanagedSourceDirectories ++= Seq(vexii / "src/main/scala",
      vexii / "ext/rvls/bindings/spinal", vexii / "ext/rvls/bindings/jni", baseDirectory.value / "generated"),
    Compile / unmanagedSources ++= Seq(baseDirectory.value / "VexiiCore.scala", baseDirectory.value / "Run.scala") ++
      Seq("Soc.scala", "Buses.scala", "Peripherals.scala", "Serial.scala", "SimpleBus.scala", "ProtocolChecks.scala").map(workstation / "SpinalSoc/src/main/scala/rvwsoc" / _),
    Compile / unmanagedSources ++= Seq("ProtocolChecks.scala", "AxiReadChecks.scala", "AxiWriteChecks.scala",
      "TileLinkProbeChecks.scala", "BusAssertions.scala").map(workstation / "SpinalChecks/src/main/scala/spinalchecks" / _),
    libraryDependencies ++= Seq(
      "org.scala-lang" % "scala-reflect" % scalaVersion.value,
      "org.scala-lang" % "scala-compiler" % scalaVersion.value,
      "com.github.scopt" %% "scopt" % "4.1.0", "com.lihaoyi" %% "sourcecode" % "0.3.0",
      "commons-io" % "commons-io" % "2.11.0", "net.openhft" % "affinity" % "3.23.2",
      "org.slf4j" % "slf4j-simple" % "2.0.5", "com.github.oshi" % "oshi-core" % "6.4.0",
      "org.scalatest" %% "scalatest" % "3.2.17", "org.yaml" % "snakeyaml" % "1.8",
      "net.fornwall" % "jelf" % "0.7.0", "org.scream3r" % "jssc" % "2.8.0",
      "com.lihaoyi" %% "ujson" % "3.3.1"),
    scalacOptions += (idsl / Compile / packageBin / artifactPath).map(f => s"-Xplugin:${f.getAbsolutePath}").value,
    Compile / compile := (Compile / compile).dependsOn(idsl / Compile / packageBin).value,
    fork := true,
    run / javaOptions ++= Seq("-Xss64m", "-Xmx3g")
  )
