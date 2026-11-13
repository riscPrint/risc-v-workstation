ThisBuild / scalaVersion := "2.13.14"
ThisBuild / organization := "rvwsoc"
ThisBuild / version := "0.1.0-SNAPSHOT"
val spinalVersion = "1.15.0"
libraryDependencies ++= Seq(
  "com.github.spinalhdl" %% "spinalhdl-core" % spinalVersion,
  "com.github.spinalhdl" %% "spinalhdl-lib" % spinalVersion,
  compilerPlugin("com.github.spinalhdl" %% "spinalhdl-idsl-plugin" % spinalVersion)
)
Compile / unmanagedSourceDirectories += baseDirectory.value / "generated"
fork := true
Compile / unmanagedSources ++= {
  val example = baseDirectory.value / "examples" / "stub"
  Seq(example / "Stub.scala") ++ (if (sys.props.get("rvw.soc.stub").contains("true")) Seq(example / "Run.scala") else Nil)
}
Compile / unmanagedSources ++= {
  if (sys.props.get("rvw.soc.vex").contains("true")) {
    val vex = file(sys.env("VEXRISCV"))
    (vex / "src/main/scala" ** "*.scala").get ++
      (baseDirectory.value / "examples/vex" ** "*.scala").get
  } else Nil
}
libraryDependencies ++= (if (sys.props.get("rvw.soc.vex").contains("true"))
  Seq("org.yaml" % "snakeyaml" % "1.8") else Nil)
