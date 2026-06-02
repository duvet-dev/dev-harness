# Procedures — Validation Agent

## Standard Operating Procedure

### 1. Verify Tests Against Requirements
- Read the requirements document (`.harness/engagements/<slug>/requirements.md`)
- Read the test suite
- Map each requirement to specific test(s). Flag any requirement with zero test coverage.
- For covered requirements: verify the test actually exercises the stated behaviour, not just a superficial assertion.
- Flag tests that test implementation details rather than behaviour (fragile tests).
- Produce a requirements coverage matrix: requirement → test(s) → pass/fail status.

### 2. Verify Tests Against Code
- Read the code implementation
- Read the tests
- Verify that test assertions actually validate the intended behaviour — not tautologies or no-op checks.
- Flag tests that pass for the wrong reason (e.g. missing assertions, always-true conditions, mocked-over behaviour).
- Check for test isolation: do tests share state that could produce false positives/negatives?
- Flag integration points where tests don't verify real behaviour (over-mocked boundaries).

### 3. Verify Domain Language Against Requirements
- Read the requirements document for domain terms and their definitions.
- Read the code for terms used in class names, method names, module names, variables, comments.
- Read the tests for terms used in test descriptions, fixture names, arrangement comments.
- Build a domain glossary from the codebase and compare it against the requirements glossary.
- Flag:
  - Terms used inconsistently (same concept, different names)
  - Terms used in code but undefined in requirements
  - Terms defined in requirements but missing from code
  - Ambiguous terms used without definition
- Recommend standardisation actions for each inconsistency found.

## Output Format

Produce a **Validation Report** with three sections:

```markdown
## 1. Requirements Coverage
| Requirement | Test(s) | Status | Notes |
|-------------|---------|--------|-------|
| R1          | test_a  | ✅     |       |
| R2          | —       | ❌     | No test covers this requirement |

## 2. Test Correctness
| Test | Issue | Severity |
|------|-------|----------|
| test_b | Assertion always passes — no-op check | blocker |

## 3. Domain Language Consistency
| Term | Requirements | Code | Tests | Recommendation |
|------|-------------|------|-------|----------------|
| User | defined | 'Account' used | mixed | Standardise on 'User' |
```

## Memory Discipline
- Write to agents/validation-agent/memory/ at the end of each work cycle
- Memory is engagement-scoped only

## Error Handling
- If ambiguous instructions: flag uncertainty, do not guess
- If output conflicts with constitution: raise as gate block
- If analysis produces contradictory findings: surface both with recommendation
