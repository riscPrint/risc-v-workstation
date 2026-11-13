from rvw.cosim.adjudicate import adjudicate


def result(status='match', index=0, value='0x1'):
    row = dict(status=status, instructions=3 if status == 'match' else index, trace_complete=True,
               reproduction=dict(elf_sha256='e', trace_sha256='t', platform_sha256='p'))
    if status == 'mismatch':
        row['mismatch'] = dict(instruction_index=index, differences=dict(rd_wdata=dict(expected=value, actual='0x0')))
    return row


def test_both_match_and_common_input():
    reports = dict(spike=result(), sail=result())
    assert adjudicate(reports)['status'] == 'match'
    reports['sail']['reproduction']['trace_sha256'] = 'other'
    assert adjudicate(reports)['status'] == 'inconclusive'


def test_dut_matches_one_reference():
    reports = dict(spike=result('mismatch'), sail=result())
    report = adjudicate(reports)
    assert report['status'] == 'disagreement'
    assert report['dut_matches_at_boundary'] == ['sail']
    assert report['references'] == reports


def test_both_reject_same_or_different_result():
    reports = dict(spike=result('mismatch'), sail=result('mismatch'))
    assert adjudicate(reports)['status'] == 'mismatch'
    reports['sail'] = result('mismatch', value='0x2')
    assert adjudicate(reports)['status'] == 'disagreement'
    assert adjudicate(reports)['dut_matches_at_boundary'] == []


def test_coverage_or_missing_reference_never_passes():
    reports = dict(spike=result(), sail=result())
    reports['sail']['uncompared_instructions'] = 1
    assert adjudicate(reports)['status'] == 'inconclusive'
    reports['sail']['status'] = 'error'
    assert adjudicate(reports)['status'] == 'inconclusive'



def test_execute_uses_both_references(monkeypatch):
    from rvw.cosim import cli
    from rvw.cosim.adjudicate import execute_json
    calls = []
    def check(action, **options):
        calls.append((action, options))
        return result()
    monkeypatch.setattr(cli, 'execute_json', check)
    for sail in ('/missing/sail', '/another/sail'):
        monkeypatch.setenv('RVW_SAIL', sail)
        report = execute_json(elf='input.elf', trace='trace.jsonl', strict=True)
        assert report['status'] == 'match'
        assert report['matched_references'] == ['spike', 'sail']
    assert [options['model'] for _, options in calls] == ['spike', 'sail'] * 2
    assert all(action == 'check' and options['strict'] for action, options in calls)
