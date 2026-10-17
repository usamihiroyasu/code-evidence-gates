"""Aggregate exported saved diagnostic labels without executing experimental code.

Stdlib only; no candidate/test/contract execution or historical-helper import.
Usage after reviewed export: python aggregate_diagnostics.py
Prints one JSON result; input files and this driver must match INPUT_MANIFEST.
"""
import hashlib
import json
import os
import stat
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent
FILES = ('inline_labels.json', 'alias_labels.json', 'registration_labels.json',
         'gptoss_assertion_labels.json', 'flash_assertion_labels.json', 'recorded_totals.json')
CAP = 16 * 1024 * 1024
STATUSES = ('MATCH', 'MISMATCH', 'REFERENCE_EXCEPTION', 'TIMEOUT', 'UNSUPPORTED')


def read(name, expected=None):
    if name not in (*FILES, 'INPUT_MANIFEST.json', 'aggregate_diagnostics.py'):
        raise ValueError('unlisted input')
    fd = os.open(ROOT / name, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > CAP:
            raise ValueError('not a bounded regular file')
        raw = stream.read(CAP + 1)
    if len(raw) > CAP or (expected and hashlib.sha256(raw).hexdigest() != expected):
        raise ValueError('length/hash mismatch')
    return raw


def load(name, pins):
    return json.loads(read(name, pins[name]))


def exception_counts(packet, paired=False):
    counts = {}
    seen = set()
    natural = fixtures = 0
    mapping = {(r['config_id'], r['call_id']): r for r in packet['origin_mapping']} if paired else None
    if paired and len(mapping) != len(packet['origin_mapping']):
        raise ValueError('duplicate on/off origin identity')
    for row in packet['records']:
        key = (row['config_id'], row['call_id'])
        if key in seen or row['is_fixture'] != (row['config_id'] == 'fixture'):
            raise ValueError('duplicate identity or inconsistent fixture flag')
        seen.add(key)
        er = row['exception_result']
        if er == {'kind': 'PASS'} and row['self_exec_status'] == 'PASS':
            category = 'PASS'
        elif set(er) == {'kind', 'class'} and er['kind'] == 'EXCEPTION':
            category = er['class']
            required = 'TIMEOUT' if category == 'TimeoutException' else 'FAIL'
            if row['self_exec_status'] != required:
                raise ValueError('inconsistent exception record')
        else:
            raise ValueError('invalid exception record')
        if row['is_fixture']:
            fixtures += 1
            continue
        natural += 1
        arm = row['config_id']
        if paired:
            origin = mapping[key]
            if any(origin[f] != row[f] for f in ('task_id', 'code_sha256', 'self_tests_sha256')):
                raise ValueError('on/off origin hash/task mismatch')
            condition = origin['alias_condition']
            if condition not in ('on', 'off'):
                raise ValueError('invalid registration condition')
            counts.setdefault(arm, {}).setdefault(condition, Counter())[category] += 1
        else:
            counts.setdefault(arm, Counter())[category] += 1
    if paired and set(mapping) != {key for key in seen if key[0] != 'fixture'}:
        raise ValueError('on/off coverage mismatch')
    return counts, {'natural_records': natural, 'fixture_records': fixtures,
                    'origin_mapping_records': len(packet['origin_mapping'])}


def assertions(packet):
    expected = {}
    case_ids = set()
    for case in packet['cases']:
        if case['case_id'] in case_ids:
            raise ValueError('duplicate case identity')
        case_ids.add(case['case_id'])
        for item in case['assertions']:
            key = (case['case_id'], item['lineno'], item['assertion_ast_sha256'])
            if key in expected or item['status'] not in ('COMPILED', 'UNSUPPORTED'):
                raise ValueError('duplicate/invalid compiler assertion')
            expected[key] = (case['task_id'], item['status'])
    observed = {}
    for row in packet['records']:
        key = (row['case_id'], row['lineno'], row['assertion_ast_sha256'])
        if key not in expected or key in observed or row['status'] not in STATUSES:
            raise ValueError('unknown/duplicate assertion result')
        task, compiler = expected[key]
        if task != row['task_id'] or (compiler == 'UNSUPPORTED') != (row['status'] == 'UNSUPPORTED'):
            raise ValueError('compiler/result identity or status mismatch')
        observed[key] = row['status']
    if set(observed) != set(expected):
        raise ValueError('assertion coverage mismatch')
    counts = {status: 0 for status in STATUSES}
    with_mismatch = all_match_complete = without_mismatch_incomplete = 0
    for case in packet['cases']:
        statuses = [observed[(case['case_id'], a['lineno'], a['assertion_ast_sha256'])] for a in case['assertions']]
        for status in statuses:
            counts[status] += 1
        complete = not any(status in ('UNSUPPORTED', 'REFERENCE_EXCEPTION', 'TIMEOUT') for status in statuses)
        mismatch = 'MISMATCH' in statuses
        with_mismatch += int(mismatch)
        all_match_complete += int(complete and bool(statuses) and all(s == 'MATCH' for s in statuses))
        without_mismatch_incomplete += int(not mismatch and not complete)
    return {'cases_total': len(case_ids), 'assertions_total': len(observed), 'counts': counts,
            'cases_with_mismatch': with_mismatch, 'cases_all_match_complete': all_match_complete,
            'cases_without_mismatch_incomplete': without_mismatch_incomplete}


def main():
    manifest = json.loads(read('INPUT_MANIFEST.json'))
    if manifest['schema'] != 'emse-saved-diagnostic-projection-v1' or set(manifest['files']) != set(FILES):
        raise ValueError('manifest schema/file whitelist mismatch')
    read('aggregate_diagnostics.py', manifest['driver_sha256'])
    inputs = {name: load(name, manifest['files']) for name in FILES}
    table5, coverage = {}, {}
    for arm, file in (('inline', FILES[0]), ('alias', FILES[1]), ('registration', FILES[2])):
        table5[arm], coverage[arm] = exception_counts(inputs[file], paired=(arm == 'registration'))
    table14 = {profile: assertions(inputs[file]) for profile, file in (
        ('gpt-oss', FILES[3]), ('flash', FILES[4]))}
    actual = {'table5': table5, 'table14': table14}
    if actual != inputs['recorded_totals.json']:
        raise ValueError('recomputed labels disagree with hash-pinned saved aggregates')
    combined = {status: sum(item['counts'][status] for item in table14.values()) for status in STATUSES}
    print(json.dumps({'schema': 'emse-diagnostic-aggregation-result-v1', **actual,
          'table5_record_coverage': coverage,
          'table14_combined': {'cases_total': sum(x['cases_total'] for x in table14.values()),
                               'assertions_total': sum(combined.values()),
                               'resolved': combined['MATCH'] + combined['MISMATCH'], 'counts': combined},
          'saved_aggregate_match': True, 'new_scientific_executions': 0,
          'limits': 'Saved-label reconstruction for Tables 5 and 14; no generated-code/reference-output/policy re-execution and no Table 13 classification replay.'},
          sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
