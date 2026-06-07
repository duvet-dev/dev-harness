# Procedures — Research Agent

## Standard Operating Procedure
1. Search codebase for relevant patterns and implementations
2. Gather information from project documentation and config
3. Consult external references when needed
4. Summarise findings in structured format

## Memory Discipline
- Write to agents/research-agent/memory/ at the end of each work cycle
- Memory is engagement-scoped only

## Error Handling
- If ambiguous instructions: flag uncertainty, do not guess
- If output conflicts with constitution: raise as gate block
- If analysis produces contradictory findings: surface both with recommendation
