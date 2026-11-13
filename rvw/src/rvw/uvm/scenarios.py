"""Bounded SoC virtual scenarios using project-owned execution callbacks."""
import random


class SocScenarios:
    def __init__(self, backend, *, seed=1):
        self.backend=backend
        self.random=random.Random(seed)

    @staticmethod
    def checked(report):
        if not isinstance(report,dict) or type(report.get('checks')) is not int or report['checks']<1:
            raise AssertionError('SOC_SCENARIO_NO_CHECKS')
        return report

    async def boot(self):
        await self.backend.reset()
        # The backend must wait for checked program completion, not a PC prefix.
        return self.checked(await self.backend.boot())

    async def interrupt_storm(self, causes, *, count=16, max_gap=8):
        causes=tuple(causes)
        if not causes or count<1 or max_gap<1 or any(type(c) is not int or not 0<=c<64 for c in causes):
            raise ValueError('bounded interrupt causes, count and gap required')
        reports=[]
        try:
            for _ in range(count):
                cause=self.random.choice(causes)
                await self.backend.wait_cycles(self.random.randrange(1,max_gap+1))
                await self.backend.irq(1<<cause)
                report=self.checked(await self.backend.wait_interrupt(cause))
                if report.get('cause')!=cause: raise AssertionError('SOC_SCENARIO_INTERRUPT_CAUSE')
                reports.append(report)
                await self.backend.irq(0)
        finally:
            await self.backend.irq(0)
        return dict(checks=sum(r['checks'] for r in reports),interrupts=len(reports))

    async def bus_error(self, request):
        try:
            await self.backend.inject_bus_error(True)
            report=self.checked(await self.backend.transfer(request))
            if report.get('error') is not True: raise AssertionError('SOC_SCENARIO_MISSING_BUS_ERROR')
            return report
        finally:
            await self.backend.inject_bus_error(False)

    async def reset_during_traffic(self, *, delay=3):
        if type(delay) is not int or delay<1: raise ValueError('positive reset delay required')
        handle=await self.backend.start_traffic()
        try:
            await self.backend.wait_cycles(delay)
            if not await self.backend.traffic_pending(handle):
                raise AssertionError('SOC_SCENARIO_NO_PENDING_TRAFFIC')
            await self.backend.reset()
            # Project reset must reset the DUT, agents and expected model together.
            report=self.checked(await self.backend.check_reset(handle))
            if report.get('aborted') is not True: raise AssertionError('SOC_SCENARIO_MISSING_ABORT')
            return report
        finally:
            await self.backend.stop_traffic(handle)
