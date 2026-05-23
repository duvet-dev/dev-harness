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
        "8. Interface segregation: granular enough interfaces or wide-fat patterns?\n\n"
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
