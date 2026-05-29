"""Analysis agents — LLM-based codebase analysis agents for P1-P5.

Defines AnalysisAgent configurations and the AnalysisAgentRegistry.
Each agent is a language-agnostic LLM analyser that produces structured
JSON output. Extensible: adding P6 means one more agent config.

R22 — Independent Repository Assessment
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AnalysisAgent:
    """Configuration for a single analysis agent.

    Each agent is an LLM-based analyser that assesses a specific
    dimension of a codebase (P1-P5). All analysers are language-agnostic
    — the LLM determines languages, patterns, and quality from context.
    """

    name: str
    """Agent identifier, e.g. 'project-profiler', 'code-critic'."""

    description: str
    """Human-readable description of what this agent evaluates."""

    system_prompt: str
    """System prompt that establishes the agent's role and expertise."""

    output_schema: dict[str, Any] = field(default_factory=dict)
    """JSON Schema describing the expected output structure."""

    model: str = "deepseek-v4-pro"
    """Default model for this agent."""

    temperature: float = 0.3
    """LLM temperature — lower for structured analysis output."""

    timeout: int = 600
    """Timeout in seconds for this agent's execution."""

    agent_role: str = "critical-analyser"
    """Agent role for RepoTool permission lookup. Set to "critical-analyser"
    to enable read-only file access via RepoTool during analysis."""


# P1 — Project Profiler
P1_PROJECT_PROFILER = AnalysisAgent(
    name="project-profiler",
    description=(
        "Scans the filesystem to detect languages, build systems, "
        "frameworks, and project types in each sub-directory."
    ),
    system_prompt=(
        "You are a project profiler. Your job is to analyse a codebase "
        "directory and produce a structured profile of each project it "
        "contains. You are language-agnostic: identify languages, build "
        "systems, frameworks, and project types entirely from file extensions, "
        "config files, imports, and directory structure — do not assume any "
        "default language.\n\n"
        "For each sub-project, determine:\n"
        "1. Primary and secondary languages used\n"
        "2. Build system(s): look for pyproject.toml, Cargo.toml, "
        "package.json, pom.xml, build.gradle, Makefile, CMakeLists.txt, etc.\n"
        "3. Frameworks: look for imports, config files, package manifests\n"
        "4. Project type: API service, CLI tool, library/package, data pipeline, "
        "UI/frontend, config/ops, documentation, monorepo-root workspace config\n\n"
        "Be thorough but practical — don't over-classify config or docs dirs."
    ),
    output_schema={
        "type": "object",
        "properties": {
            "projects": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Project/subdirectory name"},
                        "type": {"type": "string", "enum": [
                            "api-service", "cli-tool", "library", "data-pipeline",
                            "ui-frontend", "config-ops", "documentation",
                            "monorepo-root", "other"
                        ]},
                        "language": {"type": "string"},
                        "secondary_languages": {
                            "type": "array", "items": {"type": "string"}
                        },
                        "build_system": {"type": "string"},
                        "frameworks": {
                            "type": "array", "items": {"type": "string"}
                        },
                        "confidence": {
                            "type": "string", "enum": ["high", "medium", "low"]
                        },
                    },
                    "required": ["name", "type", "language", "confidence"],
                },
            },
            "overview": {
                "type": "object",
                "properties": {
                    "total_projects": {"type": "integer"},
                    "languages_detected": {
                        "type": "array", "items": {"type": "string"}
                    },
                    "total_files_scanned": {"type": "integer"},
                    "notes": {"type": "string"},
                },
            },
        },
        "required": ["projects", "overview"],
    },
)

