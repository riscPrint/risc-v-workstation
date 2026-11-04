"""Periodic clock levels in global samples, independent of async state support."""
import math


def parse(items, clocks):
    schedules = {}
    for item in items or []:
        name, sep, bits = item.partition('=')
        if not sep or name not in clocks or name in schedules:
            raise ValueError('clock schedules need unique declared PORT=BITS entries')
        if not 2 <= len(bits) <= 256 or set(bits) != {'0', '1'}:
            raise ValueError('clock schedule must contain 2..256 binary samples, with both levels')
        schedules[name] = bits
    if schedules and set(schedules) != set(clocks):
        raise ValueError('clock schedules must declare every event clock, including the primary clock')
    if schedules and math.lcm(*(len(x) for x in schedules.values())) > 4096:
        raise ValueError('joint clock schedule period must not exceed 4096 samples')
    return schedules


def constrain(wrapper, schedules):
    if not schedules:
        return wrapper
    period = math.lcm(*(len(x) for x in schedules.values()))
    width = max(1, (period - 1).bit_length())
    lines = [f'reg [{width-1}:0] rvw_schedule_sample = 0;',
             f'always @($global_clock) rvw_schedule_sample <= '
             f'rvw_schedule_sample == {period-1} ? 0 : rvw_schedule_sample + 1;']
    for i, (clock, bits) in enumerate(sorted(schedules.items())):
        # The user writes sample zero first; Verilog literal bit zero is on the right.
        lines += [f"wire [{len(bits)-1}:0] rvw_schedule_{i} = {len(bits)}'b{bits[::-1]};",
                  f'always @* assume ({clock} == rvw_schedule_{i}[rvw_schedule_sample % {len(bits)}]);']
    return wrapper.rsplit('endmodule', 1)[0] + '\n'.join(lines) + '\nendmodule\n'
