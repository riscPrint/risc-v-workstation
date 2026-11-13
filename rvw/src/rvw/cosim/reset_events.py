"""Validate project reset receipts before resetting the independent processor."""
from .reset import ResetContract, ResetSample, check_reset


class ResetReplay:
    def __init__(self, declaration, request_address=None):
        self.request_address = request_address
        self.request_cycle = None
        self.events = []
        self.next = 0
        self.last_cycle = -1
        if declaration is None:
            return
        if declaration.get('schema') != 'rvw.reset-events/1':
            raise ValueError('invalid reset declaration')
        self.events = declaration['events']
        if not self.events or [e['step'] for e in self.events] != list(range(1, len(self.events)+1)):
            raise ValueError('reset steps must be consecutive from one')
        for event in self.events:
            timing = event['schedule']
            if event['kind'] != 'reset' or event.get('preserve_ram') is not True:
                raise ValueError('reference reset requires retained RAM')
            for key, low in [('assert_clocks', 2), ('delay_clocks', 1)]:
                if type(timing[key]) is not int or not low <= timing[key] <= 1024:
                    raise ValueError('invalid reset timing')
            if not timing.get('state') or not timing.get('invalid_outputs'):
                raise ValueError('reset needs state and output expectations')

    def retire(self, record):
        if self.request_address is None or record.get('mem_addr') != self.request_address:
            return
        if record.get('mem_wmask') != 255:
            return
        if self.next < len(self.events) and record['mem_wdata'] == self.events[self.next]['step']:
            if self.request_cycle is not None:
                raise ValueError('duplicate reset request')
            self.request_cycle = record['cycle']

    def apply(self, record, model, pc):
        if self.next >= len(self.events):
            raise ValueError('unexpected reset pulse')
        event = self.events[self.next]
        if record['step'] != event['step']:
            raise ValueError('reset step differs')
        timing = event['schedule']
        samples = [ResetSample(**row) for row in record['samples']]
        if (len(samples) != timing['assert_clocks'] + 1 or
                samples[0].cycle <= self.last_cycle or samples[-1].cycle != record['cycle'] or
                any(b.cycle != a.cycle+1 for a,b in zip(samples,samples[1:]))):
            raise ValueError('reset pulse timing differs')
        if self.request_address is not None and (
                self.request_cycle is None or samples[0].cycle - 1 != self.request_cycle + timing['delay_clocks']):
            raise ValueError('reset does not follow its retired request and delay')
        contract = ResetContract({k:(v['value'],v['mask']) for k,v in timing['state'].items()},
                                 tuple(timing['invalid_outputs']))
        checked = check_reset(contract, samples)
        if checked['status'] != 'consistent':
            raise ValueError(f"reset state not checked: {checked['reason']}")
        if not hasattr(model, 'reset_preserve_ram'):
            raise ValueError('reference cannot reset with RAM retained')
        model.reset_preserve_ram(pc)
        self.last_cycle = record['cycle']
        self.request_cycle = None
        self.next += 1

    def finish(self):
        if self.next != len(self.events):
            raise ValueError('missing reset pulse receipts')
