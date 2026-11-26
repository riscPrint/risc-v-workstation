"""Run current Python producers on small inputs. This is parser evidence, not RTL evidence."""
import json
from pathlib import Path
import tempfile
import sqlite3

from rvw.agent.guide import load
from rvw.lint.cli import report as lint_report
from rvw.lint.sarif import convert as sarif
from rvw.csim.study import run as csim_run
from rvw.mcp.envelope import envelope
from rvw.results.schema import Verdict, RunResult, SuiteResults, TestEntry


def produce(root):
    root = Path(root)
    trace = root / 'trace.jsonl'
    trace.write_text('\n'.join(json.dumps(r) for r in [
        {'schema': 'rvw.rvfi/1', 'xlen': 32, 'isa': 'rv32im'},
        {'order': 0, 'insn': '0x00100093', 'mode': 3, 'rd': 1,
         'rs1_rdata': '0x0', 'rs2_rdata': '0x0'},
    ]) + '\n')
    repo = Path(__file__).resolve().parents[2]
    database = root / 'captured.db'
    connection = sqlite3.connect(database)
    sql = (repo / 'rvw/tests/data/cluster.sql').read_text()
    connection.executescript(sql.replace('@REPO@', str(repo)).replace('@TMP@', str(root)))
    meta = dict(connection.execute('SELECT key,value FROM meta'))
    connection.close()
    settings = root / 'lint.json'
    settings.write_text(json.dumps({'schema': 'rvw.lint-settings/1',
        'config': meta.get('config', 'captured'), 'top': meta['toplevel'],
        'db': str(database), 'backends': ['rules', 'structural']}))
    lint = lint_report(settings)
    suite = SuiteResults(run_id='parser-test', suite='small', core='external',
        config='small', created='2026-01-01T00:00:00Z',
        tests=[TestEntry(id='pass', status='pass'), TestEntry(id='planted', status='fail')])
    return {'run': RunResult(status='fail', core='external', config='small',
                            fail_code=3, artifacts={'rvfi_trace': 'trace.jsonl'}).to_dict(),
            'suite': suite.to_dict(), 'suite_counts': suite.counts(), 'csim_study': csim_run({'branch': {'model': 'bimodal'}}, []), 'lint': lint, 'sarif': sarif(lint), 'guide': load(),
            'gates': [envelope(Verdict(verdict=v, tests=t).to_dict()) for v, t in
                      [('accept', 'pass'), ('reject', 'fail'), ('inconclusive', 'incomplete')]]}


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='rvw-vscode-producers-') as directory:
        print(json.dumps(produce(directory)))
