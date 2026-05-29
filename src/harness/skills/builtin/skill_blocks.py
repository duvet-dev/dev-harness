"""Pre-defined static skill content blocks — V7 §7.

Each skill is a static content block injected into agent prompts.
These are simple strings with no Jinja2 templating (dynamic injection
deferred to a later wave).
"""

from __future__ import annotations

from harness.skills.step import SkillStep


def get_builtin_skills() -> list[SkillStep]:
    """Return the pre-defined built-in skills.

    Returns:
        List of SkillStep objects for built-in skills.
    """
    return [
        SkillStep(
            skill_name="web-search",
            skill_type="tool",
            description="Search the web for documentation, patterns, "
            "and solutions",
            content=(
                "--- Web Search Skill ---\n"
                "You have access to a web search tool. You can search "
                "the web for documentation, code patterns, best "
                "practices, and current reference information.\n"
                "Use this skill when:\n"
                "- You need library or framework documentation\n"
                "- You need to verify facts against current sources\n"
                "- You need code examples or patterns\n"
                "- The user asks you to research a topic\n"
                "\n"
                "Invoke the web search tool with a clear, specific "
                "query. For complex topics, use multiple targeted "
                "queries rather than one broad search.\n"
                "--- End Web Search Skill ---"
            ),
        ),
        SkillStep(
            skill_name="code-review",
            skill_type="knowledge",
            description="Code review guidelines and best practices",
            content=(
                "--- Code Review Skill ---\n"
                "When reviewing code, check for:\n"
                "1. Correctness — does the code do what it claims?\n"
                "2. Edge cases — are input boundaries, error states, "
                "and empty/null cases handled?\n"
                "3. Type safety — are types correct and consistent?\n"
                "4. Performance — are there obvious inefficiencies?\n"
                "5. Security — are there injection risks, secret "
                "leaks, or unsafe patterns?\n"
                "6. Style — does it follow the project conventions?\n"
                "7. Maintainability — is it readable and well-named?\n"
                "8. Testing — are there tests for the new code?\n"
                "\n"
                "For each finding, classify as: BLOCKER, MAJOR, "
                "MINOR, or STYLE.\n"
                "--- End Code Review Skill ---"
            ),
            agents=[
                "coding-agent",
                "critical-analyser",
                "testing-agent",
                "review-coordinator",
                "architecture-critic",
                "code-critic",
                "security-critic",
            ],
        ),
        SkillStep(
            skill_name="test-writing",
            skill_type="knowledge",
            description="Test writing guidelines and patterns",
            content=(
                "--- Test Writing Skill ---\n"
                "When writing tests, follow these guidelines:\n"
                "1. Test behaviour, not implementation\n"
                "2. One logical assertion per test\n"
                "3. Use descriptive test names (test_<behaviour>)\n"
                "4. Arrange-Act-Assert structure\n"
                "5. Test edge cases: empty, null, error states\n"
                "6. Test the happy path\n"
                "7. Use fixtures for shared setup\n"
                "8. Aim for 95% coverage on new code\n"
                "\n"
                "For unit tests, mock external dependencies. For "
                "integration tests, use real instances where "
                "practical.\n"
                "--- End Test Writing Skill ---"
            ),
            agents=[
                "testing-agent",
                "coding-agent",
                "test-coverage-analyser",
            ],
        ),
        SkillStep(
            skill_name="architecture-review",
            skill_type="knowledge",
            description="Architecture review guidelines",
            content=(
                "--- Architecture Review Skill ---\n"
                "When reviewing architecture, evaluate:\n"
                "1. Separation of concerns — are responsibilities "
                "cleanly divided?\n"
                "2. Coupling — are components loosely coupled?\n"
                "3. Cohesion — are related things grouped together?\n"
                "4. SOLID principles — single responsibility, "
                "open/closed, Liskov, interface segregation, "
                "dependency inversion\n"
                "5. Domain-driven design — does the model reflect "
                "the problem domain?\n"
                "6. Scalability — will the design handle growth?\n"
                "7. Security — are trust boundaries clearly defined?\n"
                "8. Testability — can components be tested in "
                "isolation?\n"
                "\n"
                "Flag any deviation from the project's stated "
                "architecture principles.\n"
                "--- End Architecture Review Skill ---"
            ),
            agents=[
                "architect",
                "architecture-critic",
                "critical-analyser",
                "review-coordinator",
                "design-reviewer",
            ],
        ),
    ]
