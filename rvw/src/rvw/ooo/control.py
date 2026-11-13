"""Serialize non-trapping architectural control instructions in timing only."""
SERIAL = {'csr', 'fence', 'system'}


def supported(decoded):
    return decoded.cls != 'system' or decoded.mnemonic in ('mret', 'sret')