# P2 — Responsibility Decoder
P2_RESPONSIBILITY_DECODER = AnalysisAgent(
    name="responsibility-decoder",
    description=(
        "Infers the purpose of each project from README files, entry "
        "points, docstrings, and config descriptions."
    ),
    system_prompt=(
        "You are a responsibility decoder. Your job is to infer the "
        "purpose of each project or module in a codebase by analysing "
        "its README, entry points, docstrings, config file descriptions, "
        "file naming patterns, and Docker metadata.\n\n"
        "For each project, determine:\n"
        "1. What does this codebase do? (concise purpose statement)\n"
        "2. Confidence level: high (clear README + entry points), "
        "medium (some documentation, reasonable inference), "
        "low (minimal docs, must infer from structure)\n"
        "3. Key responsibilities (3-5 bullet points)\n\n"
        "Read README first paragraphs carefully. Check __init__.py "
        "docstrings, main() functions, app factories, and config "
        "file descriptions. File naming that follows conventions "
        "(api.py, domain/, models/, handlers/) is a strong signal."
    ),
    output_schema={
        "type": "object",
        "properties": {
            "projects": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "purpose": {"type": "string"},
                        "confidence": {
                            "type": "string", "enum": ["high", "medium", "low"]
                        },
                        "key_responsibilities": {
                            "type": "array", "items": {"type": "string"}
                        },
                        "evidence": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "What files/indicators support the inference",
                        },
                    },
                    "required": ["name", "purpose", "confidence", "key_responsibilities"],
                },
            },
        },
        "required": ["projects"],
    },
)

# P3 — Architecture Critic
P3_ARCHITECTURE_CRITIC = AnalysisAgent(
    name="architecture-critic",
    description=(
        "Assesses design quality, architectural coherence, dependency "
        "direction, coupling, and boundary violations."
    ),
    system_prompt=(
        "You are an architecture critic. Your job is to assess the "
        "architectural quality of a codebase by analysing its directory "
        "structure, module organisation, import/dependency relationships, "
        "and package conventions.\n\n"
        "Evaluate:\n"
        "1. Architecture pattern: layered, hexagonal/ports-and-adapters, "
        "clean, onion, flat, MVC, or unrecognisable\n"
        "2. Dependency direction: does domain/core import from infrastructure? "
        "Are inner layers preserved?\n"
        "3. Coupling: are there excessive cross-module imports? Circular "
        "dependencies?\n"
        "4. Bottleneck modules: modules that too many others depend on\n"
        "5. Boundary violations: domain logic importing from infrastructure, "
        "http, or database layers\n"
        "6. Package structure: does the layout match the expected pattern "
        "for the detected project type?\n"
        "7. Module size: overly large modules that should be split\n"
        "8. Interface segregation: granular enough interfaces or wide-fat patterns?\n"
        "9. **Future-extensibility (MVP Thinking Trap):** does the architecture only "
        "address the minimum current requirements, or has it considered the likely "
        "envelope of future needs? Designs that work for today but are brittle when "
        "extended are a red flag — flag them explicitly. MVP *doing* is good; "
        "MVP *thinking* is bad.\n\n"
        "Base your assessment on the actual directory and import structure "
        "provided. Do not guess. If the architecture is unclear, say so."
    ),
    output_schema={
        "type": "object",
        "properties": {
            "architecture": {
                "type": "object",
                "properties": {
                    "recognised_pattern": {
                        "type": "string",
                        "enum": [
                            "hexagonal", "layered", "clean", "onion",
                            "flat", "mvc", "unrecognisable", "mixed",
                        ],
                    },
                    "confidence": {
                        "type": "string", "enum": ["high", "medium", "low"]
                    },
                    "description": {"type": "string"},
                },
                "required": ["recognised_pattern", "confidence"],
            },
            "dependency_analysis": {
                "type": "object",
                "properties": {
                    "dependency_direction_ok": {"type": "boolean"},
                    "circular_dependencies": {
                        "type": "array", "items": {"type": "string"}
                    },
                    "bottleneck_modules": {
                        "type": "array", "items": {"type": "string"}
                    },
                    "notes": {"type": "string"},
                },
            },
            "boundary_violations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "violator": {"type": "string"},
                        "violation": {"type": "string"},
                        "severity": {
                            "type": "string", "enum": ["critical", "warning", "info"]
                        },
                    },
                },
            },
            "recommendations": {
                "type": "array", "items": {"type": "string"}
            },
            "score": {
                "type": "string", "enum": ["excellent", "good", "fair", "poor"]
            },
        },
        "required": ["architecture", "score"],
    },
)

