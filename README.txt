From Candidate Admission to Task-Level Return
Saved-record reconstruction artifact

This artifact supplies recorded candidate-admission, task-selection and selected
rejection-diagnostic evidence from two separately frozen public-task cohorts.
It contains typed records, explicit fixture identities, source/hash commitments,
table-to-file maps and reconstruction scripts. It is not full generation or native
evaluation replication, and does not independently validate recorded outcomes.

Requirements and commands (run from this artifact root)
  Standard-library Python with SQLite JSON functions available.
  Recorded successful aggregation check used CPython 3.11.6. This is an
  aggregation interpreter version, not an inference/evaluation backend identity
  or a claim that every original stage used that build.

  python3 -I -B core/aggregate_reviewed.py --output NEW_CORE_RESULT.json
  python3 -I -B diagnostics_5_14/aggregate_diagnostics.py
  python3 -I -B diagnostics_13/reconstruct_table13_candidate.py --input diagnostics_13/TYPED_PAIRS.json --input-sha256 6038514deb8714f4bc63d9195da9e58f2a7353ec1d62e40d7d5ae476faf55cf5 --output NEW_TABLE13_RESULT.json

Choose new output filenames; existing outputs are not overwritten. The second
command writes its result to stdout. Do not run core/selection_replay/analyze.py
as a standalone entrypoint: only its aggregation definitions are used here.

Coverage
  core/: Tables 2/4/6, 3, 7, 9 and derivable Table 15 cross-cells.
  diagnostics_5_14/: Table 5 exception/registration counts and Table 14 assertion
  status counts, retaining unsupported records and absent reference bindings.
  diagnostics_13/: all 34 selected saved assertion-output pairs, including three
  outside-domain and two comparator-compatible pairs. Per-pair classifications
  are reconstructed from saved pairs and pinned domain/comparison rules; they
  are not claimed to be historically serialized labels or new observations.

Preserved result files come from the recorded checks of these inputs. Two script
headers have since been made timeless; their computational ASTs are unchanged.
CODE_EQUIVALENCE.json binds the old/new bytes and AST comparison. Do not replace
the historical driver hashes inside saved results with hashes of a later file.

The scripts do not call models, execute candidate/reference programs, rerun native
suites, or recompute bootstrap intervals. They do not authenticate the original
label derivation. Raw problem text and executable implementation/test bodies are
not supplied. Protocols retain historical study-stage descriptions; these are
not additional actions performed by the reconstruction commands above.

Integrity and origin
  MANIFEST.json binds every delivered leaf other than itself, including saved
  results. Nested core/PACKAGE_MANIFEST.json covers the core leaves other than
  itself; the input manifest pins the core entrypoint's required inputs.
  FILE_PROVENANCE_AND_RIGHTS.json maps every leaf's source and notice scope.
  Upstream HumanEval/EvalPlus license texts remain in core/rights. Those notices
  do not automatically license all author-contributed code or recorded data.

Licenses
  Author-contributed software portions: MIT (LICENSE_CODE_MIT.txt).
  Author-created data and documentation portions: CC BY 4.0
  (LICENSE_DATA_DOCS_CC_BY_4.0.txt). Third-party materials retain their original
  conditions and notices; see FILE_PROVENANCE_AND_RIGHTS.json.
