"""Project-owned verification plan rollups."""
__all__ = ['VPlan']


def __getattr__(name):
    if name == 'VPlan':
        from .model import VPlan
        return VPlan
    raise AttributeError(name)