# P4 — Code Critic
P4_CODE_CRITIC = AnalysisAgent(
    name="code-critic",
    description=(
        "Assesses code quality: SOLID adherence, naming, error handling, "
        "complexity, redundancy, magic values, comment quality, and dead code."
    ),
    system_prompt=(
        "You are a code critic. Your job is to assess code quality at the "
        "source level across an entire codebase. You are language-agnostic "
        "— evaluate based on principles, not specific language idioms.\n\n"
        "Evaluate these dimensions:\n"
        "1. Structure: Single-responsibility indicators — are modules, "
        "classes, and functions reasonably sized? Dependency injection "
        "patterns vs hard-coded instantiation?\n"
        "2. Naming: Consistency (snake_case vs camelCase vs PascalCase), "
        "descriptive vs abbreviated names\n"
        "3. Error handling: Bare excepts, exception swallowing, error "
        "codes vs raising, consistent error type usage\n"
        "4. Complexity: Functions with high branching/deep nesting, "
        "long parameter lists\n"
        "5. Redundancy: Duplicated code blocks, repeated imports, "
        "parallel class hierarchies\n"
        "6. Magic values: Hard-coded strings/numbers that should be "
        "constants or config\n"
        "7. Comments: Stale or misleading comments vs useful docstrings. "
        "Commented-out code (code smell)\n"
        "8. Dead code signals: Unused imports, unused variables/parameters, "
        "orphaned functions\n\n"
        "For each dimension, provide a pass/warn/fail rating with "
        "specific examples from the codebase. Be constructive."
    ),
    output_schema={
        "type": "object",
        "properties": {
            "dimensions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "rating": {
                            "type": "string", "enum": ["pass", "warn", "fail"]
                        },
                        "findings": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "file": {"type": "string"},
                                    "line": {"type": "integer"},
                                    "message": {"type": "string"},
                                    "severity": {
                                        "type": "string",
                                        "enum": ["info", "warning", "error"],
                                    },
                                },
                            },
                        },
                        "recommendation": {"type": "string"},
                    },
                    "required": ["name", "rating", "findings"],
                },
            },
            "overall_rating": {
                "type": "string", "enum": ["excellent", "good", "fair", "poor"]
            },
            "file_count_analysed": {"type": "integer"},
            "recommendations": {
                "type": "array", "items": {"type": "string"}
            },
        },
        "required": ["dimensions", "overall_rating"],
    },
)

# P5 — Test Auditor
P5_TEST_AUDITOR = AnalysisAgent(
    name="test-auditor",
    description=(
        "Analyses the testing posture: test categories, coverage depth, "
        "test quality, isolation, speed, and runnability."
    ),
    system_prompt=(
        "You are a test auditor. Your job is to analyse the testing "
        "posture of a codebase. Evaluate across languages and frameworks.\n\n"
        "Evaluate these dimensions:\n"
        "1. Test categories: Are tests organised into business/feature tests, "
        "integration tests, and unit tests?\n"
        "2. Coverage depth: Beyond simple module coverage — are business "
        "behaviours under test? Or only trivial unit tests?\n"
        "3. Coverage gaps: Critical modules with no tests, uncovered paths\n"
        "4. Test quality indicators: Assertions per test ratio, mocking "
        "overuse (testing mocks, not real behaviour), test naming clarity, "
        "setup complexity\n"
        "5. Test isolation: Do tests share state? Use tmp_path/isolated "
        "filesystems? Any filesystem pollution side effects?\n"
        "6. Test speed: Any obviously slow tests? Are integration/e2e tests "
        "separated from unit tests?\n"
        "7. Test runnability: Can tests be run out of the box? Check for "
        "test config files, conftest.py, pytest.ini, etc.\n\n"
        "Be specific — reference actual test files and patterns found."
    ),
    output_schema={
        "type": "object",
        "properties": {
            "overview": {
                "type": "object",
                "properties": {
                    "total_test_files": {"type": "integer"},
                    "total_test_functions": {"type": "integer"},
                    "test_frameworks_detected": {
                        "type": "array", "items": {"type": "string"}
                    },
                },
                "required": ["total_test_files", "total_test_functions"],
            },
            "test_pyramid": {
                "type": "object",
                "properties": {
                    "unit_tests": {"type": "integer"},
                    "integration_tests": {"type": "integer"},
                    "business_feature_tests": {"type": "integer"},
                    "notes": {"type": "string"},
                },
            },
            "coverage_assessment": {
                "type": "object",
                "properties": {
                    "estimated_coverage_pct": {"type": "number"},
                    "assessment": {
                        "type": "string", "enum": ["excellent", "good", "fair", "poor"]
                    },
                    "critical_gaps": {
                        "type": "array", "items": {"type": "string"}
                    },
                },
                "required": ["estimated_coverage_pct", "assessment"],
            },
            "quality_dimensions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "rating": {
                            "type": "string", "enum": ["pass", "warn", "fail"]
                        },
                        "details": {"type": "string"},
                    },
                    "required": ["name", "rating"],
                },
            },
            "recommendations": {
                "type": "array", "items": {"type": "string"}
            },
        },
        "required": ["overview", "coverage_assessment"],
    },
)




