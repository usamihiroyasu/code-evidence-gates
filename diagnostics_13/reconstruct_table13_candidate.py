"""Pure saved-pair reconstruction; no source-code evaluation.

Use only the independently bound exported asset SHA. Newly persisted classifications
are reconstructed, not claimed to have been serialized in the historical journal.
"""
import argparse
import hashlib
import json
import math
import os
import re
import stat

SOURCE_SHA = 'd85e8c0c1f11a92504f471652b62a6af30722145d0df78dfc6dee59de627531f'
SOURCE_BYTES = 38101
COMPARATOR_SHA = '3c833c39b842e33f251c83db4347e0a95191909f23b390c12d73ab29a28a4daf'
CONTRACTS = [
    ['HumanEval/66', ['s'], 0, 'ce5e5a735e970485b8515950224d061735dae4de3881c4291a4f1e2368a0eb90', 'exact-string'],
    ['HumanEval/47', ['l'], 0, 'ad75f8c0f3d35e2165131922d469b7d3787c39b208aa5190d78c9e5e37360a7a', 'nonempty-numeric-sequence'],
    ['HumanEval/7', ['strings', 'substring'], 0, 'dd16dbe5ceb6693e772deaa69731a281b01fee09ecf59add3dfa8c37993807aa', 'exact-string-list-and-string'],
    ['HumanEval/129', ['grid', 'k'], 0, '1676cc2b5ad6a462813b4edfd3c80ec6033f4f040a1d88865307d48865a425f2', 'positive-exact-int-k-square-set-grid'],
    ['HumanEval/103', ['n', 'm'], 0, 'e6dc91808f548c1974d070eb343814d5ca29ab056f9ccbedb6760423e3fb5475', 'two-positive-exact-ints'],
    ['HumanEval/2', ['number'], 1e-6, '7aaec53937bfbe0ee2528b37f05a7bcd260a86138e1f84dbf68a509157c763b9', 'positive-float-not-positive-infinity'],
    ['HumanEval/81', ['grades'], 0, 'df0f9608a9665606a7aa0db9fe738bbc3ec9f202611807d156c28c9d827b02ec', 'grades-closed-zero-four'],
    ['HumanEval/6', ['paren_string'], 0, '05a249ecebadb37919899861cc68aeb8ff93749f4f2a5ab155b762485f81639a', 'exact-string-parenthesis-space-prefix-final-balance'],
    ['HumanEval/123', ['n'], 0, 'e0554d77d6b7e8128daf51202f7df5284113fd8b805f8537045b71f1dcb8d5a4', 'positive-exact-int']
]
POLICY = {'source_sha256': COMPARATOR_SHA, 'is_floats_lines': [111,119], 'comparison_lines': [195,205],
          'out_role': 'generated_expected', 'exp_role': 'saved_reference_actual', 'reset_atol': 'per_pair',
          'float_default_atol': 1e-6, 'rtol': 1e-7,
          'qualified_outputs': 'finite-scalar-float-or-exact-int-string-flat-list'}
REPRESENTATION = {'integer': 'canonical-base10-string', 'float': 'canonical-python-binary64-hex',
                  'boolean': 'separate-bool-tag', 'container': 'recursive-list-only', 'max_depth': 6,
                  'max_list_length': 4096, 'max_string_length': 16384}

def need(ok, code):
    if not ok:
        raise ValueError(code)

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf8')

def sha(value):
    return hashlib.sha256(value).hexdigest()

def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, 'DUPLICATE_JSON_KEY')
        result[key] = value
    return result

def reject_constant(_):
    raise ValueError('NONFINITE_JSON_CONSTANT')

