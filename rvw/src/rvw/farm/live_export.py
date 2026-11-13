"""Standalone export of the owner-scoped live dashboard and its C5 summaries."""
import json
from pathlib import Path
from .http import PAGE
from .live import snapshot, bundle


def export(queue, owner, out):
    view = snapshot(queue, owner)
    recorded = {'/snapshot': view}
    from urllib.parse import quote
    for cluster in view['failure_clusters']:
        for relative in cluster['bundles']:
            recorded['/bundle/' + cluster['job_id'] + '?path=' + quote(relative, safe="~()*!.'-")] = bundle(
                queue, owner, cluster['job_id'], relative)
    payload = json.dumps(recorded).replace('<', '\\u003c')
    lines = PAGE.splitlines()
    lines = ["const recorded=" + payload + "; async function get(path){if(!(path in recorded))throw Error('No recorded evidence');return recorded[path]}"
             if line.startswith('async function get(path)') else line for line in lines]
    page = '\n'.join(lines).replace('<label>Token <input id="token" type="password"></label>', '')
    page = page.replace('Regression service', 'Recorded regression service')
    page = page.replace('</script>', "byId('refresh').click();\n</script>")
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page)
    return dict(out=str(path), runs=len(view['runs']), clusters=len(view['failure_clusters']),
                evidence='recorded', gate_acceptance='not_inferred')
