"""Offline recorded predicates only; no candidate execution."""
def tally(rows):
    result = {}
    for cfg in sorted({r['config_id'] for r in rows}):
        group = [r for r in rows if r['config_id'] == cfg]
        available = {i for i, r in enumerate(group) if r['G_O_plus']}
        pools = {p: set() for p in ['C9', 'S9', 'E9', 'A9', 'Pb']}
        for i, r in enumerate(group):
            s = r['structural'];c = r['format_valid'] and s['code_syntax_ok']
            structure = r['format_valid'] and s['syntax_ok'] and s['named_entry_exists'] and s['distinct_target_asserts'] >= 3
            execute = r['format_valid'] and r['self_exec_status'] == 'PASS'
            assert r['G_E'] == (structure and execute)
            assert r['G_O_base'] == (r['oracle_base_status'] == 'pass')
            assert r['G_O_plus'] == (r['oracle_base_status'] == r['oracle_plus_status'] == 'pass')
            for p, admit in zip(pools, [c, structure, execute, structure and execute, r['G_O_base']]):
                if admit:pools[p].add(i)
        result[cfg] = {}
        for p, admitted in pools.items():
            passed = admitted & available;nonpass = admitted - available;counts = dict.fromkeys(['FAIL', 'TIMEOUT', 'UNAVAILABLE'], 0)
            for i in nonpass:
                statuses = {group[i]['oracle_base_status'], group[i]['oracle_plus_status']}
                counts['FAIL' if 'fail' in statuses else 'TIMEOUT' if 'timeout' in statuses else 'UNAVAILABLE'] += 1
            result[cfg][p] = dict(planned=len(group), admitted=len(admitted), admitted_plus_pass=len(passed), admitted_nonpass=len(nonpass), excluded_plus_pass=len(available-admitted), conditional_nonpass_denominator=len(admitted), conditional_nonpass_rate=len(nonpass)/len(admitted) if admitted else None, tasks_with_admission=len({group[i]['task_id'] for i in admitted}), tasks_with_admitted_plus_pass=len({group[i]['task_id'] for i in passed}), nonpass_status_counts=counts)
    return result
