"""CPU CSR qualification through project instruction-execution callbacks.

Use the checks worker's catalog and semantic oracle. Never infer reset values
or write safety from an address or a CSR name.
"""
import random
from rvw.formal.csr import load, step


class CsrQualification:
    def __init__(self, catalog_selection, *, seed=1):
        self.model = load(catalog_selection)
        self.random = random.Random(seed)
        self.checks = 0
        self.coverage = set()

    async def run(self, execute, *, random_writes=8):
        """execute(address, transaction) returns trap and pre-write read_data.

        The project must execute an architectural CSR instruction with the
        requested access and privilege. A bus register write is not sufficient.
        Each call must finish before the next call starts. Reset once before
        this sequence. Unknown-reset safe CSRs receive an explicit write first.
        """
        if type(random_writes) is not int or random_writes < 0:
            raise ValueError('random_writes must be a nonnegative integer')
        width = self.model['xlen']
        mask = (1 << width)-1
        for csr in self.model['csrs']:
            state = csr['reset']
            operations = []
            if not csr.get('reset_known', True):
                if not csr.get('assembly_safe', False):
                    raise ValueError('unknown reset requires a project-safe initialization')
                operations.append(dict(read=False, write=True, data=state, privilege=3))
            operations.append(dict(read=True, write=False, data=0, privilege=3))
            if csr.get('assembly_safe', False):
                values = [0, mask] + [1 << bit for bit in range(width)]
                values += [self.random.getrandbits(width) for _ in range(random_writes)]
                values += [csr['reset']]
                for value in values:
                    operations.append(dict(read=False, write=True, data=value, privilege=3))
                    operations.append(dict(read=True, write=False, data=0, privilege=3))
            for index, transaction in enumerate(operations):
                trap, next_state = step(csr, state, transaction, width)
                reply = await execute(csr['address'], dict(transaction))
                if type(reply.get('trap')) is not bool or reply['trap'] != trap:
                    raise AssertionError('CSR_TRAP:'+csr['name'])
                # Initialization has no read, so no unknown reset is compared.
                if transaction['read'] and not trap and reply.get('read_data') != state:
                    raise AssertionError('CSR_DATA:'+csr['name'])
                state = next_state
                self.checks += 1
                self.coverage.add((csr['name'], 'write' if transaction['write'] else 'read', trap))
        if not self.checks:
            raise AssertionError('no CSR qualification checks')
        return dict(checks=self.checks, coverage=sorted(self.coverage))
