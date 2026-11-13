package spinalchecks

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._

class RecoveryChecksSpec extends AnyFunSuite {
  class Top extends Component {
    val allocate = in Bool()
    val release = in Bool()
    val retire = in Bool()
    val device = in Bool()
    val allocateId = in UInt(2 bits)
    val releaseId = in UInt(2 bits)
    val retireId = in UInt(2 bits)
    val deviceId = in UInt(2 bits)
    val allocateTag = in UInt(4 bits)
    val releaseTag = in UInt(4 bits)
    val retireTag = in UInt(4 bits)
    val deviceTag = in UInt(4 bits)
    val kill = in Bits(2 bits)
    val fenceStart = in Bool()
    val fenceDone = in Bool()
    val fenceMask = in Bits(2 bits)
    RecoveryChecks.bind("ops", 2, allocate, allocateId, allocateTag, release, releaseId, releaseTag,
      retire, retireId, retireTag, device, deviceId, deviceTag, kill, fenceStart, fenceDone, fenceMask)
  }

  test("generation-tagged effects and fence snapshots: legal flow and seeded violations") {
    val (cfg, _) = SpinalChecks.install(SpinalConfig(targetDirectory = "generated/recovery",
      defaultConfigForClockDomains = ClockDomainConfig(resetKind = SYNC)), ChecksConfig(mode = Mode.Monitor))
    val compiled = SimConfig.withConfig(cfg).workspacePath("simWorkspace").workspaceName("recovery")
      .withVerilator.compile(new Top)
    val faults = Seq("none", "allocate_busy", "retire_killed", "device_killed", "device_speculative",
      "duplicate_retire", "kill_retired", "retire_on_kill", "old_device_generation", "old_generation", "bad_release", "early_fence",
      "overlap_fence", "unsolicited_fence", "range")
    for(fault <- faults) compiled.doSim(name = fault, seed = 17) { d =>
      def drive(event: String, id: Int, tag: Int, mask: Int): Unit = {
        Seq(d.allocate, d.release, d.retire, d.device, d.fenceStart, d.fenceDone).foreach(_ #= false)
        d.allocateId #= id; d.releaseId #= id; d.retireId #= id; d.deviceId #= id
        d.allocateTag #= tag; d.releaseTag #= tag; d.retireTag #= tag; d.deviceTag #= tag
        d.kill #= 0; d.fenceMask #= mask
        event match {
          case "allocate" => d.allocate #= true
          case "release" => d.release #= true
          case "retire" => d.retire #= true
          case "device" => d.device #= true
          case "kill" => d.kill #= mask
          case "start" => d.fenceStart #= true
          case "done" => d.fenceDone #= true
          case "empty" => d.fenceStart #= true; d.fenceDone #= true
          case "release_done" => d.release #= true; d.fenceDone #= true
          case "back_to_back" => d.release #= true; d.fenceDone #= true; d.fenceStart #= true
          case "kill_done" => d.kill #= mask; d.fenceDone #= true
          case "retire_kill" => d.retire #= true; d.kill #= mask
          case "allocate_start" => d.allocate #= true; d.fenceStart #= true
          case "replace" => d.release #= true; d.allocate #= true; d.allocateTag #= tag + 1
          case _ =>
        }
      }
      drive("", 0, 0, 3)
      d.clockDomain.forkStimulus(10); d.clockDomain.waitSampling(5)
      def step(event: String = "", id: Int = 0, tag: Int = 1, mask: Int = 3): Unit = {
        d.clockDomain.waitFallingEdge(); drive(event, id, tag, mask); d.clockDomain.waitSampling()
      }
      fault match {
        case "none" =>
          step("allocate"); step("start", mask = 1); step("allocate", 1, 2)
          step("release_done"); step("release", 1, 2); step("empty")
          step("allocate", 0, 3); step("start", mask = 1); step("kill_done", mask = 1); step("release", 0, 3)
          step("allocate", 0, 4); step("retire", 0, 4); step("device", 0, 4); step("replace", 0, 4)
          step("retire", 0, 5); step("device", 0, 5); step("release", 0, 5)
          step("allocate", 0, 6); step("start", mask = 1); step("back_to_back", 0, 6); step("done")
          step("allocate", 0, 9); step("allocate", 1, 10); step("start", mask = 1)
          step("release_done", 0, 9); step("empty", mask = 0); step("release", 1, 10)
          step("allocate", 0, 11); step("allocate", 1, 12); step("start")
          step("release", 0, 11); step("allocate", 0, 13); step("release_done", 1, 12); step("release", 0, 13)
          step("allocate", 0, 14); step("allocate_start", 1, 15); step("release_done", 0, 14); step("release", 1, 15)
        case "allocate_busy" => step("allocate"); step("allocate", tag = 2)
        case "retire_killed" => step("allocate"); step("kill", mask = 1); step("retire")
        case "device_killed" => step("allocate"); step("kill", mask = 1); step("device")
        case "device_speculative" => step("allocate"); step("device")
        case "duplicate_retire" => step("allocate"); step("retire"); step("retire")
        case "kill_retired" => step("allocate"); step("retire"); step("kill", mask = 1)
        case "retire_on_kill" => step("allocate"); step("retire_kill", mask = 1)
        case "old_device_generation" => step("allocate"); step("release"); step("allocate", tag = 2); step("retire", tag = 2); step("device", tag = 1)
        case "old_generation" => step("allocate"); step("release"); step("allocate", tag = 2); step("retire", tag = 1)
        case "bad_release" => step("allocate"); step("release", tag = 2)
        case "early_fence" => step("allocate"); step("start"); step("done")
        case "overlap_fence" => step("start"); step("start")
        case "unsolicited_fence" => step("done")
        case "range" => step("allocate", id = 2)
      }
      for(_ <- 0 until 3) step()
      val expected = fault match {
        case "none" => Set.empty[String]
        case "allocate_busy" | "range" => Set("recovery.allocate")
        case "retire_killed" | "duplicate_retire" | "old_generation" | "retire_on_kill" => Set("recovery.retire")
        case "device_killed" | "device_speculative" | "old_device_generation" => Set("recovery.device_effect")
        case "kill_retired" => Set("recovery.kill_retired")
        case "bad_release" => Set("recovery.release")
        case "early_fence" => Set("recovery.fence_drained")
        case _ => Set("recovery.fence_lifecycle")
      }
      assert(ChecksSim.firings(d).map(_.check.kind).toSet == expected, fault)
    }
  }
}
