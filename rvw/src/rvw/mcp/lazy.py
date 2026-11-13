"""Resolve a declared tool without importing unrelated providers."""
from importlib import import_module


def resolve(provider, name):
    for spec in import_module(provider).mcp_tools():
        if spec.name == name:
            return spec
    raise ValueError(f'tool {name} disappeared from {provider}')


def tool_handler(provider, name, wants_job=False):
    target = None

    def get():
        nonlocal target
        if target is None:
            target = resolve(provider, name).handler
        return target

    if wants_job:
        def call(job, **arguments):
            return get()(job=job, **arguments)
    else:
        def call(**arguments):
            return get()(**arguments)
    call.__module__ = provider
    return call


def functions(module):
    """A namespace of deferred functions, for declarations that refer to handlers.

    Use this only for function attributes. Keep constants in a light module.
    """
    class Functions:
        def __getattr__(self, name):
            target = None
            def call(*args, **kwargs):
                nonlocal target
                if target is None:
                    target = getattr(import_module(module), name)
                return target(*args, **kwargs)
            call.__module__ = module
            call.__name__ = name
            setattr(self, name, call)
            return call
    return Functions()
