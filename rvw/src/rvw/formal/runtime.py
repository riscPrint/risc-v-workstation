"""Record host pressure without treating a timeout as a capacity result."""
import os


def load_average():
    try:
        return list(os.getloadavg())
    except (AttributeError, OSError):
        return None


def timeout_details(wall_s, timeout_s, load_start, *, engine=None):
    next_timeout = max(1800, timeout_s * 2)
    action = f'Retry the same check and depth with --timeout {next_timeout:g}.'
    if load_start and load_start[0] > 20:
        action = 'Retry when the one-minute load is at most 20. Use at most two engines. ' + action
    if engine:
        action += f' Current engine: {engine}.'
    return dict(wall_s=wall_s, timeout_s=timeout_s, load_average_start=load_start,
                load_average_end=load_average(), next_setting=action,
                capacity_classification='unresolved')
