from rvw.cov.line_metrics import line_metrics


def test_per_line_metrics_keep_kinds_and_deduplicate_locations():
    def point(identifier,kind,count):
        return {'id':identifier,'count':count,'fields':{'t':kind},'scala':{
            'locations':[{'file':'a.scala','line':4},{'file':'a.scala','line':4},{'file':'a.scala','line':8}]}}
    result = line_metrics([point('a','toggle',0),point('b','expr',1),point('c','fsm_arc',2),
                           {'id':'unmapped','count':4,'fields':{'t':'line'}}],
                          lambda points:{'total':len(points),'hit':sum(p['count']>0 for p in points)})
    assert result['a.scala:4']['metrics']['toggle'] == {'total':1,'hit':0}
    assert result['a.scala:8']['metrics']['expr'] == {'total':1,'hit':1}
    assert result['a.scala:4']['statement_hit_status'] == 'undetermined'


def test_existing_report_exposes_native_metric_summaries():
    from rvw.cov.code import report
    points=[{'id':kind,'count':count,'fields':{'t':kind,'page':'v_'+kind+'/tiny','h':'TOP.tiny'},
             'scala':{'file':'Tiny.scala','line':9}} for kind,count in [('toggle',0),('expr',2),('fsm_arc',1)]]
    result=report({'schema':'rvw.coverage/1','points':points,'sources':{},'tests':{}})
    metrics=result['scala_line_metrics']['Tiny.scala:9']['metrics']
    assert metrics['toggle']['never_hit']==1 and metrics['expr']['hit']==1
    assert result['scala_mapping']['statement_hit_status']=='undetermined'
