"""Summarize conditional native attempts without promoting them to ISA proof."""


def summarize(row):
    retry = row.get('rtlil_retry', {})
    engines = [dict(engine=r.get('engine'), status=r.get('status'), reason=r.get('reason'))
               for r in retry.get('rows', [])]
    return dict(status='inconclusive', conditional_native_proof=row.get('conditional_native_proof', False),
                reason=row.get('error') or retry.get('reason') or row.get('stop_reason', 'No native proof closed'),
                engines=engines, cover=row.get('concrete_conditional_cover'))
