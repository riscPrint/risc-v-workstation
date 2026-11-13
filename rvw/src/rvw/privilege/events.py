"""Mailbox stimulus support for project adapters.

The adapter resolves ELF symbols and supplies memory and device callbacks. A
request is acknowledged only after its callback completes. No RTL names live here.
"""


class MailboxDriver:
    def __init__(self, events):
        self.events = list(events)
        if any(e.get('kind')=='wfi-wake' for e in self.events):
            raise ValueError('WFI clock-stop input requires StopWakeDriver')
        if any(e.get('phase_gate') for e in self.events):
            raise ValueError('phased reset requires PhaseDriver')
        steps = [e['step'] for e in events]
        if steps != sorted(set(steps)) or any(type(s) is not int or s <= 0 for s in steps):
            raise ValueError('mailbox steps must be positive and strictly increasing')
        self.done = []

    def service(self, request, drive, acknowledge, *, pc=None, symbols=None):
        if len(self.done) == len(self.events):
            return False
        event = self.events[len(self.done)]
        if request != event['step']:
            return False
        if event.get('when_pc') and (symbols is None or pc != symbols.get(event['when_pc'])):
            return False
        drive(event)
        acknowledge(event['step'])
        self.done.append(event)
        return True

    @property
    def complete(self):
        return len(self.done) == len(self.events)


def reset_check(config, observations):
    from rvw.cosim.reset import ResetContract, ResetSample, check_reset
    contract = ResetContract({k: (v['value'], v['mask']) for k, v in config['state'].items()},
                             tuple(config['invalid_outputs']))
    expected = config['pulses']
    if not observations or len(observations) != expected:
        return {'status': 'inconclusive', 'reason': 'missing reset pulse observations'}
    results = []
    for pulse in observations:
        result = check_reset(contract, [ResetSample(**s) for s in pulse])
        results.append(result)
    status = ('fail' if any(r['status'] == 'mismatch' for r in results) else
              'pass' if all(r['status'] == 'consistent' for r in results) else 'inconclusive')
    return {'status': status, 'pulses': results}


def mailbox(step):
    return f''' la t0, stimulus_step
 li t1, {step}
 sd t1, 0(t0)
 la t0, stimulus_ack
1: ld t1, 0(t0)
 li t2, {step}
 bne t1, t2, 1b
'''
