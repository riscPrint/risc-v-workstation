scalaVersion := "2.13.14"
libraryDependencies ++= Seq(
  "com.github.spinalhdl" %% "spinalhdl-core" % "1.15.0",
  compilerPlugin("com.github.spinalhdl" %% "spinalhdl-idsl-plugin" % "1.15.0")
)
fork := true
run / javaOptions ++= Seq("-Xmx1g", "-XX:ActiveProcessorCount=2")
