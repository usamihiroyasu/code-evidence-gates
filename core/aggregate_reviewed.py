#!/usr/bin/env python3
"""Aggregate saved labels only; never runs generated programs, fixtures or bootstrap."""
import argparse
import hashlib
import json
import runpy
import sys
from collections import Counter
from fractions import Fraction
from itertools import permutations
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def selection_summary(core, rows, rule):
    result = core['analyze'](rows)
    return {cfg: result[cfg][rule] for cfg in result}


def order_summary(core, before, after, old_rule, new_rule):
    tasks = sorted({r['task_id'] for r in before})
    require(len(tasks) == 32 and len(before) == len(after) == 128, 'ORDER_COHORT')
    changes = []
    for order in permutations(range(4)):
        counts = []
        for rows, rule in ((before, old_rule), (after, new_rule)):
            passed = 0
            for task in tasks:
                pool = {int(r['call_id'].rsplit(':', 1)[1]): r for r in rows if r['task_id'] == task}
                require(set(pool) == set(range(4)), 'FOUR_SAVED_SAMPLES_REQUIRED')
                chosen = next((pool[i] for i in order if core['eligible'](rule, pool[i])), None)
                passed += bool(chosen is not None and chosen['G_O_plus'])
            counts.append(passed)
        changes.append(counts[1] - counts[0])
    return dict(orders=24, pass_delta_range=[min(changes), max(changes)],
                uniform_order_expected_pass_delta=str(Fraction(sum(changes), 24)),
                orders_with_changed_pass_total=sum(x != 0 for x in changes),
                delta_histogram=dict(sorted(Counter(map(str, changes)).items())))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New output JSON; existing file is never overwritten')
    args = parser.parse_args()
    require(not args.output.exists(), 'OUTPUT_ALREADY_EXISTS')
    manifest_path = ROOT / 'INPUT_MANIFEST_REVIEWED.json'
    manifest = json.loads(manifest_path.read_text())
    for item in manifest['files']:
        path = ROOT / item['relative_path']
        require(path.is_file() and sha(path) == item['sha256'], 'INPUT_SHA_MISMATCH: ' + item['relative_path'])
    tally = runpy.run_path(str(ROOT / 'admission_ablation/set_tally.py'), run_name='_saved_label_library')['tally']
    sql = runpy.run_path(str(ROOT / 'admission_ablation/sql_tally.py'), run_name='_saved_label_library')['sql_tally']
    core = runpy.run_path(str(ROOT / 'selection_replay/analyze.py'), run_name='_saved_label_library')
    result = {'status': 'SAVED_LABEL_AGGREGATE_ONLY', 'input_manifest_sha256': sha(manifest_path),
              'driver_sha256': sha(Path(__file__)), 'new_model_calls': 0, 'new_native_executions': 0,
              'bootstrap_runs': 0, 'old_fixture_calls': 0, 'tables_2_4_6': {}, 'table_7': {}, 'table_3': {}, 'table_9': {}}
    for study in ('v9', 'v11'):
        rows = lines(ROOT / ('admission_ablation/' + study + '_rows.jsonl'))
        require(len(rows) == 256, 'EXPECTED_256_RECORDS_PER_STUDY')
        counts = tally(rows)
        require(counts == sql(rows), 'SEPARATE_SET_SQL_DISAGREEMENT')
        result['tables_2_4_6'][study] = counts
        result['table_7'][study] = core['analyze'](rows)
    planned = lines(ROOT / 'full_contract/planned_rows.jsonl')
    journal = lines(ROOT / 'full_contract/journal.jsonl')
    require(len(planned) == 512 and len(journal) == 511, 'FULL_CONTRACT_RECORD_COUNTS')
    fixtures = json.loads((ROOT / 'full_contract/ACTUAL_FIXTURES.json').read_text())
    fixture_keys = {(r['config_id'], r['call_id']) for r in fixtures}
    require(len(fixtures) == len(fixture_keys) == 7, 'ACTUAL_FIXTURE_KEYS')
    valid_keys = {(r['native_config_id'], r['call_id']) for r in planned if r['format_valid']}
    index = {(r['config_id'], r['call_id']): r for r in journal if (r['config_id'], r['call_id']) in valid_keys}
    require(len(valid_keys) == len(index) == 504 and len(journal) - len(index) == 7, 'NATIVE_LABEL_KEYS_OR_FIXTURE_COUNT')
    require(not (valid_keys & fixture_keys) and {(r['config_id'], r['call_id']) for r in journal} - valid_keys == fixture_keys, 'FIXTURE_KEY_SEPARATION')
    require(len({(r['config_id'], r['call_id']) for r in journal}) == 511, 'DUPLICATE_JOURNAL_KEYS')
    expected = json.loads((ROOT / 'EXPECTED_SAVED_RESULTS.json').read_text())
    for study in ('v9', 'v11'):
        result['table_3'][study] = {}
        result['table_9'][study] = {}
        for cfg in ('flash', 'gpt-oss'):
            before = [r for r in planned if r['study'] == study and r['config_id'] == cfg]
            after = []
            for row in before:
                record = index.get((row['native_config_id'], row['call_id']))
                if row['format_valid']:
                    require(record is not None and record['format_valid'] is True and record['simulation_fixture'] is True, 'SAVED_CANDIDATE_METADATA')
                    # Historical marker is true for all records; actual fixtures are identified by their manifest keys.
                    require(all(row[k] == record[k] for k in ('call_id', 'task_id', 'code_sha256', 'self_tests_sha256')), 'PAIRED_IDENTITY_MISMATCH')
                    require(record['condition'] == 'explicit_namespace_module_alias', 'CONTRACT_IDENTITY')
                after.append(row | {'self_exec_status': record['self_exec_status'] if record else 'INVALID'})
            row_results = {}
            for label, group in (('A9', before), ('A9*', after)):
                admitted = [r for r in group if core['eligible']('A9', r)]
                selected = selection_summary(core, group, 'A9')[cfg]
                cell = dict(planned=128, admitted=len(admitted), admitted_suite_nonpass=sum(not r['G_O_plus'] for r in admitted),
                            excluded_suite_pass=sum(r['G_O_plus'] and not core['eligible']('A9', r) for r in group),
                            first_pass=selected['first_pass'], first_nonpass=selected['first_nonpass'],
                            abstentions=selected['abstentions'], uniform_expected_pass=selected['uniform_expected_pass'])
                require(cell == expected['table_3'][study][cfg][label], 'SAVED_TABLE3_DISAGREEMENT')
                row_results[label] = cell
            result['table_3'][study][cfg] = row_results
            order_results = {'C9>A9': order_summary(core, before, before, 'C9', 'A9'),
                             'A9>A9*': order_summary(core, before, after, 'A9', 'A9')}
            for contrast, cell in order_results.items():
                saved = expected['table_9'][study][cfg][contrast]
                require(all(cell[k] == saved[k] for k in saved), 'SAVED_TABLE9_DISAGREEMENT')
            result['table_9'][study][cfg] = order_results
            gained = [r for r, n in zip(before, after) if r['self_exec_status'] != 'PASS' and n['self_exec_status'] == 'PASS']
            result.setdefault('contract_completion_gain', {}).setdefault(study, {})[cfg] = {
                'newly_completed_candidates': len(gained),
                'newly_completed_but_structure_rejected': sum(not core['eligible']('S9', r) for r in gained),
                'note': 'Candidate identities paired before aggregating; no semantic correctness inference.'}
    result['limits'] = 'Aggregation of supplied frozen labels, not verification of label derivation, code execution, original journal SQL, bootstrap, reference health, generation or complete reproduction.'
    with args.output.open('x') as output:
        json.dump(result, output, indent=2, sort_keys=True)
        output.write('\n')
    print(json.dumps({'output': str(args.output), 'sha256': sha(args.output), 'status': result['status']}))


if __name__ == '__main__':
    main()