# P6 — Security Auditor
P6_SECURITY_AUDITOR = AnalysisAgent(
    name="security-auditor",
    description=(
        "Scans the codebase for security vulnerabilities: hardcoded secrets, "
        "unsafe subprocess calls, path traversal, eval() usage, SQL injection "
        "risks, and insecure dependencies."
    ),
    system_prompt=(
        "You are a security auditor. Your job is to analyse the codebase for "
        "security vulnerabilities. You are language-agnostic — identify security "
        "issues from file content, not language stereotypes.\n\n"
        "For each security finding, report:\n"
        "1. The exact file path and line number\n"
        "2. The vulnerability type\n"
        "3. The severity (critical, high, medium, low, info)\n"
        "4. A description of why it's a problem\n"
        "5. A concrete remediation suggestion\n\n"
        "Focus on:\n"
        "- Hardcoded API keys, passwords, tokens, secrets in source code\n"
        "- Unsafe subprocess calls (shell=True, command injection)\n"
        "- Path traversal vulnerabilities (user input in file paths)\n"
        "- Use of eval()/exec() with untrusted input\n"
        "- SQL injection risks (string concatenation in queries)\n"
        "- Insecure cryptography (weak algorithms, hardcoded keys)\n"
        "- Command injection via os.system(), subprocess without sanitization\n"
        "- Insecure file permissions\n"
        "- Exposure of internal IPs or infrastructure details\n\n"
        "Be thorough but practical. Prioritise issues that pose real risk.\n"
        "Use the RepoTool (read/list/exists) to inspect specific files as needed."
    ),
    output_schema={
        "type": "object",
        "properties": {
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "file": {"type": "string", "description": "File path"},
                        "line": {"type": "integer", "description": "Line number"},
                        "type": {"type": "string", "enum": [
                            "hardcoded-secret", "unsafe-subprocess", "path-traversal",
                            "eval-exec", "sql-injection", "weak-crypto",
                            "command-injection", "insecure-permissions",
                            "info-leak", "other"
                        ]},
                        "severity": {"type": "string", "enum": ["critical", "high", "medium", "low", "info"]},
                        "description": {"type": "string"},
                        "remediation": {"type": "string"},
                    },
                    "required": ["file", "type", "severity", "description"],
                },
            },
            "summary": {
                "type": "object",
                "properties": {
                    "total_findings": {"type": "integer"},
                    "critical_count": {"type": "integer"},
                    "high_count": {"type": "integer"},
                    "medium_count": {"type": "integer"},
                    "low_count": {"type": "integer"},
                    "overall_risk": {"type": "string", "enum": ["critical", "high", "moderate", "low", "minimal"]},
                },
            },
        },
        "required": ["findings", "summary"],
    },
)

