"""Group native coverage points by linked Scala line and native metric."""
from collections import defaultdict


def line_metrics(points, summarize):
    grouped = defaultdict(lambda:defaultdict(dict))
    for point in points:
        mapping = point.get('scala')
        if not mapping:
            continue
        kind = point['fields'].get('t','unknown')
        for location in mapping.get('locations',[mapping]):
            key = f"{location['file']}:{location['line']}"
            grouped[key][kind][point['id']] = point
    return {line:{'metrics':{kind:summarize(list(by_id.values())) for kind,by_id in sorted(metrics.items())},
                  'statement_hit_status':'undetermined',
                  'unit':'native instrumented points linked to this line'}
            for line,metrics in sorted(grouped.items())}
