Core saved-label aggregation

Run from the artifact root:
  python3 -I -B core/aggregate_reviewed.py --output NEW_CORE_RESULT.json
Or, from inside core/:
  python3 -I -B aggregate_reviewed.py --output NEW_CORE_RESULT.json

Requires a standard-library Python runtime with SQLite JSON functions.
Recorded successful aggregation check used CPython 3.11.6. This does not identify
the original generation or native-evaluation backend.

The entrypoint checks all 13 input-manifest pins. It imports the pure set/SQL and
selection definitions without calling the historical library main or fixtures.
Do not use selection_replay/analyze.py as a standalone entrypoint.

TABLE_TO_FILES.json maps current Tables 2/4/6, 3, 7, 9 and derivable Table 15
cross-cells to supplied records/result keys. Diagnostic Tables 5/13/14 have their
own separate directories/commands. All planned attempts and explicit fixture
identities remain represented. simulation_fixture=true marks all 511 saved
full-contract rows; membership is defined by seven ACTUAL_FIXTURES keys, not by
that legacy marker.

Set and SQLite tallies operate on the same supplied derivative labels, not newly
queried original native journals. This aggregation does not re-execute programs,
regenerate samples, validate reference outputs, recompute bootstrap intervals or
certify reference health. EXPERIMENT_METADATA retains actual request/seed/source
commitments with its original stage-specific qualifications.

INPUT_MANIFEST_REVIEWED.json pins execution inputs. PACKAGE_MANIFEST.json binds
all delivered core leaves other than itself, including ACTUAL_RESULT.json. The
artifact-root MANIFEST.json binds the entire delivered selection. SOURCE_BINDINGS
preserves source roles/hashes without private absolute paths. See the root origin
map and THIRD_PARTY_NOTICES.txt for file-specific source/notice distinctions.
