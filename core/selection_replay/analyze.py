"""Saved-record deterministic selection; never executes candidate code."""
import hashlib, json
from collections import Counter
from fractions import Fraction
from pathlib import Path

RULES = ('C9', 'S9', 'E9', 'A9', 'Pb')
def eligible(rule, r):
    s = r['structural']
    structure = r['format_valid'] and s['syntax_ok'] and s['named_entry_exists'] and s['distinct_target_asserts'] >= 3
    execute = r['format_valid'] and r['self_exec_status'] == 'PASS'
    return {'C9': r['format_valid'] and s['code_syntax_ok'], 'S9': structure, 'E9': execute, 'A9': structure and execute, 'Pb': r['G_O_base']}[rule]

def select(call_ids):
    return min(call_ids, key=lambda c: int(c.rsplit(':', 1)[1])) if call_ids else None

def task_record(rule, rows):
    ids = sorted((r['call_id'] for r in rows if eligible(rule, r)), key=lambda c: int(c.rsplit(':', 1)[1]))
    choice = select(ids); by_id = {r['call_id']: r for r in rows}
    k = sum(by_id[c]['G_O_plus'] for c in ids)
    return dict(admitted_call_ids=ids, chosen_call_id=choice, state='A' if choice is None else 'P' if by_id[choice]['G_O_plus'] else 'N', uniform_pass=str(Fraction(k, len(ids))) if ids else '0', uniform_nonpass=str(Fraction(len(ids)-k, len(ids))) if ids else '0')

def analyze(rows):
    out = {}
    for cfg in sorted({r['config_id'] for r in rows}):
        group = [r for r in rows if r['config_id'] == cfg]
        tasks = sorted({r['task_id'] for r in group}); out[cfg] = {}
        assert len(group) == 128 and len(tasks) == 32
        for t in tasks:
            pool = [r for r in group if r['task_id'] == t]
            assert len(pool) == 4 and {int(r['call_id'].rsplit(':', 1)[1]) for r in pool} == {0,1,2,3}
            assert len({r['call_id'] for r in pool}) == 4
        baseline = {t: task_record('C9', [r for r in group if r['task_id'] == t]) for t in tasks}
        for rule in RULES:
            decisions = {t: task_record(rule, [r for r in group if r['task_id'] == t]) for t in tasks}
            counts = Counter(d['state'] for d in decisions.values()); n = counts['P']+counts['N']
            up = sum((Fraction(d['uniform_pass']) for d in decisions.values()), Fraction(0))
            un = sum((Fraction(d['uniform_nonpass']) for d in decisions.values()), Fraction(0))
            assert up+un == n and n+counts['A'] == 32
            transitions = Counter(baseline[t]['state']+'>'+decisions[t]['state'] for t in tasks)
            out[cfg][rule] = dict(planned_tasks=32, selected_tasks=n, abstentions=counts['A'], first_pass=counts['P'], first_nonpass=counts['N'], first_yield=str(Fraction(counts['P'],32)), first_conditional_pass=str(Fraction(counts['P'],n)) if n else None, uniform_expected_pass=str(up), uniform_expected_nonpass=str(un), uniform_yield=str(up/32), uniform_conditional_pass=str(up/n) if n else None, c9_paired_transitions=dict(sorted(transitions.items())), tasks=decisions)
    return out

def fixtures():
    assert select(['t:sample:2','t:sample:0','t:sample:1']) == 't:sample:0'
    assert select(['t:sample:10','t:sample:2']) == 't:sample:2' and select([]) is None
    rows = [dict(call_id=f't:sample:{i}', format_valid=True, self_exec_status='PASS' if i else 'FAIL', G_O_base=True, G_O_plus=bool(i), structural=dict(syntax_ok=True, code_syntax_ok=True,named_entry_exists=True,distinct_target_asserts=3)) for i in range(4)]
    assert task_record('C9',rows)['state'] == 'N' and task_record('E9',rows)['state'] == 'P'
    assert task_record('C9',rows)['uniform_pass'] == '3/4'
    assert task_record('E9',rows) == task_record('E9',list(reversed(rows)))
    for r in rows:r['format_valid']=False; r['G_O_base']=False
    assert all(task_record(p,rows)['state'] == 'A' for p in RULES)

if __name__ == '__main__':
    root = Path(__file__).resolve().parent; fixtures()
    manifest = json.loads((root/'INPUT_MANIFEST.json').read_text())
    for n,h in manifest['frozen_files'].items():assert hashlib.sha256((root/n).read_bytes()).hexdigest() == h
    result = {}
    for study,s in manifest['studies'].items():
        path = root.parent/s['derivative_path']; assert hashlib.sha256(path.read_bytes()).hexdigest() == s['derivative_sha256']
        result[study] = analyze([json.loads(l) for l in path.read_text().splitlines()])
    payload = dict(schema='fixed-policy-selection-replay-v1',status='COMPLETE_POST_OUTCOME_SAVED_RECORD_REPLAY',input_manifest_sha256=hashlib.sha256((root/'INPUT_MANIFEST.json').read_bytes()).hexdigest(),results=result,new_model_calls=0,new_native_executions=0)
    with (root/'analysis.json').open('x') as f:json.dump(payload,f,indent=2,sort_keys=True); f.write('\n')
