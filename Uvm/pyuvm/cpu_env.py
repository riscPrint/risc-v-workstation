"""Optional pyuvm live CPU environment with project-owned pin adapters."""
import pyuvm
from rvw.sim.cpu_env import CpuMemory, CpuScoreboard, monitor


class LiveCpuEnvironment(pyuvm.uvm_env):
    def build_phase(self):
        self.config = pyuvm.ConfigDB().get(self, '', 'cpu')
        cfg = self.config
        self.memory = CpuMemory(cfg['memory_base'], cfg['memory_size'],
                                seed=cfg.get('seed', 1), max_wait=cfg.get('max_wait', 3),
                                fetch_errors=cfg.get('fetch_errors', ()))
        self.memory.preload(cfg['elf'])
        self.scoreboard = CpuScoreboard(cfg['reference'])
        self.virtual_sequencer = pyuvm.uvm_sequencer('virtual_sequencer',self)
        self.virtual_sequencer.memory = self.memory
        self.virtual_sequencer.scoreboard = self.scoreboard
        self.virtual_sequencer.controls = cfg.get('controls')
        self.done = False

    async def run_phase(self):
        cfg = self.config
        await monitor(cfg['dut'], cfg['bindings'], self.scoreboard,
                      retirements=cfg['retirements'], max_cycles=cfg['max_cycles'])
        self.done = True

    def check_phase(self):
        assert self.done, 'CPU monitor did not reach its expected end'
        self.scoreboard.finish(self.config['retirements'])


class RandomControlSequence(pyuvm.uvm_sequence):
    def __init__(self, name='random_controls', *, count=16, allowed_irqs=0, max_gap=8):
        super().__init__(name)
        self.count, self.allowed_irqs, self.max_gap = count, allowed_irqs, max_gap

    async def body(self):
        if self.sequencer.controls is None:
            raise ValueError('project CPU control callbacks required')
        await self.sequencer.controls.random_requests(self.count,self.allowed_irqs,self.max_gap)


class CsrQualificationSequence(pyuvm.uvm_sequence):
    """Run catalog-derived CSR checks through a project CPU executor."""
    def __init__(self, selection, execute, name='csr_qualification', *, seed=1, random_writes=8):
        super().__init__(name)
        self.selection, self.execute = selection, execute
        self.seed, self.random_writes = seed, random_writes

    async def body(self):
        from rvw.uvm.csr_sequence import CsrQualification
        self.qualification = CsrQualification(self.selection, seed=self.seed)
        self.report = await self.qualification.run(self.execute, random_writes=self.random_writes)
