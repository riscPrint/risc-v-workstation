"""Check an adapter identity document (rvw.adapter-capture/2) against the selected source."""
import json
import re

SCHEMA = 'rvw.adapter-capture/2'
_PATH = re.compile(r'[A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)*')


def accept(text, source):
    """Return the parsed document. `source` is the runner's C1 source descriptor.

    The adapter may add source keys (tools_rev, tools_dirty); the selected ones must agree.
    Each `result_claims` entry (a dotted C1 path) must later hold in every C1 result.
    """
    value = json.loads(text)
    json.dumps(value, allow_nan=False)
    if not isinstance(value, dict) or value.get('schema') != SCHEMA or value.get('complete') is not True:
        raise ValueError('adapter capture is incomplete or has another schema')
    reported = value.get('source')
    if not isinstance(reported, dict) or any(
            json.dumps(reported.get(key), sort_keys=True) != json.dumps(wanted, sort_keys=True)
            for key, wanted in source.items()):
        raise ValueError('adapter capture describes another source')
    claims = value.get('result_claims')
    if not isinstance(claims, dict) or not claims:
        raise ValueError('adapter capture has no C1 claims')
    if any(not _PATH.fullmatch(path) for path in claims):
        raise ValueError('adapter capture has an invalid C1 field path')
    return value


def claim_error(claims, result):
    """Why a C1 result (a dict) does not carry the claimed values, or None."""
    for path, value in claims.items():
        observed = result
        for part in path.split('.'):
            if not isinstance(observed, dict) or part not in observed:
                return f"C1 adapter capture claim {path} is missing"
            observed = observed[part]
        if json.dumps(observed, sort_keys=True) != json.dumps(value, sort_keys=True):
            return f"C1 adapter capture claim {path} differs from the adapter identity"
    return None
