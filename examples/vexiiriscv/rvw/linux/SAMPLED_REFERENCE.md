# Sample a checkpoint continuation with Spike

Keep a copy of the starting checkpoint. Restore another copy with a C2
window. Keep its final checkpoint. Use the frozen runtime that created
those checkpoints. The two checkpoints must have the same model and input
identity. Their compact input histories must have an exact prefix relation.
The reset run must set `RVW_BOOT_REFERENCE_INPUTS=1`. Input history capture
is off by default. It cannot start retrospectively at a later checkpoint.

```sh
python rvw/linux/build_reference.py --shim EXTERNAL_SHIM/librvw_spike.so --out REFERENCE_PROFILE
RVW_SPIKE_MEMORY_LOG=1 python rvw/linux/sample.py --checkpoint BEFORE.zip --end-checkpoint AFTER.zip \
  --trace WINDOW_RUN/rvfi.jsonl --elf INPUTS/reset.elf \
  --payloads INPUTS/payloads.json --map INPUTS/devices.json \
  --shim EXTERNAL_SHIM/librvw_spike.so \
  --reference-extension REFERENCE_PROFILE/vexii-linux.so --out SAMPLE_RESULT -n 32
```

Build the shim with `Cosim/build.sh EXTERNAL_SHIM/librvw_spike.so` from the
workstation root. The command checks its build manifest and linked Spike
identity. The sample command captures the shim, original boot bytes, map
and C2 window outside the repository. It checks the ELF, payload and map
digests against the checkpoint. It checks the trace's ELF and RTL identity.

The project reference profile sets Sv39 and disables Sv48 and Sv57. It
constrains PMP CSR values to the core's 32-bit physical address width. It
keeps Spike's PMP permission logic. It supplies the core's read-only `mtopi`
with standard interrupt priority and omits trigger CSRs because this config
has no TriggerPlugin. These are static model settings from the selected
core config. They do not take values from DUT registers. They do not enable
the full AIA extension. The command checks the profile's binary, source and
linked Spike hashes. It resets the reference after extension registration
and before the first instruction. The bare counter control can use Spike
without this profile. The Linux prefix needs the profile.

`RVW_SPIKE_MEMORY_LOG=1` uses the existing shim's in-memory diagnostic stream.
It avoids a temporary-file operation for each reference instruction. It does
not retain a full retirement trace. The captured environment records this
choice. The default shim behavior remains available.

Spike executes from the original reset ELF. It loads the original payloads
at their recorded addresses. It executes the prefix without storing or
comparing a full RTL trace. It never takes GPRs, CSRs or RAM from the RTL
checkpoint. The compact input history supplies only device-read values,
counter-read values and observed interrupt inputs. Device accesses and
counter accesses must have the recorded PC, instruction and retirement
boundary. Device writes also compare. Other reference state follows Spike.

External records use `rvw.external-interrupts/1`. Pin records affect
reference CSR reads. A core-observed `taken` record supplies the interrupt
at the recorded retirement boundary. The matching trap record checks the
cause, EPC and tval. An external interrupt must have asserted input evidence.
Software-only interrupt state remains in Spike. An unrecorded reference
trap is a mismatch. Missing input, identity or window evidence is an error.

The command compares the next N consecutive retirements after the starting
checkpoint. It checks PC, next PC, instruction, privilege, source registers
and values, destination register and value, memory masks, address and data.
Counter values are explicit synchronized inputs. The result reports their
count. It does not call those counter values independent matches.

A result of `match` covers only the named N-retirement sample. It does not
establish that every instruction in the prefix matched. It does not prove
the whole Linux boot or replace a full C1/C2 regression gate. The current
input binding supports machine software, timer and external pins. It
refuses asserted supervisor-external pins. The shim does not yet bind that
input's CSR view for this sampled path. A CSR read near a pin transition
can also expose a pipeline-input timing difference. It must be diagnosed;
the command does not mask a difference to force a match.

## Native samples

| Workload | Prefix retirements executed | Compared retirements | Result |
|---|---:|---:|---|
| Supervisor counter continuation | 8 | 12 | Match; three counter inputs |
| Same continuation with a corrupted destination | 8 | 0 | Mismatch at the first compared destination |
| Timer control after checkpoint | 14 | 4 | Match; one interrupt |
| Timer recovery after masked checkpoint | 14 | 4 | Match; one interrupt |
| Linux after the first 600-second checkpoint | 2,044,149 | 32 | Match with the project reference profile |
| Same Linux checkpoint, larger sample | 2,044,149 | 1,024 | Match; 168 counter inputs, 124 interrupts and 205 trap events through the sample |

The larger sample took 32.26 seconds for reference execution. Its event and
counter counts include the prefix. It covers two more interrupts than the
32-retirement sample. The RTL window has 1,467 records from 4,096 cycles.
The final pending retirement is omitted. No Linux wave was generated.

The default reference first differed on `pmpaddr0` at order 17,616. A bounded
early trace identified its wider physical address model. The project profile
also resolves the observed MTOPI, trigger-presence and SATP-mode differences.
The corrected diagnostic prefix matched 18,000 retirements after the PMP
binding. The long sample is the separate 1,024-retirement result above.
Neither result establishes a full Linux instruction match. Full prefix
comparison and whole-core qualification remain open.
