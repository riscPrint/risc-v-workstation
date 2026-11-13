"""Canonical MCP vocabulary with accepted, explicit compatibility aliases."""
from copy import deepcopy
from dataclasses import replace
from functools import wraps

from .spec import ToolError


def with_aliases(tool, **aliases):
    """Map canonical names to handler names without changing provider Python APIs."""
    schema = deepcopy(tool.input_schema)
    properties = schema['properties']
    for canonical, old in aliases.items():
        if canonical in properties:
            raise ValueError('canonical argument already exists: ' + canonical)
        properties[canonical] = deepcopy(properties[old])
        properties[old] = {**properties[old], 'deprecated': True, 'x-alias-for': canonical}
        if old in schema.get('required', []):
            schema['required'].remove(old)
            schema.setdefault('allOf', []).append({'anyOf': [
                {'required': [canonical]}, {'required': [old]}]})

    @wraps(tool.handler)
    def call(*args, **arguments):
        for canonical, old in aliases.items():
            if canonical in arguments:
                if old in arguments:
                    raise ToolError(f'Use only one of {canonical} or {old}', code='invalid_arguments')
                arguments[old] = arguments.pop(canonical)
        return tool.handler(*args, **arguments)

    return replace(tool, input_schema=schema, handler=call)
