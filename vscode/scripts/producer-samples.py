"""Run current Python producers on small inputs. This is parser evidence, not RTL evidence."""
import json
from pathlib import Path
import tempfile
import sqlite3

from rvw.agent.guide import load
from rvw.lint.cli import report as lint_report
from rvw.lint.sarif import convert as sarif
from rvw.cov import code
from rvw.cov.functional import functional
from rvw.mcp.envelope import envelope
from rvw.plan import VPlan
from rvw.results.schema import Verdict


def produce(root):
    root = Path(root)
    trace = root / 'trace.jsonl'
    trace.write_text('\n'.join(json.dumps(r) for r in [
        {'schema': 'rvw.rvfi/1', 'xlen': 32, 'isa': 'rv32im'},
        {'order': 0, 'insn': '0x00100093', 'mode': 3, 'rd': 1,
         'rs1_rdata': '0x0', 'rs2_rdata': '0x0'},
    ]) + '\n')
    coverage = functional([trace])
    (root / 'functional.json').write_text(json.dumps(coverage))
    (root / 'Unit.v').write_text('// Unit.scala:3\nassign x=y;\n')
    raw = root / 'coverage.dat'
    raw.write_text("# SystemC::Coverage-3\nC '\x01f\x02Unit.v\x01l\x021\x01page\x02v_line/Unit\x01h\x02TOP.unit' 1\n")
    merged = code.merge([f'sample={raw}'], root)
    plan = root / 'plan.json'
    plan.write_text(json.dumps({'schema': 'rvw.vplan/1',
        'requirements': {'ADD': 'Observe add.'},
        'features': [{'id': 'add', 'requirements': ['ADD'],
                      'coverage': [{'path': 'functional.json', 'groups': ['class_mode']}]}]}))
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
    return {'lint': lint, 'sarif': sarif(lint), 'guide': load(), 'functional': coverage, 'coverage': merged,
            'coverage_report': code.report(merged), 'plan': VPlan(plan).status(),
            'gates': [envelope(Verdict(verdict=v, tests=t).to_dict()) for v, t in
                      [('accept', 'pass'), ('reject', 'fail'), ('inconclusive', 'incomplete')]]}


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='rvw-vscode-producers-') as directory:
        print(json.dumps(produce(directory)))
