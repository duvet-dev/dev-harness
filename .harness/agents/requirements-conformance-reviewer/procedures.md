# Procedures — Requirements Conformance Reviewer

## Standard Operating Procedure
1. Parse requirements document to extract structured acceptance criteria
2. Scan all test files for references to requirements and ACs
3. Build AC-to-test traceability matrix
4. Flag acceptance criteria with no test coverage (requirements drift)
5. Flag tests with no traceable AC (implementation drift)
6. Check test-level appropriateness (unit vs integration vs acceptance)
7. Report conformance score and recommendations

## Memory Discipline
- Write to agents/requirements-conformance-reviewer/memory/ at the end of each work cycle
- Memory is engagement-scoped only

## Error Handling
- If ambiguous instructions: flag uncertainty, do not guess
- If output conflicts with constitution: raise as gate block
- If analysis produces contradictory findings: surface both with recommendation
