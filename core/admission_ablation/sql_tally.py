"""Offline recorded predicates only; no candidate execution."""
import json,sqlite3
def sql_tally(rows):
    db = sqlite3.connect(':memory:');db.execute('CREATE TABLE r(cfg TEXT, task TEXT, j TEXT)')
    db.executemany('INSERT INTO r VALUES(?,?,?)', [(r['config_id'], r['task_id'], json.dumps(r)) for r in rows])
    x = lambda p: "json_extract(j,'$." + p + "')"
    c = x('format_valid')+' AND '+x('structural.code_syntax_ok')
    s = x('format_valid')+' AND '+x('structural.syntax_ok')+' AND '+x('structural.named_entry_exists')+' AND '+x('structural.distinct_target_asserts')+'>=3'
    e = x('format_valid')+' AND '+x('self_exec_status')+"='PASS'"
    expressions = {'C9':c,'S9':s,'E9':e,'A9':'('+s+') AND ('+e+')','Pb':x('G_O_base')}
    passed = x('oracle_base_status')+"='pass' AND "+x('oracle_plus_status')+"='pass'"
    fail = x('oracle_base_status')+"='fail' OR "+x('oracle_plus_status')+"='fail'"
    timeout = x('oracle_base_status')+"='timeout' OR "+x('oracle_plus_status')+"='timeout'"
    result = {}
    for name, expr in expressions.items():
        q = 'WITH t AS(SELECT cfg,task,('+expr+') AS a,('+passed+') AS p,CASE WHEN '+fail+' THEN 0 WHEN '+timeout+' THEN 1 ELSE 2 END AS kind FROM r) '
        q += 'SELECT cfg,count(*),sum(a),sum(a AND p),sum(a AND NOT p),sum(NOT a AND p),count(DISTINCT CASE WHEN a THEN task END),count(DISTINCT CASE WHEN a AND p THEN task END),sum(a AND NOT p AND kind=0),sum(a AND NOT p AND kind=1),sum(a AND NOT p AND kind=2) FROM t GROUP BY cfg'
        for cfg,n,a,p,np,excluded,ta,tp,nf,nt,nu in db.execute(q):
            result.setdefault(cfg,{})[name] = dict(planned=n,admitted=a,admitted_plus_pass=p,admitted_nonpass=np,excluded_plus_pass=excluded,conditional_nonpass_denominator=a,conditional_nonpass_rate=np/a if a else None,tasks_with_admission=ta,tasks_with_admitted_plus_pass=tp,nonpass_status_counts={'FAIL':nf,'TIMEOUT':nt,'UNAVAILABLE':nu})
    db.close();return result
