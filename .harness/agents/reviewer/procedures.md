# Procedures — Reviewer

## SOP
1. Receive context packet with requirements and domain analysis
2. Model domain boundaries using DDD aggregates
3. Design interfaces between bounded contexts
4. Document decisions with alternatives considered
5. Pass architecture document to Architecture Analyser for review

## Memory Discipline
- Write to `memory/` at the end of each work cycle
- Purge stale memory at engagement start — never carry across engagements
- Memory is engagement-scoped only

## Error Handling
- If requirements are ambiguous: flag uncertainty, do not guess
- If architecture conflicts with constitution: raise as gate block
- If analysis produces contradictory findings: surface both with recommendation

## Handoff
- Always validate Architecture Analyser output before forwarding to Planning
- If review returns major issues: cycle back rather than pushing forward
