"""Early diagnostics for reset forms outside the security transform."""


class UnsupportedSecurity(ValueError):
    pass


RESET_HINT = ('Move assertions from an asynchronous-reset process to a rising-edge '
              'process guarded by sampled reset. For IFT, use a public rising-edge '
              'clock and SYNC reset in the shared project Elaboration.config, then '
              'rebuild RTL and SpinalDB. Do not remove the assertions or tie state.')


def check_properties(module):
    kinds = {c['type'] for c in module.get('cells', {}).values()}
    properties = kinds & {'$assert', '$assume', '$cover', '$check'}
    asynchronous = {k for k in kinds if k.startswith(('$adff', '$aldff', '$_DFF_PP', '$_DFF_PN'))}
    if properties and asynchronous:
        raise UnsupportedSecurity('DUT properties with asynchronous-reset state are unsupported by the security transform. ' + RESET_HINT)


def mapping_failure(log):
    errors = [line for line in log.splitlines() if line.startswith('ERROR:')]
    for line in errors:
        if 'Multiple edge sensitive events' in line or ('reset' in line.lower() and 'non-constant' in line):
            raise UnsupportedSecurity(line + ' ' + RESET_HINT)
