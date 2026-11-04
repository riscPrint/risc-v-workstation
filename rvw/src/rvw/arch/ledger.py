"""Store model predictions before later RTL measurements. Never overwrite records."""
from datetime import datetime, timezone
from pathlib import Path

from . import core
from .dse import canonical


def now():
    return datetime.now(timezone.utc).isoformat()


def store(path, data):
    with Path(path).open('x') as stream:
        stream.write(canonical(data).decode() + '\n')
    return data


def predict(candidate, out, project=None):
    if project is not None:
        from rvw.common.project import load_project
        load_project(project)
    report, _, sha = core.checked_report(candidate)
    if report['engine'] != 'gem5':
        raise ValueError('prediction requires a gem5 report')
    return store(out, {'schema': 'rvw.arch-prediction/1', 'created_at': now(),
                       'candidate': str(Path(candidate).resolve()), 'candidate_sha256': sha,
                       'prediction': report, 'status': 'predicted'})


def score_prediction(prediction, rtl, out, project=None):
    raw = Path(prediction).read_bytes()
    record = core.read_json(raw)
    if record.get('schema') != 'rvw.arch-prediction/1' or record.get('status') != 'predicted':
        raise ValueError('invalid prediction record')
    created = datetime.fromisoformat(record['created_at'])
    if created.tzinfo is None or created > datetime.now(timezone.utc):
        raise ValueError('invalid prediction timestamp')
    model, _, sha = core.checked_report(record['candidate'])
    if sha != record['candidate_sha256'] or model != record['prediction']:
        raise ValueError('prediction evidence changed')
    measured, rows, _ = core.checked_report(rtl)
    # A local ordering check, not a trusted timestamp or proof of blinding.
    if measured['engine'] != 'rtl' or any(Path(r['evidence']).stat().st_mtime <= created.timestamp() for r in rows.values()):
        raise ValueError('RTL evidence must be measured after the prediction')
    report = core.compare(rtl, record['candidate'], project=project)
    return store(out, {'schema': 'rvw.arch-prediction-score/1', 'scored_at': now(),
                       'prediction_sha256': core.digest(raw), 'prediction': str(Path(prediction).resolve()),
                       'comparison': report, 'status': 'reported',
                       'limits': 'Local timestamps only. No trusted chronology or fidelity verdict.'})