# P7 — Dependency Analyser
P7_DEPENDENCY_ANALYSER = AnalysisAgent(
    name="dependency-analyser",
    description=(
        "Analyses the dependency structure: import graph, circular dependencies, "
        "coupling between modules, and architectural layer violations."
    ),
    system_prompt=(
        "You are a dependency analyst. Your job is to analyse a codebase's "
        "dependency structure and identify architectural issues.\n\n"
        "Analyse from the project's configuration files and source code:\n"
        "1. External dependencies — what libraries/packages are used\n"
        "2. Internal module coupling — which modules depend on which\n"
        "3. Circular dependencies — modules that depend on each other\n"
        "4. Layer violations — code that crosses architectural boundaries\n"
        "5. Dead or unused dependencies\n"
        "6. Tight coupling — modules with too many direct dependencies\n\n"
        "For each issue, report the file path and specific lines involved.\n"
        "Focus on structural health rather than style.\n\n"
        "Use the RepoTool (read/list/exists) to inspect imports, build files, "
        "and module structures as needed."
    ),
    output_schema={
        "type": "object",
        "properties": {
            "external_dependencies": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "version": {"type": "string"},
                        "category": {"type": "string", "enum": ["framework", "library", "tool", "unknown"]},
                        "primary_purpose": {"type": "string"},
                    },
                },
            },
            "circular_dependencies": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "cycle": {"type": "array", "items": {"type": "string"}},
                        "description": {"type": "string"},
                    },
                },
            },
            "coupling_issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "module": {"type": "string"},
                        "type": {"type": "string", "enum": [
                            "layer-violation", "tight-coupling", "circular-dependency",
                            "unused-dependency", "excessive-fan-out", "other"
                        ]},
                        "description": {"type": "string"},
                        "impact": {"type": "string", "enum": ["high", "medium", "low"]},
                    },
                },
            },
            "overall_assessment": {"type": "string"},
        },
        "required": ["external_dependencies", "coupling_issues"],
    },
)

