"""Canonical verification verdicts and conservative aggregation."""
VERDICTS = {'pass', 'fail', 'inconclusive', 'no_checks', 'unsupported', 'not_installed', 'error'}


def producer_verdict(data):
    """Read an explicit verdict. Command completion is not verification."""
    if data.get('inconclusive'):
        return 'inconclusive'
    value = data.get('verdict', data.get('status'))
    return value if value in VERDICTS else 'inconclusive'


def weakest_verdict(verdicts):
    values = {v if v in VERDICTS else 'inconclusive' for v in verdicts}
    if not values:
        return 'no_checks'
    # A known failure remains a failure. Other blockers also prevent pass.
    for verdict in ('fail', 'error', 'not_installed', 'unsupported', 'inconclusive', 'no_checks', 'pass'):
        if verdict in values:
            return verdict
