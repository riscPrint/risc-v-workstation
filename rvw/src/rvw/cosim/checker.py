"""Model-independent comparison policy. All accepted differences are recorded."""
from collections import deque
from .trace import HEX, Trace

# Kinds of synchronization (each can be switched off on its own; --strict turns off all).
SYNC_KINDS = ("counter", "mmio", "csr", "irq")

# Standard counters and machine aliases, including RV32 high halves.
COUNTERS = set(range(0xc00, 0xc20)) | set(range(0xc80, 0xca0)) | {0xb00, 0xb02, 0xb80, 0xb82} | set(range(0xb03, 0xb20)) | set(range(0xb83, 0xba0))


INSTRET = {0xb02, 0xc02, 0xb82, 0xc82}
# mip/sip bits that show external interrupt inputs (MSIP, MTIP, SEIP, MEIP; further limited to the
# platform's declared `irq_inputs`). The reference has no
# interrupt sources, so a read may take such a bit from the core, but only as a 1 the reference
# lacks (an input ORs into the bit; SEIP that software wrote is reference state and compared) and
# only with evidence that the input was high: an irq level event in the trace (from the input
# latency before the previous retirement up to the read), or, in a trace without level events,
# the handler of an interrupt with that cause (up to its xRET). Level events are kept as bounded
# per-bit state (last cycle set high, cycle it went low after that), never as a history.
IRQ_INPUT_MASKS = {0x344: 0xa88, 0x144: 0x200}
XRET = (0x30200073, 0x10200073)
HEX_FIELDS = set(HEX) | {"cause", "tval", "fd_wdata", "fflags", "fcsr"}
# C2 lets the records of cycle N come before the irq event of cycle N, so the checker reads one
# cycle at a time and applies its irq events before its other records. A real core retires a few
# instructions per cycle; a trace with more records than this in one cycle is refused with an error
# rather than compared without some of that cycle's level events.
MAX_RECORDS_PER_CYCLE = 4096


def irq_first_by_cycle(records):
    """The records of `records` (cycles never decrease) with each cycle's irq events moved before
    that cycle's other records; otherwise in file order. Holds at most one cycle."""
    group, cycle = [], None
    for record in records:
        if record["cycle"] != cycle:
            yield from sorted(group, key=lambda r: r.get("event") != "irq")   # stable
            group, cycle = [], record["cycle"]
        if len(group) >= MAX_RECORDS_PER_CYCLE:
            raise ValueError(f"more than {MAX_RECORDS_PER_CYCLE} records in cycle {cycle}: the checker "
                             "cannot place that cycle's irq level events")
        group.append(record)
    yield from sorted(group, key=lambda r: r.get("event") != "irq")


class ReferenceEnded(Exception):
    """The reference stopped at its own program termination (`status` "pass" or "fail"),
    for example Sail at an HTIF tohost write. The comparison ends there."""
    def __init__(self, status):
        super().__init__(f"reference ended ({status})")
        self.status = status


def c2_view(values):
    """A record or effect with C2 value fields as lowercase hex strings, like the trace."""
    result = {k: hex(v) if k in HEX_FIELDS and type(v) is int else v for k, v in values.items()}
    if "csr_state" in result:
        result["csr_state"] = {k: hex(v) for k, v in result["csr_state"].items()}
    if "fault_access" in result:
        result["fault_access"] = {k: hex(v) if k in ("addr", "rdata", "wdata") and v is not None else v
                                  for k, v in result["fault_access"].items()}
    from .extensions import serialize
    for name in ("vector", "hypervisor", "debug"):
        if name in result:
            result[name] = serialize(result[name])
    return result


def counter_read(insn):
    # CSRRS/CSRRC rs1=x0 or CSRRSI/CSRRCI zimm=0, never a modifying access.
    return (insn & 0x7f == 0x73 and (insn >> 12) & 7 in (2, 3, 6, 7)
            and (insn >> 15) & 31 == 0 and insn >> 20 in COUNTERS)


def csr_access(insn):
    """CSR number of a Zicsr instruction, or None."""
    if insn & 0x7f == 0x73 and (insn >> 12) & 7 in (1, 2, 3, 5, 6, 7):
        return insn >> 20
    return None


