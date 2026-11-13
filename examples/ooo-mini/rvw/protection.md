# U-mode and PMP checks

The default core has M-mode and U-mode with four PMP entries and four-byte
grain. PMP supports OFF, TOR, NA4 and NAPOT. The lowest matching entry wins.
A partial match faults. Locked entries check M-mode accesses. Locked TOR entries
also lock the preceding address register. PMP configuration clears reserved bits.

Fetch and data permissions are checked before the access. A denied data load
has no load request and produces zero result data. A denied store never changes
RAM. The ROB retains each fault until commit. Recovery can discard a younger
fault without entering a handler. Permission changes and MRET flush younger work.
MPRV uses MPP for data permissions. Trap entry records the prior privilege.
MRET restores it and clears MPRV on return to U-mode. M-mode CSR access from
U-mode traps. U-mode counter access requires mcounteren.

## Measured results

Default configuration, seed 17:

| Check | Result | Limit |
|---|---|---|
| PMP matcher | 26 native cases pass | Range boundaries, all entry positions, priority, locked permissions and empty TOR. Not whole-core proof. |
| Generated RV32 PMP suite | 242/242 RTL pass | Four entries, four-byte grain, M/U cases. |
| Directed speculative faults | 1/1 RTL pass | Divide stalls the head while a branch discards younger denied accesses. Real load/store faults later trap at commit. The protected word stays unchanged. |
| Strict Spike | 243/243 complete traces match; 15,913 instruction records; zero synchronization | No full CSR snapshot. |
| Native properties | 22 monitors, zero firings in all 243 runs | Generated default SV binds also run with assertions enabled. No whole-core proof. |
| PMP isolation pair | Complete, no_leak_observed | One pair, private words 1 and 305419896. Both reset and pass. Public U-mode window is 21 cycles. Each sees only the tohost store on the data bus. This is bounded simulation evidence. |
| Existing smoke and interrupt regression | 13/13 RTL pass before the mem_fault observation-field repair | Includes the new directed program, three smoke cases and nine interrupt cases. |

## Reproduce

Use the native setup and set RVW_HOME to the workstation checkout. Keep raw
outputs in the ignored rvw/out tree. These commands require fresh output names:

```sh
export RVW_SBT_LOCK=sbt-ooomini2
export RVW_OOO_LOCK=ooo-mini-ooomini2
cd examples/ooo-mini
"$RVW_HOME/scripts/with-lock.sh" sbt-ooomini2 nice -n 10 sbt \
  'runMain ooomini.PmpSmoke' 'runMain ooomini.Generate'
nice -n 10 "$RVW_HOME/rvw/.venv/bin/python" rvw/check-protection.py
export RVW_SEC_RTL="$PWD/rvw/out/rtl"
export RVW_SEC_WORK="$PWD/rvw/out/sec-work"
nice -n 10 "$RVW_HOME/rvw/.venv/bin/rvw" sec isolation \
  --manifest rvw/sec/pmp.json --out rvw/out/isolation
```

The comparison script captures the Spike binary, its build manifest, platform,
ELFs and traces once. Fresh Spike instances run the same strict checker as
`rvw cosim check`. Its receipt stays outside version control. No comparison
synchronization is enabled. The security harness uses aligned accesses only;
its word RAM binding does not model the core's general unaligned access port.

The first Spike campaign found a missing mem_fault retirement field. The
field was added to the core before the complete 243-case recapture. Matcher
review also found an empty TOR entry matching a crossing access. The new
native case fails before the range guard and passes after it.

S-mode, translation, delegation, ePMP and debug privilege are absent. Full
privileged ISA compliance is not established. Other privilege families,
isolation policies, secrets, channels and positive leakage controls remain open.
