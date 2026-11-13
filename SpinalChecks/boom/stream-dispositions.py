#!/usr/bin/env python3
"""Regenerate source-only BOOM stream dispositions. No elaboration or simulation."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def dispositions():
    rows = []
    historic = (HERE / 'streams-reviewed.txt').read_text().splitlines()
    historic += [line for line in (HERE / 'waivers.txt').read_text().splitlines()
                 if line.startswith(('stream.payload_stable:io_mem_a ', 'stream.payload_stable:arbiter.io_ups_0_a ', 'stream.payload_stable:arbiter.a_arbiter.io_inputs_0 '))]
    for line in historic:
        if not line.startswith('stream.'):
            continue
        check, reason = line.split(None, 1)
        bound = check in {'stream.valid_hold:' + k for k in ('tile.frontend.f3.io_deq', 'tile.frontend.f3_bpd_queue.io_deq', 'tile.frontend.f4.io_deq', 'tile.frontend.f4_bpd_queue.io_deq', 'tile.lsu.stq_execute_queue.io_deq')}
        path = check.split(':', 1)[1]
        payload = check.startswith('stream.payload_stable:')
        condition, sample = None, None
        if bound:
            mechanism = 'registered_queue_flush'
            condition, sample = 'io_flush', 'previous'
        elif 'rpq.' in path:
            if payload:
                mechanism = 'live_branch_mask_update'
            else:
                mechanism = 'registered_branch_kill_or_flush'
                condition = 'IsKilledByBranch(io.brupdate, False, head_uop) || (io.flush && flush_fn(head_uop))'
                sample = 'previous; select out_uop or indexed head uop after elaboration'
        elif path in ('tile.frontend.fb.io_deq', 'tile.frontend.io_cpu_fetchpacket'):
            mechanism = 'registered_fetch_buffer_clear'
            condition, sample = 'FetchBuffer.io.clear', 'previous'
        elif path == 'io_mem_a' or path.startswith('arbiter.') or path.endswith('mshrs.io_mem_acquire'):
            mechanism = 'tilelink_pre_acceptance_offer'
        else:
            mechanism = 'per_cycle_offer'
        if bound:
            remaining = 'Validate the existing binding name and timing in a BOOM elaboration. No native result is claimed.'
        elif condition:
            remaining = 'Create an exact cancellation observation from the source guard. Verify its name and sample phase before changing channel settings.'
        elif mechanism == 'live_branch_mask_update':
            remaining = 'Separate immutable payload fields from the live branch mask. A kill-only condition does not permit every legal mask update.'
        else:
            remaining = 'Keep the exact offer semantics. A registered-flush condition alone does not describe every allowed offer change.'
        rows.append({'id': check, 'explicit_binding': bound,
                     'classification': 'reviewed_cancellation' if condition else 'reviewed_offer_or_payload_change',
                     'reason': reason, 'generic_rule_explains': False,
                     'mechanism': mechanism, 'cancel_condition': condition, 'cancel_sample': sample,
                     'binding_validation': 'NOT RUN', 'remaining': remaining})
    return {'schema': 'rvw.boom-stream-source-review/1', 'issue': 5,
            'historical_fired_checks': 24, 'source_dispositions': len(rows),
            'generic_cancellation_explained': 0, 'source_bound_cancellations': sum(r['explicit_binding'] for r in rows), 'native_validation': 'NOT RUN',
            'scope': 'Source review only. Chisel Queue flush and branch-mask mutation are not Spinal Stream helper calls.',
            'unmapped_historical_checks': 24 - len(rows), 'checks': rows}


if __name__ == '__main__':
    (HERE / 'stream-dispositions.json').write_text(json.dumps(dispositions(), indent=2) + '\n')