def read_bound(path, pin):
    need(re.fullmatch('[0-9a-f]{64}', pin) is not None, 'INPUT_PIN_ARGUMENT')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= 262144,
             'INPUT_REGULAR_CAP')
        raw = bytearray()
        while len(raw) <= 262144:
            part = os.read(fd, min(65536, 262145-len(raw)))
            if not part:
                break
            raw.extend(part)
        after = os.fstat(fd)
        identity = lambda s: (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        need(identity(before) == identity(after) == identity(os.lstat(path)), 'INPUT_DRIFT')
        need(len(raw) == before.st_size and sha(raw) == pin, 'INPUT_SHA')
        return bytes(raw)
    finally:
        os.close(fd)

def decode(value, depth=0):
    need(depth <= 6 and type(value) is dict and set(value) == {'t','v'}, 'TYPED_SCHEMA')
    tag, payload = value['t'], value['v']
    if tag == 'bool':
        need(type(payload) is bool, 'BOOL_TAG')
        return payload
    if tag == 'int':
        need(type(payload) is str and len(payload) <= 4096 and re.fullmatch(r'-?(?:0|[1-9][0-9]*)',payload) is not None,
             'INT_TAG')
        number = int(payload)
        need(str(number) == payload, 'INT_CANONICAL')
        return number
    if tag == 'float64':
        need(type(payload) is str and len(payload) <= 128, 'FLOAT_TAG')
        number = float.fromhex(payload)
        need(math.isfinite(number) and number.hex() == payload, 'FLOAT_CANONICAL_FINITE')
        return number
    if tag == 'str':
        need(type(payload) is str and len(payload) <= 16384, 'STRING_TAG')
        return payload
    if tag == 'list':
        need(type(payload) is list and len(payload) <= 4096, 'LIST_TAG')
        return [decode(x,depth+1) for x in payload]
    raise ValueError('UNQUALIFIED_TYPED_TAG')

def check_shape(task, args):
    # This qualifies the finite saved JSON representation; it is not a new domain rule.
    if task in ('HumanEval/66','HumanEval/6'):
        need(type(args[0]) is str, 'OBSERVED_STRING_SHAPE')
    elif task in ('HumanEval/47','HumanEval/81'):
        need(type(args[0]) is list and all(type(v) in (int,float,bool) for v in args[0]), 'OBSERVED_NUMERIC_LIST')
    elif task == 'HumanEval/7':
        need(type(args[0]) is list and all(type(v) is str for v in args[0]) and type(args[1]) is str,
             'OBSERVED_STRING_LIST')
    elif task == 'HumanEval/129':
        need(type(args[0]) is list and all(type(row) is list and all(type(v) in (int,float,bool) for v in row)
             for row in args[0]) and type(args[1]) in (int,float,bool), 'OBSERVED_GRID_SHAPE')
    elif task == 'HumanEval/103':
        need(all(type(v) in (int,float,bool) for v in args), 'OBSERVED_NUMERIC_PAIR')
    elif task in ('HumanEval/2','HumanEval/123'):
        need(type(args[0]) in (int,float,bool), 'OBSERVED_NUMERIC_SCALAR')
    else:
        raise ValueError('UNKNOWN_TASK')

def in_domain(task, args):
    if task == 'HumanEval/66':
        return type(args[0]) is str
    if task == 'HumanEval/47':
        return len(args[0]) > 0 and all(isinstance(v,(int,float)) for v in args[0])
    if task == 'HumanEval/7':
        return type(args[0]) is list and all(type(v) is str for v in args[0]) and isinstance(args[1],str)
    if task == 'HumanEval/129':
        grid, k = args
        n = len(grid)
        return type(k) is int and k > 0 and n >= 2 and all(len(row) == n for row in grid) and \
            {v for row in grid for v in row} == set(range(1,n*n+1))
    if task == 'HumanEval/103':
        n, m = args
        return type(n) is int and type(m) is int and n > 0 and m > 0
    if task == 'HumanEval/2':
        value = args[0]
        return value > 0 and isinstance(value,float) and value != float('+inf')
    if task == 'HumanEval/81':
        return all(0.0 <= value <= 4.0 for value in args[0])
    if task == 'HumanEval/6':
        value = args[0]
        if type(value) is not str:
            return False
        balance = 0
        for character in value:
            if character not in ('(',')',' '):
                return False
            if character == '(':
                balance += 1
            if character == ')':
                balance -= 1
            if balance < 0:
                return False
        return balance == 0
    if task == 'HumanEval/123':
        return type(args[0]) is int and args[0] > 0
    raise ValueError('UNKNOWN_DOMAIN_RULE')

def qualified_output(value):
    return type(value) in (int,float,str) or (type(value) is list and all(type(x) in (int,str) for x in value))

def compatible(expected, actual, declared_atol):
    exact = expected == actual
    need(not exact, 'SAVED_MISMATCH_INCONSISTENT')
    atol = declared_atol
    if atol == 0 and isinstance(actual,float):
        atol = 1e-6
    if not exact and atol != 0:
        if type(expected) is not type(actual):
            return False, 'NONZERO_ATOL_TYPE_MISMATCH', atol
        need(type(expected) is type(actual) is float, 'UNQUALIFIED_NONSCALAR_FLOAT_COMPARISON')
        return abs(expected-actual) <= atol+1e-7*abs(actual), 'FINITE_SCALAR_TOLERANCE', atol
    return exact, 'EXACT_COMPARISON', atol

def write_new(path, raw):
    need(len(raw) <= 262144, 'OUTPUT_CAP')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        view = memoryview(raw)
        while view:
            count = os.write(fd,view)
            need(count > 0, 'SHORT_WRITE')
            view = view[count:]
        os.fsync(fd)
    finally:
        os.close(fd)

def main():
    parser = argparse.ArgumentParser(description='Reconstruct policy labels on one exact source-bound 34-pair asset.')
    parser.add_argument('--input', required=True)
    parser.add_argument('--input-sha256', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    raw = read_bound(args.input,args.input_sha256)
    asset = json.loads(raw, object_pairs_hook=no_duplicates, parse_constant=reject_constant)
    need(set(asset) == {'schema','purpose','source','representation','contracts','comparator_rule','pairs'}, 'ASSET_KEYS')
    need(asset['schema'] == 'emse-table13-typed-pairs-v1' and asset['purpose'] == 'reconstruction-of-saved-pair-policy-not-new-observations', 'ASSET_SCHEMA')
    need(asset['source'] == {'sha256':SOURCE_SHA,'bytes':SOURCE_BYTES,'records':34,'comparator_sha256':COMPARATOR_SHA}, 'SOURCE_BINDING')
    need(canonical(asset['representation']) == canonical(REPRESENTATION)
         and canonical(asset['comparator_rule']) == canonical(POLICY), 'RULE_REPRESENTATION_BINDING')
    expected_contracts = [{'task_id':t,'parameters':p,'atol':a,'source_contract_index':i,
                           'source_contract_sha256':h,'declarative_rule':r}
                          for i,(t,p,a,h,r) in enumerate(CONTRACTS)]
    need(canonical(asset['contracts']) == canonical(expected_contracts), 'CONTRACT_BINDINGS')
    rules = {r['task_id']:r for r in expected_contracts}
    need(type(asset['pairs']) is list and len(asset['pairs']) == 34, 'EXACT_34_PAIRS')
    indices, identities, seen_tasks = set(), set(), set()
    counts = {'gpt-oss':0,'Flash':0}
    rows = []
    for pair in asset['pairs']:
        need(type(pair) is dict and set(pair) == {'source_record_index','source_row_sha256','pair_id','profile','task_id',
             'case_id','self_test_line','assertion_ast_sha256','reference_code_sha256','saved_exact_status',
             'args','kwargs','generated_expected','reference_actual'}, 'PAIR_KEYS')
        profile, task = pair['profile'], pair['task_id']
        need(profile in counts and task in rules and pair['saved_exact_status'] == 'MISMATCH', 'PAIR_SCOPE')
        index = pair['source_record_index']
        need(type(index) is int and 0 <= index < 34 and index not in indices, 'SOURCE_RECORD_COVERAGE')
        indices.add(index)
        need(type(pair['case_id']) is str and re.fullmatch(re.escape(task)+r':sample:[0-3](?::reference-selftests)?',pair['case_id']), 'CASE_ID')
        need(type(pair['self_test_line']) is int and 0 < pair['self_test_line'] < 100000, 'ASSERTION_LINE')
        for field in ('source_row_sha256','pair_id','assertion_ast_sha256','reference_code_sha256'):
            need(type(pair[field]) is str and re.fullmatch('[0-9a-f]{64}',pair[field]) is not None, 'PAIR_SHA')
        key = [profile,pair['case_id'],pair['assertion_ast_sha256']]
        need(tuple(key) not in identities and sha(canonical(key)) == pair['pair_id'], 'PAIR_IDENTITY')
        identities.add(tuple(key)); counts[profile] += 1; seen_tasks.add(task)
        need(type(pair['args']) is list and len(pair['args']) == len(rules[task]['parameters'])
             and pair['kwargs'] == {}, 'ARGUMENT_SCHEMA')
        values = [decode(x) for x in pair['args']]
        check_shape(task,values)
        expected, actual = decode(pair['generated_expected']), decode(pair['reference_actual'])
        need(qualified_output(expected) and qualified_output(actual), 'QUALIFIED_FINITE_OUTPUT_SHAPE')
        domain = in_domain(task,values)
        close, reason, atol = compatible(expected,actual,rules[task]['atol'])
        category = 'outside_pinned_domain' if not domain else ('in_domain_compatible' if close else 'in_domain_different')
        rows.append({'pair_id':pair['pair_id'],'profile':profile,'task_id':task,'case_id':pair['case_id'],
                     'source_record_index':index,'source_row_sha256':pair['source_row_sha256'],
                     'assertion_ast_sha256':pair['assertion_ast_sha256'],'reference_code_sha256':pair['reference_code_sha256'],
                     'source_contract_sha256':rules[task]['source_contract_sha256'],
                     'domain_rule':rules[task]['declarative_rule'],'in_domain':domain,'comparator_compatible':close,
                     'comparison_reason':reason,'effective_atol':atol,'category':category,
                     'classification_status':'RECONSTRUCTED_FROM_SAVED_PAIR_NOT_HISTORICALLY_SERIALIZED'})
    need(indices == set(range(34)) and counts == {'gpt-oss':20,'Flash':14} and seen_tasks == set(rules), 'FULL_FINITE_COVERAGE')
    summary = {}
    for profile in ('gpt-oss','Flash'):
        group = [row for row in rows if row['profile'] == profile]
        summary[profile] = {'selected_exact_differences':len(group),
                            **{category:sum(row['category'] == category for row in group)
                               for category in ('outside_pinned_domain','in_domain_compatible','in_domain_different')}}
    output = {'schema':'emse-table13-reconstructed-policy-v1','input_sha256':args.input_sha256,
              'source_sha256':SOURCE_SHA,'comparator_source_sha256':COMPARATOR_SHA,
              'classification_status':'RECONSTRUCTED_NOT_NEW_REFERENCE_OBSERVATIONS',
              'rows':rows,'summary':summary,'reference_calls':0,'candidate_calls':0,
              'limits':['Fresh pair and fresh task atol, not mutable original-suite state.',
                        'Selected assertion pairs, not independent candidates or general error prevalence.',
                        'No task/reference/candidate source executed; no historical label reauthentication.']}
    output_raw = json.dumps(output,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False).encode('utf8')+b'\n'
    write_new(args.output,output_raw)
    print(json.dumps({'status':'RECONSTRUCTED_SAVED_PAIR_POLICY','bytes':len(output_raw),'sha256':sha(output_raw),
                      'records':34,'reference_calls':0,'candidate_calls':0},sort_keys=True))

if __name__ == '__main__':
    main()