# P8 — Documentation Reviewer
P8_DOCUMENTATION_REVIEWER = AnalysisAgent(
    name="documentation-reviewer",
    description=(
        "Reviews documentation quality: README completeness, docstring coverage, "
        "inline documentation, API docs, and stale or misleading comments."
    ),
    system_prompt=(
        "You are a documentation reviewer. Your job is to assess the quality and "
        "completeness of a codebase's documentation.\n\n"
        "Evaluate:\n"
        "1. README — does it explain what the project is, how to set it up, "
        "how to use it, how to contribute?\n"
        "2. Docstring coverage — what proportion of public APIs have docstrings?\n"
        "3. Inline documentation — are complex sections explained with comments?\n"
        "4. API documentation — is there formal API/interface documentation?\n"
        "5. Stale documentation — comments that contradict the code\n"
        "6. Missing documentation — undocumented public interfaces\n\n"
        "Use the RepoTool (read/list/exists) to inspect specific files.\n"
        "Be constructive — identify what's missing and suggest improvements.\n"
        "Rate each dimension separately."
    ),
    output_schema={
        "type": "object",
        "properties": {
            "ratings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "dimension": {"type": "string", "enum": [
                            "readme", "docstrings", "inline-comments",
                            "api-docs", "accuracy", "overall"
                        ]},
                        "rating": {"type": "string", "enum": ["excellent", "good", "fair", "poor", "missing"]},
                        "details": {"type": "string"},
                    },
                    "required": ["dimension", "rating"],
                },
            },
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": [
                            "missing", "stale", "incorrect", "incomplete", "good", "other"
                        ]},
                        "file": {"type": "string"},
                        "description": {"type": "string"},
                    },
                },
            },
            "recommendations": {
                "type": "array", "items": {"type": "string"},
            },
        },
        "required": ["ratings", "findings"],
    },
)
# P10 — Critical Reviewer (Embedded Crichton)
# Runs after P1-P8, reads their outputs, uses RepoTool for deep file access.
# Catches cross-cutting issues that specialised agents miss.
P10_CRITICAL_REVIEWER = AnalysisAgent(
    name="critical-reviewer",
    description=(
        "Cross-cutting critical reviewer. Reads all other agent outputs, "
        "then browses the codebase via RepoTool to find issues specialised "
        "agents miss: constant duplication, serialisation asymmetry, phantom "
        "roles, contract violations, concurrency gaps, stub implementations, "
        "test quality nuance, and effort estimation."
    ),
    system_prompt=(
        "You are the Critical Reviewer (P10), the final analysis agent. "
        "You have access to:\n"
        "1. The outputs from P1-P8 (preceding analysis agents) — their raw "
        "JSON responses are provided below.\n"
        "2. RepoTool — read(), list(), exists() — any file in the repository.\n"
        "3. The fast scan results (structure, git diff, coverage, dead code).\n\n"
        "Your job is to find what the other agents missed by reading actual "
        "source code and connecting patterns across modules. Be thorough "
        "and specific — reference actual file paths and line numbers.\n\n"
        "## Review Checklist (cross-cutting)\n\n"
        "1. **Duplicated constants** — Same value defined in multiple files "
        "(e.g. paths.py patterns)\n"
        "2. **Serialisation symmetry** — For classes with to_dict()/from_dict(): "
        "do field names match? Any transformed keys?\n"
        "3. **Phantom roles** — Role/type strings in module A that don't exist "
        "as enum members in module B\n"
        "4. **Contract violations** — Abstract interface lifecycle vs "
        "implementation (prepare/run pattern, undocumented status values)\n"
        "5. **Concurrency gaps** — File-based state access without locks "
        "(load→modify→save patterns)\n"
        "6. **Production stubs** — Placeholder implementations in production "
        "code (NotImplementedError, pass-only bodies, pytest.skip() in non-test)\n"
        r"7. **Test quality** — Beyond coverage \%: assertion specificity, "
        "fixture isolation, edge case coverage\n"
        "8. **Version/platform gaps** — EOL Python versions, stale patterns\n"
        "9. **Effort estimation** — Estimate hours to fix each finding\n"
        "10. **YAML/config write safety** — yaml.dump() losing comments "
        "and field ordering\n\n"
        "For each finding, provide:\n"
        "- Category (from checklist above)\n"
        "- File(s) with line numbers\n"
        "- Description (what's wrong and why it matters)\n"
        "- Effort (estimated hours to fix)\n"
        "- Risk (high/medium/low)\n"
        "- Recommendation (specific fix)\n\n"
        "Use RepoTool to read source files. The directory tree is provided "
        "in the context. Browse deeply — the most valuable findings come "
        "from reading actual code, not just the structure.\n\n"
        "Prioritise: focus on findings that P1-P8 would miss. If an issue "
        "is already reported by another agent, don't duplicate it — reference "
        "it and add cross-dimension context instead."
    ),
    output_schema={
        "type": "object",
        "properties": {
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string", "enum": [
                            "duplicated-constants", "serialisation-asymmetry",
                            "phantom-roles", "contract-violation",
                            "concurrency-gap", "production-stub",
                            "test-quality", "version-gap",
                            "yaml-write-safety", "other-cross-cutting"
                        ]},
                        "files": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "File paths involved"
                        },
                        "description": {"type": "string"},
                        "effort_hours": {"type": "number"},
                        "risk": {"type": "string", "enum": ["high", "medium", "low"]},
                        "recommendation": {"type": "string"},
                    },
                    "required": ["category", "description", "effort_hours", "risk"],
                },
            },
            "summary": {
                "type": "object",
                "properties": {
                    "total_findings": {"type": "integer"},
                    "total_effort_hours": {"type": "number"},
                    "fix_immediately": {
                        "type": "array", "items": {"type": "string"},
                        "description": "< 1 hour each, no risk"
                    },
                    "fix_soon": {
                        "type": "array", "items": {"type": "string"},
                        "description": "1-4 hours, low risk"
                    },
                    "design_debt": {
                        "type": "array", "items": {"type": "string"},
                        "description": "4+ hours, needs design discussion"
                    },
                    "leave_alone": {
                        "type": "array", "items": {"type": "string"},
                        "description": "Intentional trade-offs"
                    },
                },
            },
        },
        "required": ["findings", "summary"],
    },
)


class AnalysisAgentRegistry:
    """Registry of all analysis agents (P1-P5).

    Extensible: add a new AnalysisAgent to DEFAULT_AGENTS and it's
    automatically included in all assessments.
    """

    DEFAULT_AGENTS: list[AnalysisAgent] = [
        P1_PROJECT_PROFILER,
        P2_RESPONSIBILITY_DECODER,
        P3_ARCHITECTURE_CRITIC,
        P4_CODE_CRITIC,
        P5_TEST_AUDITOR,
        P6_SECURITY_AUDITOR,
        P7_DEPENDENCY_ANALYSER,
        P8_DOCUMENTATION_REVIEWER,
    ]

    _custom_agents: dict[str, AnalysisAgent] = {}

    @classmethod
    def get_all(cls) -> list[AnalysisAgent]:
        """Return all registered analysis agents (default + custom)."""
        agents = list(cls.DEFAULT_AGENTS)
        agents.extend(cls._custom_agents.values())
        return agents

    @classmethod
    def get(cls, name: str) -> AnalysisAgent | None:
        """Get an agent by name."""
        for agent in cls.get_all():
            if agent.name == name:
                return agent
        return None

    @classmethod
    def register(cls, agent: AnalysisAgent) -> None:
        """Register a custom analysis agent."""
        cls._custom_agents[agent.name] = agent

    @classmethod
    def unregister(cls, name: str) -> None:
        """Remove a custom analysis agent by name."""
        cls._custom_agents.pop(name, None)

    @classmethod
    def reset(cls) -> None:
        """Remove all custom agents."""
        cls._custom_agents.clear()


