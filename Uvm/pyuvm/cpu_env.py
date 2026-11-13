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
        self.done = False

    async def run_phase(self):
        cfg = self.config
        await monitor(cfg['dut'], cfg['bindings'], self.scoreboard,
                      retirements=cfg['retirements'], max_cycles=cfg['max_cycles'])
        self.done = True

    def check_phase(self):
        assert self.done, 'CPU monitor did not reach its expected end'
        self.scoreboard.finish(self.config['retirements'])
