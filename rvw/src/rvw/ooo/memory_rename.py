"""Oracle store-data renaming bound. Normal loads still verify and retire."""


def validate(policy, memory_policy):
    if not isinstance(policy, dict) or (policy and policy != {'mode': 'oracle_store_data'}):
        raise ValueError('memory_rename must select mode oracle_store_data')
    if policy and memory_policy == 'speculate':
        raise ValueError('oracle memory rename does not support dependence replay')


def source(load, rob):
    """Use the youngest overlapping store, only for exact integer word coverage.

    The traced address is an oracle at rename. No learned prediction is claimed.
    A partial overlap must block lookup of an older full overlap.
    """
    if load.kind != 'load' or load.dest is None or load.dest >= 32 or load.size not in (4, 8):
        return None
    # A signed or zero-extending smaller load cannot alias a full-width register.
    if load.mnemonic not in ('ld', 'lw'):
        return None
    for entry in reversed(rob):
        store = entry.insn
        if store.kind in ('fence', 'csr', 'system'):
            return None
        if store.kind != 'store':
            continue
        if store.address < load.address + load.size and load.address < store.address + store.size:
            if (store.address == load.address and store.size == load.size and
                store.mnemonic in ('sd', 'sw') and len(store.sources) == 2 and
                store.sources[1] < 32):
                # LW sign extension and SW truncation need value checks on RV64.
                # Limit to LD/SD; RV32 word support needs explicit XLEN metadata.
                return entry if load.mnemonic == 'ld' and store.mnemonic == 'sd' else None
            return None
    return None
