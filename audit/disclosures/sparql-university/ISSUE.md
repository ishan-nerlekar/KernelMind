**Title:** sparql-university: the graph can't distinguish "GB counted as EU" or ">= 10" from correct queries

**What the instruction requires**
> assume that "European Union countries" refers to the official EU member states as of 2025-08-16

> at least one has more than 10 students currently enrolled

**What passes today**
- `near-1-edge-case/solve.sh`: the reference query with `"GB"` added to the EU list (the UK left in 2020). It passes.
- `near-2-edge-case/solve.sh`: the reference query with `HAVING(COUNT(DISTINCT ?student) >= 10)`. It passes.

**Why the tests miss it**
The graph contains no `"GB"` literal and no department with exactly 10 current students, so both queries return the same rows as the reference.

**Suggested fix** (`test_fix_addition.py`): two extra tests that run the agent's query on modified copies of the graph: NKUA moved to `GB`, and HistoryAndPhilosophy_NKUA reduced from 12 to exactly 10 current students. In both, Aristotle Tympas must drop out. The expected rows come from the reference query.
Checked locally with rdflib: the reference passes both; near-1 fails the GB test and near-2 the 10-student test.
