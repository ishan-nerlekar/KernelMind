**What the instruction requires**
> assume that "European Union countries" refers to the official EU member states as of 2025-08-16

> at least one has more than 10 students currently enrolled

**What passes today**
- `near-1-edge-case/solve.sh` (below): the reference query with `"GB"` added to the EU list (the UK left in 2020). It passes.
- `near-2-edge-case/solve.sh` (below): the reference query with `HAVING(COUNT(DISTINCT ?student) >= 10)`. It passes.

**Why the tests miss it**
The graph contains no `"GB"` literal and no department with exactly 10 current students, so both queries return the same rows as the reference.

**Suggested fix** (below): two extra tests that run the agent's query on modified copies of the graph: NKUA moved to `GB`, and HistoryAndPhilosophy_NKUA reduced from 12 to exactly 10 current students. In both, Aristotle Tympas must drop out. The expected rows come from the reference query.
Checked locally with rdflib: the reference passes both; near-1 fails the GB test and near-2 the 10-student test.

**Reproduce** (Harbor oracle agent with the solution swapped in):
```bash
cp -R sparql-university /tmp/sparql-university-check
# put one of the solve.sh scripts below in /tmp/sparql-university-check/solution/solve.sh, then:
harbor trial start -p /tmp/sparql-university-check -a oracle
```

<details><summary><code>near-1-edge-case/solve.sh</code> (passes the current tests)</summary>

```bash
#!/bin/bash
set -e
cat << 'EOF' > /app/solution.sparql
PREFIX uni: <http://university.org/ontology/>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT ?professorName (GROUP_CONCAT(DISTINCT ?country; separator=", ") AS ?countries)
WHERE {
  ?professor a uni:Person ;
             uni:hasName ?professorName ;
             uni:role ?role ;
             uni:worksIn ?euDepartment ;
             uni:worksIn ?department ;
             uni:worksIn ?departmentForCountries .
  FILTER(STRSTARTS(?role, "Professor"))
  ?departmentForCountries uni:belongsTo ?university .
  ?university uni:locatedInCountry ?country .
  ?euDepartment uni:belongsTo ?euUniversity .
  ?euUniversity uni:locatedInCountry ?euCountry .
  VALUES ?euCountry {
  "AT" "BE" "BG" "HR" "CY" "CZ" "DK" "EE" "FI" "FR"
  "DE" "GR" "HU" "IE" "IT" "LV" "LT" "LU" "MT" "NL"
  "PL" "PT" "RO" "SK" "SI" "ES" "SE" "GB"
  }
  ?class uni:isTaughtIn ?department .
  ?student uni:isEnrolledIn ?class ;
           uni:hasEnrollmentDate ?enrollDate .
  OPTIONAL { ?student uni:hasGraduationDate ?gradDate }
  FILTER( ?enrollDate <= "2025-08-16"^^xsd:date &&
          (!BOUND(?gradDate) || ?gradDate > "2025-08-16"^^xsd:date) )
}
GROUP BY ?professorName
HAVING(COUNT(DISTINCT ?student) > 10)
EOF
```
</details>

<details><summary><code>near-2-edge-case/solve.sh</code> (passes the current tests)</summary>

```bash
#!/bin/bash
set -e
cat << 'EOF' > /app/solution.sparql
PREFIX uni: <http://university.org/ontology/>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT ?professorName (GROUP_CONCAT(DISTINCT ?country; separator=", ") AS ?countries)
WHERE {
  ?professor a uni:Person ;
             uni:hasName ?professorName ;
             uni:role ?role ;
             uni:worksIn ?euDepartment ;
             uni:worksIn ?department ;
             uni:worksIn ?departmentForCountries .
  FILTER(STRSTARTS(?role, "Professor"))
  ?departmentForCountries uni:belongsTo ?university .
  ?university uni:locatedInCountry ?country .
  ?euDepartment uni:belongsTo ?euUniversity .
  ?euUniversity uni:locatedInCountry ?euCountry .
  VALUES ?euCountry {
  "AT" "BE" "BG" "HR" "CY" "CZ" "DK" "EE" "FI" "FR"
  "DE" "GR" "HU" "IE" "IT" "LV" "LT" "LU" "MT" "NL"
  "PL" "PT" "RO" "SK" "SI" "ES" "SE"
  }
  ?class uni:isTaughtIn ?department .
  ?student uni:isEnrolledIn ?class ;
           uni:hasEnrollmentDate ?enrollDate .
  OPTIONAL { ?student uni:hasGraduationDate ?gradDate }
  FILTER( ?enrollDate <= "2025-08-16"^^xsd:date &&
          (!BOUND(?gradDate) || ?gradDate > "2025-08-16"^^xsd:date) )
}
GROUP BY ?professorName
HAVING(COUNT(DISTINCT ?student) >= 10)
EOF
```
</details>

<details><summary>Tests to add to `tests/test_outputs.py`</summary>

```python
import rdflib


def _graph_variant(mutate):
    g = Graph()
    g.parse(str(DATA_PATH), format="ttl")
    mutate(g, rdflib.Namespace(dict(g.namespaces())["uni"]))
    return g


def _results(g):
    return sorted((str(r[0]), str(r[1])) for r in g.query(SPARQL_PATH.read_text()))


def _nkua_in_gb(g, uni):
    """Move NKUA (Greece) to the UK, which was not an EU member state on 2025-08-16."""
    nkua = next(u for u in g.subjects(uni.locatedInCountry, rdflib.Literal("GR")) if str(u).endswith("NKUA"))
    g.set((nkua, uni.locatedInCountry, rdflib.Literal("GB")))


def _history_nkua_exactly_ten(g, uni):
    """Leave HistoryAndPhilosophy_NKUA with exactly 10 current students (it has 12)."""
    dept = next(d for d in set(g.objects(None, uni.isTaughtIn)) if str(d).endswith("HistoryAndPhilosophy_NKUA"))
    classes = set(g.subjects(uni.isTaughtIn, dept))
    current = sorted({s for c in classes for s in g.subjects(uni.isEnrolledIn, c)
                      if not any(True for _ in g.objects(s, uni.hasGraduationDate))})
    for s in current[:2]:
        for c in classes:
            g.remove((s, uni.isEnrolledIn, c))


EXPECTED_GB = [('Orfeas Menis', 'GR, US'), ('Pepe Attanasio', 'PT, GR')]  # from the reference query
EXPECTED_TEN = [('Orfeas Menis', 'GR, US'), ('Pepe Attanasio', 'PT, GR')]  # from the reference query


def test_non_eu_country_excluded():
    """The graph has no non-EU country in Europe, so a query that counts "GB" as EU passes."""
    assert _results(_graph_variant(_nkua_in_gb)) == EXPECTED_GB


def test_exactly_ten_students_is_not_more_than_ten():
    """No department has exactly 10 current students, so `>= 10` passes for 'more than 10'."""
    assert _results(_graph_variant(_history_nkua_exactly_ten)) == EXPECTED_TEN
```
</details>


_Found while auditing Terminal-Bench 2.0 verifiers with near-miss solutions (commit `2fd12b8`). Happy to turn the suggested test change into a PR._
