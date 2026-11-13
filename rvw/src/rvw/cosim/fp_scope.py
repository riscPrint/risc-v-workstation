"""Explicit scope for comparisons without floating-point state evidence."""
import re


def apply_scope(status, extra, platform, fp_observed):
    parts = re.sub(r'^rv(?:32|64)', '', platform.isa.lower()).split('_')
    needs_fp = any(any(letter in re.sub(r'\d+(?:p\d+)?', '', part) for letter in 'fdg')
                   for part in parts if not part.startswith(('z', 's', 'x')))
    if (needs_fp or platform.require_fp_state) and not fp_observed:
        extra['comparison_scope'] = extra.get('scope')
        extra['scope'] = 'no_fp_state'
        if status == 'match' and platform.require_fp_state:
            extra['cause'] = 'fp_state_not_observed'
            return 'inconclusive'
    return status
