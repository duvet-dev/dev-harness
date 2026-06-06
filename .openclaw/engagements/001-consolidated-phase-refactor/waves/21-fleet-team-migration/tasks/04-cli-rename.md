# Task 4 — Rename CLI fleet group → team

**Status:** ✅ Complete
**Wave:** 21-fleet-team-migration
**Dependencies:** None
**Effort:** 1-2h

## Description

Rename the CLI `fleet` Click group to `team` with 6 subcommands. Update all exports in `cli/__init__.py`.

## Acceptance Criteria

- [x] `def fleet():` → `def team():` with updated help text
- [x] 6 subcommands renamed: list, show, add-agent, remove-agent, consult, set-governance
- [x] All exports in `cli/__init__.py` updated
- [x] Subcommand logic reviewed for team model compatibility

## Files Affected

- `src/harness/cli/main.py`
- `src/harness/cli/__init__.py`

## Verification

`python -m harness.cli.main team --help` → shows team commands
`python -m harness.cli.main fleet --help 2>&1` → "No such command"
`grep "@fleet\|@harness\.cli" src/harness/cli/main.py` → zero hits for fleet
