"""Differential probe for sparql-university: a professor with 6 current students in each of two EU departments
(12 in total, no single department above 10) must NOT be returned."""
import re, sys, rdflib
TB2 = sys.argv[1] if len(sys.argv) > 1 else "external/tb2/sparql-university"
ref = open(f"{TB2}/solution/solve.sh").read()
ref = ref[ref.index("PREFIX"):ref.rindex("EOF")]
extra = """
@prefix uni: <http://university.org/ontology/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
uni:ProbeU a uni:University ; uni:hasName "Probe U" ; uni:locatedInCountry "IT" .
uni:ProbeD1 a uni:Department ; uni:belongsTo uni:ProbeU . uni:ProbeD2 a uni:Department ; uni:belongsTo uni:ProbeU .
uni:ProbeC1 uni:isTaughtIn uni:ProbeD1 . uni:ProbeC2 uni:isTaughtIn uni:ProbeD2 .
uni:ProbeProf a uni:Person ; uni:hasName "Probe Split" ; uni:role "Professor" ; uni:worksIn uni:ProbeD1, uni:ProbeD2 .
""" + "\n".join(f'uni:PS{i} uni:isEnrolledIn uni:ProbeC{1 if i < 6 else 2} ; uni:hasEnrollmentDate "2024-01-10"^^xsd:date .'
                for i in range(12))
g = rdflib.Graph(); g.parse(f"{TB2}/tests/university_graph_test.ttl"); g.parse(data=extra, format="turtle")
names = {str(r[0]) for r in g.query(ref)}
print("reference returns the split professor:", "Probe Split" in names)
# Per-department version: count students per (professor, department) first.
per_dept = ref.replace("GROUP BY ?professorName\nHAVING(COUNT(DISTINCT ?student) > 10)", "GROUP BY ?professorName")
per_dept = per_dept.replace("?class uni:isTaughtIn ?department .", """{ SELECT ?professor ?department WHERE {
    ?professor uni:worksIn ?department . ?c uni:isTaughtIn ?department . ?s uni:isEnrolledIn ?c ; uni:hasEnrollmentDate ?ed .
    OPTIONAL { ?s uni:hasGraduationDate ?gd }
    FILTER(?ed <= "2025-08-16"^^xsd:date && (!BOUND(?gd) || ?gd > "2025-08-16"^^xsd:date)) }
    GROUP BY ?professor ?department HAVING(COUNT(DISTINCT ?s) > 10) }""")
per_dept = re.sub(r"\n\s*\?student uni:isEnrolledIn \?class ;.*?\)\s*\)\n", "\n", per_dept, flags=re.S)
g2 = rdflib.Graph(); g2.parse(f"{TB2}/tests/university_graph_test.ttl")
assert {str(r[0]) for r in g2.query(per_dept)} == {str(r[0]) for r in g2.query(ref)}, "per-department query must agree on the original data"
print("per-department query returns it:", "Probe Split" in {str(r[0]) for r in g.query(per_dept)})
