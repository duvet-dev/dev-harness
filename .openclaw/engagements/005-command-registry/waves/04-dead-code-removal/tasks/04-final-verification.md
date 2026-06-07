# Task 4 — Final cleanup grep + full test suite

**Status:** 📋 Pending
**Wave:** 04-dead-code-removal
**Dependencies:** Tasks 1-3
**Effort:** 0.5h

## Description

Final sweep: verify no stale references remain anywhere in the codebase, full test suite passes, and all 4 sync tests validate the integrity of the new registration system.

## Acceptance Criteria

- [x] `grep -rn "ResumeEngagement" src/` → zero hits
- [x] `grep -rn "CreateWaveCommand\|CreateWaveTypedHandler" src/` → zero hits (excluding CreateWaveFrom*, CreateWavesFrom* which are valid)
- [x] `grep -rn "ExecuteStepCommand\|ExecuteStepTypedHandler" src/` → zero hits
- [x] `grep -rn "COMMAND_TYPES" src/` → zero hits (old static dict)
- [x] `grep -rn "CreateWaveResult\|ExecuteStepResult\|ResumeEngagementResult" src/` → zero hits
- [x] Full test suite passes: `python -m pytest -q`
- [x] All 4 sync tests pass: `python -m pytest tests/unit/command/test_registration.py -v`
- [x] REPL can start and handle dispatch: `echo "/help" | python -m harness shell`
- [x] CLI `--help` still works: `python -m harness --help`
- [x] Click-only commands show "CLI only" message: `echo "/engagement list" | python -m harness shell 2>&1 | grep "CLI only"`
- [x] Bus-dispatchable commands still work: `echo "/status" | python -m harness shell`

## Files Affected

- (verification only — no file changes)

## Verification

```bash
echo "=== Dead Code Check ==="
for pattern in 'ResumeEngagement' 'CreateWaveCommand[^F]' 'CreateWaveTypedHandler' 'ExecuteStepCommand' 'ExecuteStepTypedHandler' 'COMMAND_TYPES' 'CreateWaveResult' 'ExecuteStepResult' 'ResumeEngagementResult'; do
    hits=$(grep -rn "$pattern" src/ 2>/dev/null | wc -l)
    if [ "$hits" -eq "0" ]; then
        echo "✓ No hits for: $pattern"
    else
        echo "✗ HITS for $pattern:"
        grep -rn "$pattern" src/
    fi
done

echo ""
echo "=== Sync Tests ==="
python -m pytest tests/unit/command/test_registration.py -v

echo ""
echo "=== Full Test Suite ==="
python -m pytest -q

echo ""
echo "=== REPL Smoke Test ==="
echo "/help" | python -m harness shell 2>&1 | head -20
echo "/exit" | python -m harness shell 2>&1

echo ""
echo "=== CLI Smoke Test ==="
python -m harness --help 2>&1 | head -10
```
