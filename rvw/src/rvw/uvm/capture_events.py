"""Check C2 handler markers before feeding scalar CPU retirement checks."""


class CaptureEvents:
    def __init__(self,events,scoreboard):
        self.events,self.scoreboard=events,scoreboard
        self.pending=False
        self.ended=False

    def observe(self,row):
        if self.ended:
            raise AssertionError('CPU_CAPTURE_AFTER_END')
        event=row.get('event')
        if event=='trap':
            if self.pending:raise AssertionError('CPU_MISSING_HANDLER')
            self.events.trap(row['cause'],row['tval'])
            self.pending=True
        elif event is None:
            # C2 intr is a first-handler marker. The reference trap has already
            # been independently checked. The scalar comparator handles the
            # subsequent retirement, not the trap a second time.
            if bool(row['intr'])!=self.pending:raise AssertionError('CPU_HANDLER_MARKER')
            self.scoreboard.observe(dict(row,intr=False))
            self.pending=False
        elif event=='irq':
            if row['levels']!=0:raise ValueError('unsupported:cpu_capture_interrupt_stimulus')
        elif event=='end':
            if row['status']!='pass' or self.pending:raise AssertionError('CPU_INCOMPLETE_CAPTURE')
            self.ended=True
        else:
            raise ValueError('unsupported CPU capture event: '+str(event))

    def finish(self,count):
        if not self.ended:raise AssertionError('CPU_INCOMPLETE_CAPTURE')
        self.scoreboard.finish(count)


def require_tohost(records,address,mask):
    """A complete capture may include retirements after its completion store."""
    stores=[r for r in records if 'event' not in r and r['mem_wmask'] and r['mem_addr']==address]
    if len(stores)!=1 or stores[0]['mem_wmask']!=mask or stores[0]['mem_wdata']!=1:
        raise AssertionError('CPU_MISSING_TOHOST')
