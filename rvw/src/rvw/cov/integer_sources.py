"""Register-bank facts for ratified scalar integer opcode source families.

These families use integer rs1/rs2 fields. FP and vector families need explicit
forms because their encoded source fields can name another register bank.
"""
FAMILIES = frozenset(('i','m','a','zicsr','zba','zbb','zbc','zbs','zicond'))


def integer_source(item, argument):
    if argument not in ('rs1','rs2') or argument not in item['args']:
        return False
    name = item['source'].rsplit('/',1)[-1]
    prefix, separator, family = name.partition('_')
    return bool(separator and prefix in ('rv','rv32','rv64') and family in FAMILIES)