# P11 — Refactoring & Abstraction Analyser
# Runs after P1-P8 (parallel with P10), reads their outputs, uses RepoTool.
# Philosophy: duplication signals a missing concept. Extract the concept,
# implement once, use everywhere.
P11_REFACTORING_ANALYSER = AnalysisAgent(
    name="refactoring-analyser",
    description=(
        "Refactoring and abstraction analyser. Reads all P1-P8 outputs, "
        "then browses the codebase via RepoTool to identify duplication "
        "patterns, missing abstractions, and concept-extraction "
        "opportunities. Philosophy: duplication signals a missing concept. "
        "Extract the concept, implement once, use everywhere."
    ),
    system_prompt=(
        "You are the Refactoring & Abstraction Analyser (P11). "
        "You have access to:\n"
        "1. The outputs from P1-P8 (preceding analysis agents) — their raw "
        "JSON responses are provided below.\n"
        "2. RepoTool — read(), list(), exists() — any file in the repository.\n"
        "3. The fast scan results (structure, git diff, coverage, dead code).\n\n"
        "Your philosophy: **Duplication is a symptom of a missing concept.**\n"
        "When you see the same code or logic in multiple places, don't just "
        "flag it as duplication — identify the concept that should be "
        "extracted, name it, and propose an abstraction.\n\n"
        "## Analysis Checklist\n\n"
        "1. **Exact code duplication** — Identical code blocks in 90%+ "
        "match across 2+ files. The concept is the operation being performed.\n"
        "2. **Logic duplication (semantic similarity)** — Same algorithm or "
        "pattern in different forms (e.g., same validation across dict and "
        "object inputs). The concept is the transformation being applied.\n"
        "3. **Missing abstraction** — Multiple implementations of the same "
        "idea without a shared interface (e.g., 3 backends all implementing "
        "run() with slightly different signatures). The concept is the "
        "contract between them.\n"
        "4. **Generic implementation opportunity** — Multiple similar "
        "implementations where a single generic version with a type "
        "parameter would work (e.g., WaveCycleRunner + ConsultationCycleRunner). "
        "The concept is the generic process they execute.\n"
        "5. **Boundary clarity** — Concepts that exist but have fuzzy "
        "boundaries (e.g., 'Phase' used as label, container, and execution "
        "stage). The concept needs a clear definition and scope.\n"
        "6. **Cross-module leakage** — Concepts that belong in one module "
        "but are reimplemented/referenced in others (e.g., retry logic in "
        "3 places instead of shared error module). The concept needs a home.\n"
        "7. **Layering violations** — Code that crosses abstraction "
        "boundaries (e.g., business logic directly calling file I/O). "
        "The concept needs proper separation.\n"
        "8. **Generic vs specific trade-off** — Places where generic code "
        "would be slightly more complex but much more reusable. Evaluate "
        "the cost vs benefit of extracting a generic version.\n\n"
        "For each finding, provide:\n"
        "- Type (from checklist above)\n"
        "- Concept name — a descriptive name for the concept being "
        "duplicated or missing\n"
        "- Concept definition — what this concept really represents\n"
        "- File(s) with line numbers for all instances\n"
        "- Code snippet from one instance (representative)\n"
        "- Refactoring proposal — type (extract function/class/module/"
        "interface), proposed name, location, interface signature\n"
        "- Impact — lines removed, complexity reduction, reusability gain\n"
        "- Effort (estimated hours to implement the refactoring)\n"
        "- Risk (high/medium/low)\n"
        "- Recommendation (whether to refactor, and in which phase)\n\n"
        "## Target Architecture\n"
        "After listing all findings, provide a 'Target Architecture' section "
        "describing how the codebase would look if all refactorings were "
        "applied. This should be a high-level overview with module structure, "
        "key interfaces, and expected improvements in maintainability metrics.\n\n"
        "Use RepoTool to read actual source files. The directory tree is "
        "provided in the context. Browse deeply — the most valuable findings "
        "come from reading code that looks different on the surface but "
        "implements the same concept.\n\n"
        "Avoid duplicating findings already reported by P10 (P10 covers "
        "constant duplication, phantom roles, concurrency gaps, etc). "
        "P11 focuses on semantically deeper abstractions: missing interfaces, "
        "generic refactoring opportunities, and architectural evolution. "
        "If P10 already flagged a constant, don't flag it again — but do "
        "flag if the pattern suggests a broader design concept."
    ),
    output_schema={
        "type": "object",
        "properties": {
            "refactorings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": [
                            "exact_duplication", "logic_duplication",
                            "missing_abstraction", "generic_opportunity",
                            "boundary_clarity", "cross_module_leakage",
                            "layering_violation", "generic_tradeoff"
                        ]},
                        "concept_name": {"type": "string",
                            "description": "Name for the concept being duplicated/missing"
                        },
                        "concept_definition": {"type": "string",
                            "description": "What this concept really represents"
                        },
                        "instances": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "file": {"type": "string"},
                                    "lines": {"type": "string"},
                                    "location": {"type": "string",
                                        "description": "Class/function name"
                                    },
                                    "description": {"type": "string",
                                        "description": "How this instance implements the concept"
                                    },
                                },
                                "required": ["file"],
                            },
                        },
                        "refactoring_proposal": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string", "enum": [
                                    "extract_function", "extract_class",
                                    "extract_module", "extract_interface",
                                    "consolidate_definition",
                                    "introduce_abstraction"
                                ]},
                                "name": {"type": "string",
                                    "description": "Proposed abstraction name"
                                },
                                "location": {"type": "string",
                                    "description": "Where to place the abstraction"
                                },
                                "interface": {"type": "string",
                                    "description": "Method/function signatures"
                                },
                                "description": {"type": "string",
                                    "description": "How to implement and use it"
                                },
                            },
                            "required": ["type", "name"],
                        },
                        "impact": {
                            "type": "object",
                            "properties": {
                                "lines_removed": {"type": "integer"},
                                "duplication_eliminated": {"type": "boolean"},
                                "reusability_gain": {"type": "string"},
                                "complexity_reduction": {"type": "string"},
                            },
                        },
                        "effort_hours": {"type": "number"},
                        "risk": {"type": "string", "enum": ["high", "medium", "low"]},
                        "recommendation": {"type": "string"},
                    },
                    "required": ["type", "concept_name", "instances", "refactoring_proposal", "effort_hours", "risk"],
                },
            },
            "target_architecture": {
                "type": "object",
                "properties": {
                    "description": {"type": "string",
                        "description": "High-level overview of the target architecture"
                    },
                    "module_structure": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Proposed module/package layout"
                    },
                    "key_interfaces": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Key interfaces/protocols to introduce"
                    },
                    "expected_improvements": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
            "summary": {
                "type": "object",
                "properties": {
                    "total_refactorings": {"type": "integer"},
                    "total_effort_hours": {"type": "number"},
                    "estimated_lines_removed": {"type": "integer"},
                    "quick_wins": {
                        "type": "array", "items": {"type": "string"},
                        "description": "< 2 hours each, clear concept to extract"
                    },
                    "high_impact": {
                        "type": "array", "items": {"type": "string"},
                        "description": "2-8 hours, structural improvement"
                    },
                    "architectural_change": {
                        "type": "array", "items": {"type": "string"},
                        "description": "8+ hours, requires design discussion"
                    },
                },
            },
        },
        "required": ["refactorings", "summary"],
    },
)


# P10 and P11 are NOT registered in DEFAULT_AGENTS or as custom — they run
# after P1-P8 complete and are wired directly into assess(). Use the
# P10_CRITICAL_REVIEWER / P11_REFACTORING_ANALYSER constants for imports;
# registry.get_all() intentionally excludes them.
