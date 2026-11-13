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
        # These are reviewed core cancellation semantics. The generic recognizer
        # only discovers Spinal library helpers. It cannot infer Chisel Queue flush.
        cancellation = check.startswith('stream.valid_hold:') and any(
            name in check for name in ('rpq.', 'frontend.f3.', 'frontend.f3_bpd_queue.',
                                      'frontend.f4.', 'frontend.f4_bpd_queue.',
                                      'frontend.fb.', 'io_cpu_fetchpacket',
                                      'stq_execute_queue.', 'xcpt_pc_req'))
        bound = check in {'stream.valid_hold:' + k for k in ('tile.frontend.f3.io_deq', 'tile.frontend.f3_bpd_queue.io_deq', 'tile.frontend.f4.io_deq', 'tile.frontend.f4_bpd_queue.io_deq', 'tile.lsu.stq_execute_queue.io_deq')}
        rows.append({'id': check, 'explicit_binding': bound, 'classification': 'reviewed_cancellation' if cancellation else 'reviewed_offer_or_payload_change',
                     'reason': reason, 'generic_rule_explains': False,
                     'remaining': 'Bind the exact cancellation signal and sample phase; retain strict checks outside cancellation.'
                     if cancellation else 'Keep the exact channel disposition; cancellation alone does not explain this rule.'})
    return {'schema': 'rvw.boom-stream-source-review/1', 'issue': 5,
            'historical_fired_checks': 24, 'source_dispositions': len(rows),
            'generic_cancellation_explained': 0, 'source_bound_cancellations': sum(r['explicit_binding'] for r in rows), 'native_validation': 'NOT RUN',
            'scope': 'Source review only. Chisel Queue flush and branch-mask mutation are not Spinal Stream helper calls.',
            'unmapped_historical_checks': 24 - len(rows), 'checks': rows}


if __name__ == '__main__':
    (HERE / 'stream-dispositions.json').write_text(json.dumps(dispositions(), indent=2) + '\n')
