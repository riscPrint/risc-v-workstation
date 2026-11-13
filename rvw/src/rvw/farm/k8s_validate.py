"""Offline Job shape validation. This does not contact Kubernetes admission."""
import hashlib
import json
from pathlib import Path
from jsonschema import Draft4Validator


def validate(document, openapi):
    if not openapi:
        raise ValueError('offline validation requires a local Kubernetes OpenAPI v2 JSON')
    data = Path(openapi).read_bytes()
    definitions = json.loads(data)['definitions']
    name = 'io.k8s.api.batch.v1.Job'
    if name not in definitions:
        raise ValueError('OpenAPI document has no batch/v1 Job definition')
    validator = Draft4Validator({'$ref': '#/definitions/' + name, 'definitions': definitions})
    errors = []
    if document.get('apiVersion') != 'v1' or document.get('kind') != 'List' or not document.get('items'):
        errors.append('expected a nonempty v1 List')
    for index, job in enumerate(document.get('items', [])):
        if job.get('apiVersion') != 'batch/v1' or job.get('kind') != 'Job':
            errors.append(f'items/{index}: expected batch/v1 Job')
        for error in validator.iter_errors(job):
            path = '/'.join(str(p) for p in error.absolute_path)
            errors.append(f'items/{index}/{path}: {error.message}')
    return dict(schema='rvw.k8s-offline-validation/1', status='valid' if not errors else 'invalid',
                jobs=len(document.get('items', [])), openapi_sha256=hashlib.sha256(data).hexdigest(),
                manifest_sha256=hashlib.sha256(json.dumps(document, sort_keys=True).encode()).hexdigest(),
                errors=errors, cluster_execution='not_run', admission='not_run')