def masked(value, mask):
    return value & sum(255 << (8*i) for i in range(8) if mask >> i & 1)


def differences(actual, expected, fields):
    return {k: {"expected": expected[k], "actual": actual[k]}
            for k in fields if actual[k] != expected[k]}


def check(trace_path, model, platform, history=10, sync=SYNC_KINDS, *, ordered_events=False):
    """Compare a C2 trace with `model`. `sync` lists the enabled synchronization kinds
    (SYNC_KINDS); sync=() turns all of them off."""
    if platform.cheri is not None:
        raise ValueError("CHERI capability comparison is not implemented")
    enabled = set(sync)
    if enabled - set(SYNC_KINDS):
        raise ValueError(f"unknown synchronization kinds {sorted(enabled - set(SYNC_KINDS))}")
    xmask = (1 << platform.xlen) - 1
    from .reset_scratch import ResetScratch
    scratch = ResetScratch(xmask if "csr" in enabled and platform.trace_from_reset else 0)
    trace = Trace(trace_path)
    if trace.multihart:
        from .multihart import check_multihart
        return check_multihart(trace, model, platform, history=history, sync=sync)
    recent = deque(maxlen=history)
    core_regs = [0] * 32
    count, trap_events, sync_count = 0, 0, 0
    translation_count = 0
    csr_snapshot_steps = 0
    vector_memory_steps = 0
    vector_memory_accesses = 0
    fault_access_steps = 0
    fp_reset_pending = platform.fcsr_reset == "unspecified" and "csr" in enabled and trace.state and trace.header["schema"] == "rvw.rvfi/2"
    instret_synced = False
    sync_recent = deque(maxlen=history)
    applied_masks = {}
    quirks = deque(maxlen=history)
    last_trap = None
    after_trap = False
    event_effect = None
    event_prior_handler = False
    ended = False
    end_status = None
    last_order = None
    last_cycle = None
    # Once the trace carries irq level events: {bit: [cycle last set high, cycle it went low
    # after that or None while high]}; at most XLEN entries however long the trace. Else None.
    irq_inputs = None
    irq_handler = 0        # without level events: interrupt causes (as mip bits) whose handler runs
    previous_cycle = 0     # cycle of the previous instruction record
    def irq_level(cycle, levels):
        for bit, state in irq_inputs.items():
            if not levels >> bit & 1 and state[1] is None:
                state[1] = cycle               # went low
        while levels:
            low = levels & -levels
            irq_inputs[low.bit_length() - 1] = [cycle, None]
            levels ^= low
    def irq_evidence():
        """mip bits of interrupt inputs that may have been high for the read being checked: high
        at some cycle from `irq_input_latency` before the previous retirement up to the read
        (cycles never decrease, so every event read so far is at or before the read)."""
        if irq_inputs is None:
            return irq_handler
        start = previous_cycle - platform.irq_input_latency
        return sum(1 << bit for bit, (_, low) in irq_inputs.items() if low is None or low > start)
    environment = None
    def result(status, **extra):
        return {"schema": "rvw.cosim/1", "status": status, "model": model.name if hasattr(model, "name") else "spike",
                "instructions": count, "trap_events": trap_events,
                "reference_limits": list(getattr(model, "limitations", ())),
                "state_coverage": {"trace_schema": trace.header["schema"],
                                   "fp": trace.header["schema"] == "rvw.rvfi/2" and trace.state and last_order is not None,
                                   "vector": trace.header.get("vector") if last_order is not None else None,
                                   "hypervisor": bool(trace.header.get("hypervisor") and last_order is not None),
                                   "two_stage_translations": translation_count,
                                   "csr_snapshot": trace.header.get("csr_snapshot", []),
                                   "csr_snapshot_steps": csr_snapshot_steps,
                                   "vector_memory_steps": vector_memory_steps,
                                   "vector_memory_accesses": vector_memory_accesses,
                                   "fault_access_steps": fault_access_steps,
                                   "environment": trace.header.get("environment"),
                                   "environment_events": environment.events if environment else 0},
                "platform_policy": {key: getattr(platform, key) for key in
                                    ("privilege_modes", "misaligned", "endianness",
                                     "absent_pmp_csrs", "ecall_tval", "pmp_granularity", "memory_read_convention", "scalar_split_ram")},
                "applied_masks": [{"reason": reason, "csr": hex(csr), "mask": hex(mask)}
                                  for (reason, csr), mask in sorted(applied_masks.items())],
                "synchronized": sync_count, "recent_synchronizations": list(sync_recent),
                "trace_complete": ended, "end_status": end_status,
                "last_order": last_order, "last_cycle": last_cycle, "pending_handler": after_trap,
                "recent_quirks": list(quirks), "sync_enabled": sorted(enabled), **extra}
    def mismatch(actual, expected, diff, index):
        regs = list(core_regs)
        if "event" not in actual and actual["rd"]:
            regs[actual["rd"]] = actual["rd_wdata"]
        reg_diff = [{"reg": f"x{i}", "expected": hex(expected["regs"][i]), "actual": hex(regs[i])}
                    for i in range(1, 32) if regs[i] != expected["regs"][i]]
        return result("mismatch", mismatch={"instruction_index": index,
                      "order": actual.get("order", last_order), "cycle": actual["cycle"],
                      "pc": hex(expected["pc"]), "disassembly": expected["disasm"],
                      "differences": {k: {side: hex(x) if k in HEX_FIELDS else x for side, x in v.items()}
                                      for k, v in diff.items()},
                      "actual": c2_view(actual),
                      "expected": c2_view({k: v for k, v in expected.items() if k not in ("regs", "before")}),
                      "last_matching": list(recent), "register_diff": reg_diff})
    try:
        if trace.header["xlen"] != platform.xlen or trace.header["isa"].lower() != platform.isa.lower():
            raise ValueError("trace ISA/XLEN must exactly match the selected platform")
        from .environment import Environment
        environment = Environment() if getattr(trace, "environment", False) else None
        records = iter(trace) if ordered_events or environment else irq_first_by_cycle(iter(trace))
        reference_end = None
        for actual in records:
            if 'event' not in actual:
                actual = platform.normalize_record(actual)
            last_cycle = actual["cycle"]
            if actual.get("event") == "end":
                if environment and (environment.read is not None or environment.write is not None):
                    raise ValueError("unconsumed device response at end")
                ended, end_status = True, actual["status"]
                continue
            if actual.get("event") == "environment":
                environment.event(actual, model, platform)
                if actual['kind'] == 'pins':
                    if irq_inputs is None:
                        irq_inputs = {}
                    irq_level(actual['cycle'], actual['levels'])
                continue
            if actual.get("event") == "irq":
                if irq_inputs is None:
                    irq_inputs = {}
                irq_level(actual["cycle"], actual["levels"])
                continue
            if actual.get("event") == "external_interrupt":
                if not hasattr(model, 'external_interrupt_event'):
                    raise ValueError('reference cannot consume declared external-interrupt evidence')
                model.external_interrupt_event(actual)
                continue
            if actual.get("event") == "debug":
                if not hasattr(model, 'debug_event'):
                    raise ValueError('reference cannot check debug transitions')
                expected = model.debug_event(actual['action'])
                from .debug_state import differences as debug_diff
                diff = debug_diff(actual['debug'], expected['debug'])
                if diff:
                    return mismatch(actual, expected, diff, count)
                continue
            if actual.get("event") == "trap":
                if environment and actual.get("before_order") != environment.order:
                    raise ValueError("trap lacks its environment retirement boundary")
                represented = last_trap is not None
                # With recorded input levels, an input interrupt is injected only when its input
                # was high (same window as the mip/sip evidence). A trap whose input stayed low
                # contradicts the trace: it is not injected and is a mismatch.
                unasserted = False
                if actual["intr"] and not represented and irq_inputs is not None:
                    code = actual["cause"] & ~(1 << (platform.xlen - 1))
                    unasserted = code in platform.irq_inputs and not irq_evidence() >> code & 1
                try:
                    expected = last_trap if represented else model.step(
                        interrupt=actual["cause"] if actual["intr"] and not unasserted else 0)
                except ReferenceEnded as end:
                    reference_end = end.status
                    break
                diff = differences(actual, expected, ["intr", "cause", "tval"])
                if unasserted:
                    diff["irq_input"] = {"expected": "high within irq_input_latency", "actual": "low"}
                # The spec lets a core write zero to xtval for illegal instructions.
                if ("tval" in diff and platform.illegal_insn_tval == "zero" and not actual["intr"]
                        and actual["cause"] == 2 and expected["cause"] == 2 and actual["tval"] == 0):
                    if not hasattr(model, "set_trap_tval"):
                        raise ValueError("the model cannot apply illegal_insn_tval=zero (configure it to write zero)")
                    del diff["tval"]
                    model.set_trap_tval(0)
                # ECALL has one declared value. Never take an arbitrary tval from the core.
                if (not actual["intr"] and expected["trap"] and not expected["intr"]
                        and actual["cause"] == expected["cause"]
                        and expected["cause"] in (8, 9, 11) and expected["insn"] == 0x73):
                    wanted = 0x73 if platform.ecall_tval == "insn" else 0
                    if actual["tval"] != wanted:
                        diff["tval"] = {"expected": wanted, "actual": actual["tval"]}
                    else:
                        diff.pop("tval", None)
                        if expected["tval"] != wanted:
                            if not hasattr(model, "set_trap_tval"):
                                raise ValueError("the model cannot apply ecall_tval")
                            model.set_trap_tval(wanted)
                            quirks.append({"quirk": "ecall_tval", "value": hex(wanted)})
                if not expected["trap"]:
                    diff["trap"] = {"expected": False, "actual": True}
                if diff:
                    return mismatch(actual, expected, diff, count-1 if last_trap is not None else count)
                trap_events += 1
                if actual["intr"]:
                    code = actual["cause"] & ~(1 << (platform.xlen - 1))
                    if code < platform.xlen:
                        irq_handler |= 1 << code
                event_prior_handler = after_trap
                event_effect = None if represented else expected
                after_trap = True
                last_trap = None
                continue
            if fp_reset_pending:
                from .reset_fp import seed
                entry = seed(actual, model, platform, prior_events=trap_events)
                if entry is not None:
                    sync_recent.append(entry)
                    sync_count += 1
                fp_reset_pending = False
            last_order = actual["order"]
            # intr marks the first handler instruction after any trap. An
            # interrupt event supplies cause; never infer a cause from a boolean.
            mmio = environment.retire(actual) if environment else platform.mmio_read(actual) if "mmio" in enabled else None
            represented_by_event = (event_effect is not None and not event_effect["intr"]
                                    and actual["trap"] and actual["pc"] == event_effect["pc"])
            try:
                expected = event_effect if represented_by_event else model.step(mmio=mmio)
            except ReferenceEnded as end:
                reference_end = end.status
                break
            expected_handler = event_prior_handler if represented_by_event else after_trap
            event_effect = None
            if "vector" in trace.header and getattr(model, "vector_config", None) != trace.header["vector"]:
                raise ValueError("reference VLEN/ELEN differs from trace or is unavailable")
            if actual.get("hypervisor", {}).get("translations"):
                if not hasattr(model, "translations"):
                    raise ValueError("reference cannot check two-stage translation records")
                expected["hypervisor"]["translations"] = model.translations(expected)
            if trace.header.get("vector_memory"):
                vector_memory_steps += 1
                vector_memory_accesses += len(actual["vector_accesses"])
            fields = ["pc", "pc_next", "insn", "mode", "trap", "rd", "mem_rmask", "mem_wmask", "mem_fault"]
            if trace.header["schema"] == "rvw.rvfi/2" and trace.state:
                state_fields = ["fd_valid", "fflags", "fcsr"]
                if actual["fd_valid"] or expected.get("fd_valid"):
                    state_fields += ["fd", "fd_wdata"]
                missing = set(state_fields) - expected.keys()
                if missing:
                    raise ValueError(f"reference cannot check C2 state fields: {sorted(missing)}")
                fields += state_fields
            diff = differences(actual, expected, fields)
            from .extensions import compare_extensions
            diff.update(compare_extensions(actual, expected, trace.header))
            reset_mask, reset_entries = scratch.observe(expected, actual, model)
            if actual.get("csr_state"):
                if not hasattr(model, "csr_snapshot"):
                    raise ValueError("reference cannot check CSR snapshots")
                snapshot = model.csr_snapshot(trace.header["csr_snapshot"])
                expected["csr_state"] = snapshot
                csr_snapshot_steps += 1
                for address, value in actual["csr_state"].items():
                    if address not in snapshot:
                        raise ValueError(f"reference cannot observe CSR {address}")
                    if value != snapshot[address]:
                        diff[f"csr[{address}]"] = {"expected": hex(snapshot[address]), "actual": hex(value)}
            if "fault_access" in actual:
                from .fault import reference_fault
                access = actual["fault_access"]
                reference_access = model.fault_access(expected) if hasattr(model, "fault_access") else None
                if reference_access is None:
                    if access["completed_rmask"] or access["completed_wmask"]:
                        raise ValueError("partial fault effects are unsupported by this reference interface")
                    if getattr(model, "name", "spike") != "spike":
                        raise ValueError("reference cannot check fault-access records")
                    reference_access = reference_fault(expected, platform.xlen)
                expected["fault_access"] = reference_access
                fault_access_steps += 1
                for key, value in access.items():
                    if value != reference_access[key]:
                        diff[f"fault_access.{key}"] = {"expected": reference_access[key], "actual": value}
            # Trace quirk declared by the platform: mode reported after an xRET or trap took effect.
            # The next instruction's mode is still checked, so a wrong return mode is caught there.
            if ("mode" in diff and platform.mode_after_change
                    and (expected["trap"] or expected["insn"] in (0x30200073, 0x10200073))):
                if not hasattr(model, "mode"):
                    raise ValueError("the model cannot report its mode after a step (needed by mode_after_change)")
                if actual["mode"] == model.mode():
                    del diff["mode"]
                    quirks.append({"order": actual["order"], "quirk": "mode_after_change",
                                   "reference": expected["mode"], "core": actual["mode"]})
            if actual["intr"] != expected_handler:
                diff["intr"] = {"expected": expected_handler, "actual": actual["intr"]}
            after_trap = bool(expected["trap"])
            if actual["mem_rmask"] or actual["mem_wmask"] or expected["mem_rmask"] or expected["mem_wmask"]:
                diff.update(differences(actual, expected, ["mem_addr"]))
            for data, mask in (("mem_rdata", "mem_rmask"), ("mem_wdata", "mem_wmask")):
                a, e = masked(actual[data], actual[mask]), masked(expected[data], expected[mask])
                if a != e:
                    diff[data] = {"expected": e, "actual": a}
            sync_reason = None
            sync_mask = None   # bits of rd_wdata taken from the core; None means all of them
            initial_instret = False
            csr = csr_access(expected["insn"])
            if not expected["trap"] and expected["rd"]:
                if reset_mask:
                    sync_reason, sync_mask = "csr_reset_unknown", reset_mask
                elif counter_read(expected["insn"]):
                    # A trace from reset has a deterministic instret: compare it strictly.
                    if csr in INSTRET and platform.trace_from_reset:
                        pass
                    elif "counter" in enabled:
                        is_instret = platform.xlen == 64 and csr in INSTRET
                        if not is_instret or not instret_synced:
                            sync_reason = "counter"
                            initial_instret = is_instret
                elif mmio and not environment and expected["mem_addr"] == actual["mem_addr"] and expected["mem_rmask"]:
                    sync_reason = "mmio"
                elif csr in platform.csr_masks and "csr" in enabled:
                    sync_reason, sync_mask = "csr", platform.csr_masks[csr]
                elif csr in IRQ_INPUT_MASKS and "irq" in enabled and actual["rd"] == expected["rd"]:
                    # Only bits the core reads as 1 and the reference as 0, with evidence.
                    taken = (actual["rd_wdata"] & ~expected["rd_wdata"] & IRQ_INPUT_MASKS[csr]
                             & platform.irq_input_mask
                             & irq_evidence())
                    if taken:
                        sync_reason, sync_mask = "irq", taken
            if actual["rd"] and sync_reason != "counter":
                strict = xmask & ~sync_mask if sync_mask is not None else xmask
                if (actual["rd_wdata"] ^ expected["rd_wdata"]) & strict:
                    diff["rd_wdata"] = {"expected": expected["rd_wdata"], "actual": actual["rd_wdata"]}
            if diff:
                return mismatch(actual, expected, diff, count)
            translation_count += len(actual.get("hypervisor", {}).get("translations", []))
            if sync_mask is not None and sync_reason != "csr_reset_unknown" and actual["rd_wdata"] == expected["rd_wdata"]:
                sync_reason = None   # the masked bits agree: nothing to take from the core
            if sync_reason and not hasattr(model, "set_reg"):
                raise ValueError(f"the model cannot take the core's value at order {actual['order']} "
                                 f"({sync_reason}); use a model that synchronizes or disable this kind")
            if sync_reason:
                # No structural mismatch can be hidden by synchronization.
                if initial_instret:
                    model.sync_instret(actual["rd_wdata"], expected["rd_wdata"])
                    instret_synced = True
                model.set_reg(actual["rd"], actual["rd_wdata"])
                sync_count += 1
                entry = {"order": actual["order"], "reason": sync_reason,
                         "reference": hex(expected["rd_wdata"]), "core": hex(actual["rd_wdata"])}
                if sync_mask is not None:
                    entry.update(csr=hex(csr), mask=hex(sync_mask))
                    key = (sync_reason, csr)
                    applied_masks[key] = applied_masks.get(key, 0) | sync_mask
                if sync_reason == "csr_reset_unknown":
                    entry["source"] = "rd_wdata"
                sync_recent.append(entry)
            sync_count += len(reset_entries)
            sync_recent.extend(reset_entries)
            for entry in reset_entries:
                key = (entry["reason"], int(entry["csr"], 16))
                applied_masks[key] = applied_masks.get(key, 0) | int(entry["mask"], 16)
            if actual["rd"]:
                core_regs[actual["rd"]] = actual["rd_wdata"]
            if not expected["trap"] and expected["insn"] in XRET:
                irq_handler = 0
            previous_cycle = actual["cycle"]
            recent.append({"order": actual["order"], "cycle": actual["cycle"],
                           "pc": hex(actual["pc"]), "insn": hex(actual["insn"]),
                           "disassembly": expected["disasm"]})
            last_trap = expected if expected["trap"] and not represented_by_event else None
            count += 1
        if reference_end is not None:
            # The reference ended at its own termination (Sail stops at the HTIF tohost store;
            # a core may retire a few more instructions before its harness sees the store).
            # The rest of the trace is read, not compared, and reported.
            uncompared = 1 if actual.get("event") != "trap" else 0
            for rest in records:
                last_cycle = rest["cycle"]
                if rest.get("event") == "end":
                    ended, end_status = True, rest["status"]
                elif "event" not in rest:
                    uncompared += 1
            if ended and end_status in ("pass", "fail") and end_status != reference_end:
                raise ValueError(f"the reference ended with {reference_end} but the core trace ends with {end_status}")
            if not count:
                raise ValueError("the reference ended before the first instruction")
            return result("match", scope="until the reference's termination" + ("" if ended else " (core trace prefix)"),
                          reference_end=reference_end, uncompared_instructions=uncompared)
        if not count and not trap_events:
            raise ValueError("trace contains no instructions or traps")
        # A reference that stops at its own termination may stop exactly at the core's last
        # instruction (a core trace that ends at the tohost store): no step raised ReferenceEnded,
        # so ask it, and check its status against the core's end event.
        reference_final = model.terminated() if hasattr(model, "terminated") else None
        if reference_final is not None:
            if ended and end_status in ("pass", "fail") and end_status != reference_final:
                raise ValueError(f"the reference ended with {reference_final} but the core trace ends with {end_status}")
            return result("match", scope="complete trace" if ended else "trace prefix",
                          reference_end=reference_final, uncompared_instructions=0)
        return result("match", scope="complete trace" if ended else "trace prefix")
    finally:
        trace.close()
