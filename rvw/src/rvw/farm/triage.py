"""Evidence-backed failure clusters. Grouping never waives a failure."""
import hashlib
import json
import re
from pathlib import Path
from .recorded_results import recorded_results as find_results
from rvw.regress.compare import compare, with_assertion_identity
from rvw.regress.known import load_known


def triage(root, baseline=None, known=None, bundles=None):
    suites = find_results(Path(root))
    known_entries = load_known(Path(known)) if known else []
    clusters = {}
    revisions = set()
    for suite in suites:
        revisions.add(suite.source.get('core_rev_full', suite.source.get('core_rev', 'unknown')))
        for original in suite.tests:
            test = with_assertion_identity(original)
            if test.status == 'pass' and test.conclusive:
                continue
            details = test.extra.get('details', {})
            details = details if isinstance(details, dict) else {}
            mismatch = details.get('first_mismatch', {})
            if isinstance(mismatch, dict) and mismatch.get('pc') is not None and mismatch.get('instruction') is not None:
                signature = 'mismatch:' + json.dumps([mismatch['pc'], mismatch['instruction']], sort_keys=True)
            elif details.get('trap_cause') is not None:
                signature = 'trap:' + str(details['trap_cause'])
            else:
                signature = test.signature or test.status
            category = 'dut_failure' if test.conclusive else 'infrastructure_or_incomplete'
            # Config and core boundaries prevent accidental cross-design waivers.
            key = json.dumps([suite.core, suite.config, category, signature])
            cluster = clusters.setdefault(key, dict(id=hashlib.sha256(key.encode()).hexdigest()[:20],
                core=suite.core, config=suite.config, signature=signature, category=category,
                members=[], known=[], bundle=None))
            run = Path(test.run) if test.run else None
            if run and not run.is_absolute():
                run = (suite.path.parent if suite.path and suite.path.is_file() else suite.path or Path(root)) / run
            cluster['members'].append(dict(suite=suite.suite, test=test.id, seed=test.seed, status=test.status,
                run=str(run) if run else None, revision=suite.source, signature=test.signature))
            for entry in known_entries:
                if entry.matches(suite.suite, test.id, test.signature, suite.config):
                    cluster['known'].append(dict(reason=entry.reason, recorded_at_rev=entry.recorded_at_rev,
                                                  test=test.id, config=entry.config))
    base_suites = find_results(Path(baseline)) if baseline else []
    base_revisions = {s.source.get('core_rev_full', s.source.get('core_rev', 'unknown')) for s in base_suites}
    for cluster in clusters.values():
        candidates = {m['revision'].get('core_rev_full', m['revision'].get('core_rev', 'unknown')) for m in cluster['members']}
        cluster['commit_ranges'] = sorted({b + '..' + c for b in base_revisions for c in candidates
                                          if re.fullmatch('[0-9a-f]{40}', b) and re.fullmatch('[0-9a-f]{40}', c)})
        representative = next((m['run'] for m in cluster['members'] if m['run']), None)
        cluster['representative'] = representative
        if bundles and representative:
            from rvw.bundle.cli import execute_json
            try:
                cluster['bundle'] = execute_json(representative, out=str(Path(bundles) / cluster['id']),
                                                  no_rerun=True, no_spinaltrace=True)
            except (ValueError, OSError, RuntimeError) as exc:
                cluster['bundle_error'] = str(exc)
    diff = compare(base_suites, suites, known_entries).to_dict() if baseline else None
    return dict(schema='rvw.failure-clusters/1', clusters=list(clusters.values()), revisions=sorted(revisions),
                baseline=str(baseline) if baseline else None, diff=diff,
                status='no_checks' if not suites else 'reported', failures_waived=False)
