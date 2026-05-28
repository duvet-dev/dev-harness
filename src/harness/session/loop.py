"""Interactive terminal loops — chat and phase-by-phase sessions.



Provides:

- ``chat_loop`` — simple interactive chat with an LLM

- ``session_loop`` — orchestrated phase-by-phase agent interaction

"""



from __future__ import annotations



import logging

import re

import sys

from datetime import datetime, timezone



logger = logging.getLogger(__name__)

from pathlib import Path

from typing import Any, Optional



import click



from harness.paths import get_providers_path

from harness.session.commands import route_chat_command, route_session_command

from harness.session.client import (

    ChatMessage,

    ChatTranscript,

    SessionClient,

    resolve_provider,

)



# ── Enable readline line editing (word-jump with Alt+arrows, etc.) ────────



try:

    import readline



    # Standard Emacs word-jump keys work on most terminals with Meta

    readline.parse_and_bind('"\\eb": backward-word')

    readline.parse_and_bind('"\\ef": forward-word')



    # Support common macOS/iTerm2 Alt+arrow sequences

    for seq, action in [

        ("\\e[1;3D", "backward-word"),   # Alt+Left

        ("\\e[1;3C", "forward-word"),    # Alt+Right

        ("\\e[1;5D", "backward-word"),   # Ctrl+Left

        ("\\e[1;5C", "forward-word"),    # Ctrl+Right

    ]:

        try:

            readline.parse_and_bind(f'"{seq}": {action}')

        except Exception:

            pass



    # Home/End

    readline.parse_and_bind('"\\e[H": beginning-of-line')

    readline.parse_and_bind('"\\e[F": end-of-line')

    # Ctrl+A / Ctrl+E fallback (already native in most terminals)

    readline.parse_and_bind('"\\e[7~": beginning-of-line')  # xterm home

    readline.parse_and_bind('"\\e[8~": end-of-line')        # xterm end

except ImportError:

    pass  # No readline (Windows) — basic input() still works





# ── Provider listing and switching helpers ─────────────────────────────────



def list_providers(root: Path) -> list[dict[str, Any]]:

    """Read ``.harness/providers.yaml`` and return a list of available providers.



    Each entry contains:

    - ``name`` — provider key in the YAML

    - ``type`` — backend type (e.g. openai-compatible, openai, anthropic)

    - ``model`` — default model name, or empty string

    - ``aliases`` — dict of model aliases (e.g. ``{"fast": "gpt-4o-mini"}``)

    """

    import yaml



    local_path = get_providers_path(root)

    if not local_path.is_file():

        return []



    config = yaml.safe_load(local_path.read_text()) or {}

    providers = config.get("providers", {}) or {}



    result: list[dict[str, Any]] = []

    for name, prov in providers.items():

        entry: dict[str, Any] = {

            "name": name,

            "type": prov.get("type", ""),

            "model": "",

            "aliases": {},

        }

        models = prov.get("models", {})

        if isinstance(models, dict):

            entry["model"] = models.get("default", "")

            entry["aliases"] = {

                k: v for k, v in models.items() if k != "default"

            }

        elif isinstance(models, list) and models:

            first = models[0]

            if isinstance(first, dict):

                entry["model"] = first.get("name", "")

        result.append(entry)



    return result





def switch_provider(

    root: Path,

    provider_name: str,

    model_alias: str | None = None,

) -> dict[str, Any] | None:

    """Resolve a new provider config and return connection settings.



    Returns None if the provider is not found.  If *model_alias* is

    given, resolves the alias to a concrete model name from the

    provider's ``models`` map.

    """

    import yaml



    local_path = get_providers_path(root)

    if not local_path.is_file():

        return None



    config = yaml.safe_load(local_path.read_text()) or {}

    providers = config.get("providers", {}) or {}

    prov = providers.get(provider_name)

    if not prov:

        return None



    # Resolve model

    raw_models = prov.get("models", {})

    if isinstance(raw_models, dict):

        models = raw_models

        model = models.get("default", "")

    elif isinstance(raw_models, list) and raw_models:

        first = raw_models[0]

        models = {}

        model = first.get("name", "") if isinstance(first, dict) else ""

    else:

        models = {}

        model = ""

    if model_alias and isinstance(models, dict) and model_alias in models:

        model = models[model_alias]



    # Build resolved config

    from harness.session.client import resolve_env_vars



    resolved: dict[str, Any] = {

        "name": provider_name,

        "api_key": resolve_env_vars(str(prov.get("api_key", ""))),

        "base_url": resolve_env_vars(str(prov.get("base_url", ""))),

        "type": prov.get("type", "openai-compatible"),

        "model": model,

    }

    return resolved





def format_providers_table(

    providers: list[dict[str, Any]],

    current: str = "",

) -> str:

    """Format a human-readable table of available providers."""

    lines: list[str] = []

    lines.append(f"  {'Provider':<16} {'Type':<22} {'Default Model':<30}")

    lines.append(f"  {'-'*16} {'-'*22} {'-'*30}")

    for p in providers:

        marker = "*" if p["name"] == current else " "

        lines.append(

            f"  {marker} {p['name']:<14} {p['type']:<22} {p['model']:<30}"

        )

        # Show aliases

        for alias, model_name in p["aliases"].items():

            lines.append(

                f"       alias ~{alias} -> {model_name}"

            )

    return "\n".join(lines)





# ── Phase definitions ──────────────────────────────────────────────────────



PHASES = [

    {

        "name": "requirements",

        "title": "Requirements Gathering",

        "agent": "requirements-builder",

        "fleets": ["discovery"],

        "artifact": "requirements.md",

        "prompt": (

            "You are a **Requirements Builder**. You are in the REQUIREMENTS "

            "phase of a development engagement.\n\n"

            "YOUR JOB:\n"

            "- Help the user clarify and document what needs to be built\n"

            "- Ask questions to surface edge cases, constraints, and unknowns\n"

            "- Produce structured requirements output when asked\n"

            "- Suggest a document structure: goals, scope, functional reqs, "

            "non-functional reqs, constraints, assumptions, open questions\n\n"

            "YOUR BOUNDARIES (stay in your lane):\n"

            "- Do NOT write any code, even if asked\n"

            "- Do NOT propose architectures, designs, or implementations\n"

            "- Do NOT research technologies or patterns\n"

            "- If asked for code, redirect: \"We're still in requirements -- "

            "let's finalise what needs building first.\"\n\n"

            "OUTPUT FORMAT:\n"

            "Present requirements in structured Markdown with clear sections. "

            "If the user asks you to write files, prefix each file with "

            "a heading like:\n"

            "    ## File: docs/requirements.md\n"

            "Use the RepoTool to write files directly. Format as\n"

            "## File: docs/requirements.md\n... and run /apply."

        ),

    },

    {

        "name": "research",

        "title": "Research & Analysis",

        "agent": "researcher",

        "fleets": ["discovery"],

        "artifact": "research.md",

        "prompt": (

            "You are a **Researcher**. You are in the RESEARCH phase of a "

            "development engagement.\n\n"

            "YOUR JOB:\n"

            "- Gather knowledge about technologies, patterns, approaches\n"

            "- Identify risks, trade-offs, and unknowns\n"

            "- Provide research briefs with competing options and pros/cons\n"

            "- Challenge assumptions and suggest alternatives\n\n"

            "YOUR BOUNDARIES (stay in your lane):\n"

            "- Do NOT write any code\n"

            "- Do NOT propose specific architectures or designs\n"

            "- Do NOT write requirements -- that phase is done\n"

            "- If asked to design, redirect: \"Let's finalise research first "

            "before locking in an architecture.\"\n\n"

            "OUTPUT FORMAT:\n"

            "Structured sections covering researched areas, findings, risks, "

            "and recommendations. If asked to write files, prefix each with:\n"

            "    ## File: path/to/research-finding.md\n"

            "Use the RepoTool to write research findings directly."

        ),

    },

    {

        "name": "design",

        "title": "Architecture & Design",

        "agent": "architect",

        "fleets": ["architecture"],

        "artifact": "design.md",

        "prompt": (

            "You are a **Software Architect**. You are in the DESIGN phase "

            "of a development engagement.\n\n"

            "YOUR JOB:\n"

            "- Model the domain: aggregates, entities, value objects\n"

            "- Define bounded contexts and context maps\n"

            "- Select architectural patterns with trade-off explanations\n"

            "- Produce interface contracts, data models, component structures\n"

            "- Use ADRs (Architecture Decision Records) where appropriate\n"

            "- **Create project-level architecture documents** -- these should\n"

            "  go in sensible locations in the project (e.g. `docs/arch/`)\n\n"

            "YOUR BOUNDARIES (stay in your lane):\n"

            "- Do NOT write production code (pseudocode / contracts are OK)\n"

            "- Do NOT implement business logic\n"

            "- Do NOT write tests (but make testing strategy clear)\n"

            "- If asked to implement, redirect: \"Let's lock the architecture "

            "first, then implement in the next phase.\"\n\n"

            "OUTPUT FORMAT WITH FILE WRITING:\n"

            "When proposing architecture documents, ADRs, or data models, "

            "format each file with a heading like:\n"

            "    ## File: docs/arch/001-adr-architecture.md\n"

            "Use the RepoTool to write design documents directly.\n"

            "You can propose multiple files in a single response."

            "Always write rather than asking the user to copy-paste."

        ),

    },

    {

        "name": "planning",

        "title": "Planning & Task Decomposition",

        "agent": "planning-agent",

        "fleets": ["planning"],

        "artifact": "plan.md",

        "prompt": (

            "You are a **Planning Agent**. You are in the PLANNING phase "

            "of a development engagement.\n\n"

            "YOUR JOB:\n"

            "- Take the architecture/design artifacts and decompose them into "

            "independently-buildable chunks of work\n"

            "- Determine dependency order — produce a DAG of work items\n"

            "- Estimate effort per task (small/medium/large)\n"

            "- Flag oversized or undersized work items that need splitting or "

            "batching\n"

            "- Assign agent roles to each work item (e.g. coder, tester)\n"

            "- Identify risky items that benefit from early prototyping or "

            "spiking\n"

            "- Suggest a wave/iteration strategy — what order to build things "

            "in and how to validate incrementally\n\n"

            "YOUR BOUNDARIES (stay in your lane):\n"

            "- Do NOT write any code\n"

            "- Do NOT redesign the architecture — plan around what's been "

            "decided\n"

            "- Do NOT rewrite requirements or design docs\n"

            "- If you spot a design gap, flag it as a risk — don't redesign "

            "it yourself\n"

            "- If asked to implement, redirect: \"Let's get the plan right "

            "first so implementation knows what to build.\"\n\n"

            "OUTPUT FORMAT:\n"

            "Write a structured plan to a file using the RepoTool. Use "

            "sections:\n"

            "    ## Wave / Iteration {N}: {title}\n"

            "    - **Dependencies:** {dep list}\n"

            "    - **Tasks:** {numbered list with per-task details}\n"

            "    - **Assigned to:** {agent role}\n"

            "    - **Risk level:** {low/medium/high}\n"

            "    - **Estimated effort:** {S/M/L}\n\n"

            "Include a dependency graph (text-based) and note any sequencing "

            "constraints. Suggest where validation checkpoints should go (e.g. "

            "(e.g. after wave 2, run tests before starting wave 3)."

        ),

    },

    {

        "name": "implementation",

        "title": "Implementation",

        "agent": "coder",

        "fleets": ["coding"],

        "artifact": "implementation.md",

        "prompt": (

            "You are a **Coder**. You are in the IMPLEMENTATION phase of a "

            "development engagement.\n\n"

            "YOUR JOB:\n"

            "- Implement features following the established architecture\n"

            "- Write tests alongside implementation (TDD if possible)\n"

            "- Produce clean, well-structured code\n"

            "- Follow the project's coding conventions\n"

            "- **Write actual files to the project** -- not just terminal output\n\n"

            "YOUR BOUNDARIES (stay in your lane):\n"

            "- Do NOT redesign the architecture -- follow what was decided\n"

            "- Do NOT rewrite requirements or design docs\n"

            "- If you discover a design gap, flag it -- don't redesign alone\n"

            "- Stay focused on the current implementation task\n\n"

            "OUTPUT FORMAT WITH FILE WRITING:\n"

            "When writing code, format each file with:\n"

            "    ## File: src/path/to/file.py\n"

            "    ```python\n"

            "    def hello():\n"

            "        pass\n"

            "    ```\n"

            "You can also use:\n"

            "    # src/path/to/file.py\n"

            "    (as the first line inside a fenced code block)\n\n"

            "Always write full, complete files with the RepoTool.\n"

            "Create all necessary supporting files (init files, config,"

            "etc.). Read existing files first to understand the codebase."

        ),

    },

    {

        "name": "testing",

        "title": "Testing & Validation",

        "agent": "tester",

        "fleets": ["testing", "validation"],

        "artifact": "testing.md",

        "prompt": (

            "You are a **Tester**. You are in the TESTING phase of a "

            "development engagement.\n\n"

            "YOUR JOB:\n"

            "- Validate implementations against acceptance criteria\n"

            "- Identify test scenarios (happy path, edge cases, errors)\n"

            "- Write unit, integration, and acceptance tests\n"

            "- Report test results and coverage gaps\n\n"

            "YOUR BOUNDARIES (stay in your lane):\n"

            "- Do NOT change implementation code to fix bugs -- report them\n"

            "- Do NOT redesign or refactor\n"

            "- Do NOT write requirements or feature specs\n"

            "- If you find a bug: describe expected, actual, and reproduction\n\n"

            "OUTPUT FORMAT WITH FILE WRITING:\n"

            "When writing test files, format each with:\n"

            "    ## File: tests/test_feature.py\n"

            "    ```python\n"

            "    def test_something():\n"

            "        pass\n"

            "    ```\n"

            "Use the RepoTool to write test files directly."

        ),

    },

    {

        "name": "review",

        "title": "Review & Polish",

        "agent": "reviewer",

        "fleets": ["review", "validation"],

        "artifact": "review.md",

        "prompt": (

            "You are a **Reviewer**. You are in the REVIEW phase of a "

            "development engagement.\n\n"

            "YOUR JOB:\n"

            "- Review the current state against best practices\n"

            "- Identify issues: correctness, completeness, consistency, "

            "security, performance\n"

            "- Suggest concrete, actionable improvements\n"

            "- Assess whether the engagement is ready to close\n\n"

            "YOUR BOUNDARIES (stay in your lane):\n"

            "- Do NOT write new code or designs\n"

            "- Do NOT redo requirements -- review, don't rework\n"

            "- Do NOT implement improvements yourself -- describe them\n"

            "- Be constructive: identify what's good AND what needs work\n\n"

            "OUTPUT FORMAT:\n"

            "Structured review findings with severity (blocker/major/minor/"

            "suggestion), location references, and recommended actions."

        ),

    },

]





# ── Get-Well phases (assessment-driven remediation session) ───────────────



def _build_get_well_phase_list() -> list[dict]:
    """Build the phase list for a get-well remediation session.

    Prepends assessment-triage and remediation-design phases to the
    standard phase pipeline (planning through review for execution).
    """
    reph = {
        "name": "assessment-triage",
        "title": "Assessment Triage & Finding Prioritisation",
        "agent": "triage-agent",
        "fleets": ["discovery"],
        "artifact": "triage.md",
        "prompt": (
            "You are an **Assessment Triage Agent**. You are in the ASSESSMENT TRIAGE "
            "phase of a get-well remediation session.\n\n"
            "YOUR JOB:\n"
            "- Load and review the latest assessment findings\n"
            "- Categorise findings by effort, impact, and dependency\n"
            "- Produce a triage table: finding ID, severity, category, "
            "estimated effort (S/M/L), impact score, dependency order\n"
            "- Highlight quick wins (low effort, high impact) vs "
            "multi-wave efforts\n"
            "- Group related findings into themes or work-streams\n"
            "- Suggest an execution order \u2014 what to fix first, what can wait\n\n"
            "YOUR BOUNDARIES:\n"
            "- Do NOT write any code\n"
            "- Do NOT design remediation solutions \u2014 only categorise and prioritise\n"
            "- Do NOT implement fixes \u2014 your output feeds the next phase\n\n"
            "OUTPUT FORMAT:\n"
            "Write a structured triage document using the RepoTool. Use sections:\n"
            "    ## Finding Summary\n"
            "    ## Themes / Work-Streams\n"
            "    ## Priority Matrix (Effort vs Impact)\n"
            "    ## Execution Order Recommendation\n"
            "    ## Quick Wins\n\n"
            "Reference findings by their ID (e.g. finding-001) and include "
            "severity and category in the triage table."
        ),
    }

    remph = {
        "name": "remediation-design",
        "title": "Remediation Design & Plan",
        "agent": "architect",
        "fleets": ["architecture", "planning"],
        "artifact": "remediation-plan.md",
        "prompt": (
            "You are a **Remediation Architect**. You are in the REMEDIATION DESIGN "
            "phase of a get-well remediation session.\n\n"
            "YOUR JOB:\n"
            "- Design a cohesive remediation plan from the triaged assessment findings\n"
            "- For each finding theme or work-stream, produce:\n"
            "    * The remediation approach (refactor, rewrite, extract, etc.)\n"
            "    * Key design decisions (as ADRs where appropriate)\n"
            "    * Dependencies between remediation work-streams\n"
            "    * Risk assessment for each approach\n"
            "- Consider architectural coherence \u2014 don\'t fix findings in isolation;\n"
            "  ensure the overall architecture improves\n"
            "- Define acceptance criteria for when a finding is considered resolved\n"
            "- Decompose the work into waves (PR-sized units) with dependencies\n"
            "- Assign agent roles to each wave\n\n"
            "YOUR BOUNDARIES:\n"
            "- Do NOT implement any code \u2014 design only\n"
            "- Do NOT write tests \u2014 define testing strategy\n"
            "- Do NOT re-triage \u2014 use the triage output from the previous phase\n"
            "- If you discover a new finding, add it to the triage doc instead\n\n"
            "OUTPUT FORMAT:\n"
            "Write a structured remediation plan using the RepoTool. Use sections:\n"
            "    ## Overview & Strategy\n"
            "    ## Work-Stream: {name}\n"
            "      ### Approach\n"
            "      ### Design Decisions\n"
            "      ### Dependencies\n"
            "      ### Risk\n"
            "      ### Acceptance Criteria\n"
            "    ## Wave Breakdown\n"
            "      Wave {N}: {title} \u2014 {agent role} \u2014 {est effort}\n"
            "    ## Execution Order\n"
            "    ## Testing Strategy\n"
            "    ## Success Metrics\n\n"
            "Use ADRs (Architecture Decision Records) in `docs/arch/` to capture "
            "key design choices."
        ),
    }

    # Start with get-well phases, then append standard phases
    result = [reph, remph]

    # Append standard phases (from PLANNING onward)
    for p in PHASES:
        if p["name"] in ("planning", "implementation", "testing", "review"):
            result.append(p)

    return result



# ── File block extraction (for /apply command) ────────────────────────────



_FILE_HEADING_PATTERN = re.compile(r"^#{1,3} +File: +(.+)$", re.MULTILINE)

_IMPLICIT_PATH_PATTERN = re.compile(

    r"^(?://|#) +([\w./\\-]+\.\w+)\s*$", re.MULTILINE

)





def _extract_file_blocks(text: str) -> dict[str, str]:

    """Extract ``## File: path`` blocks and annotated code blocks from text.



    Supports these formats:



    1. **File heading blocks** — a heading like ``## File: path/to/file``

       followed by content until the next heading or end of text.



    2. **Annotated code blocks** — a fenced code block (```...```) where the

       first content line is ``// path/to/file`` or ``# path/to/file``.



    Returns a dict mapping file paths to their content.

    """

    files: dict[str, str] = {}



    # Pattern 1: ## File: path heading blocks

    # Split by headings, process each block

    parts = _FILE_HEADING_PATTERN.split(text)

    # parts[0] is text before first match

    # Then pairs of (path, content) for each match

    for i in range(1, len(parts), 2):

        if i + 1 >= len(parts):

            break

        path = parts[i].strip()

        content_block = parts[i + 1]

        # Strip trailing content up to the next heading

        # (the regex only matches our File: headings, so other headings are fine)

        files[path] = content_block.strip()



    # Pattern 2: Annotated fenced code blocks

    # Look for ```...``` blocks where first content line is a path comment

    code_block_pattern = re.compile(

        r"```(?:\w+)?\s*\n(.+?)```", re.DOTALL

    )

    for match in code_block_pattern.finditer(text):

        content = match.group(1).strip()

        lines = content.split("\n")

        first_line = lines[0].strip()

        path_match = _IMPLICIT_PATH_PATTERN.match(first_line)

        if path_match:

            path = path_match.group(1).strip()

            file_content = "\n".join(lines[1:]).strip()

            # Only add if not already captured via heading pattern

            if path not in files:

                files[path] = file_content



    return files





def _apply_file_blocks(root: Path, text: str) -> list[tuple[str, str]]:

    """Extract files from ``text`` and write them under ``root``.



    Returns a list of ``(path, status)`` tuples where status is

    ``"created"``, ``"overwritten"``, or ``"error: ..."``.

    """

    files = _extract_file_blocks(text)

    results: list[tuple[str, str]] = []

    for filepath, content in files.items():

        # Security: reject absolute paths and path traversal attempts

        clean = filepath.removeprefix("./").removeprefix(".\\").strip()

        if clean.startswith("/") or ".." in Path(clean).parts:

            results.append((filepath, "error: path rejected (absolute or traversal)"))

            continue

        full_path = (root / clean).resolve()

        # Ensure it's still under root (resolve symlinks)

        root_resolved = root.resolve()

        if not str(full_path).startswith(str(root_resolved)):

            results.append(

                (filepath, "error: path escapes project root")

            )

            continue



        status = "created"

        if full_path.exists():

            status = "overwritten"



        full_path.parent.mkdir(parents=True, exist_ok=True)

        full_path.write_text(content)

        results.append((filepath, status))



    return results





# ── Helpers ────────────────────────────────────────────────────────────────





def _find_active_engagement(root: Path) -> Optional[str]:

    """Get the active engagement slug for the current branch."""

    from harness.engagement.resolver import resolve_active_engagement



    return resolve_active_engagement(root)





from harness.agents.consultation import ConsultationOrchestrator, ConsultationResult

from harness.agents.cycle import (

    MAX_PHASE_JUMPS_PER_PHASE,

    CycleResult,

)

from harness.agents.fleet_registry import FleetRegistry

from harness.context.loader import ContextLoader





def _load_engagement_context(

    root: Path, engagement_slug: str, tier: int = 2

) -> str:

    """Load the engagement context bundle for agent awareness.



    Returns a formatted context string, or empty string if the

    engagement doesn't exist yet (first-session startup).

    """

    engagement_root = (

        root / ".harness" / "engagements" / engagement_slug

    )

    if not engagement_root.is_dir():

        return ""

    try:

        loader = ContextLoader(engagement_root, root, cache_timeout_seconds=300)

        bundle = loader.load_bundle(tier=tier)

        if bundle:

            return (

                "--- Current Engagement Context ---\n"

                f"{bundle}\n"

                "--- End Engagement Context ---\n"

            )

    except Exception:

        # Fail-safe: don't block user interaction if context loading fails

        pass

    return ""





DOMAIN_LANGUAGE_PREAMBLE = (

    "You are working within the **Dev Harness** — an agent orchestration system. "

    "This engagement follows these naming conventions:\n"

    "- **Wave**: A PR-sized batch of work. The primary decomposition unit. "

    "  A wave can span multiple phases (e.g., design + build + test for a small feature).\n"

    "- **Phase**: A task label indicating the stage of execution "

    "  (requirements, design, build, test, review). Phases are labels on tasks, not containers.\n"

    "- **Iteration**: A review-feedback cycle within a wave (iteration 0 = first pass, "

    "  iteration 1 = revised after feedback).\n"

    "Refer to these terms consistently in your responses."

)





def _parse_waves(plan_path: Path) -> list[dict]:

    """Parse waves from a plan.md file.



    Looks for ``## Wave / Iteration {N}: {title}`` headers and returns

    a list of dicts with ``title`` and ``context`` (full plan content).

    Returns an empty list if no plan exists or no waves are found.

    """

    import re



    if not plan_path.is_file():

        return []



    content = plan_path.read_text()

    waves = []

    for match in re.finditer(

        r"^##\s+Wave\s+/\s+Iteration\s+\d+\s*:\s*(.+)$",

        content,

        re.MULTILINE,

    ):

        title = match.group(1).strip()

        waves.append({"title": title, "context": content})

    return waves









def _build_system_prompt(

    phase: dict,

    root: Path | None = None,

    engagement_slug: str = "",

    context: str = "",

    conversation: str = "",

    engagement_context: str | None = None,

    fleet_section: str | None = None,

    patterns_section: str | None = None,

) -> str:

    """Build the system prompt for an agent in a given phase.



    Injects fleet guidelines and patterns between the phase prompt

    and prior artifacts when ``root`` is available.



    Fleet participation is determined by the ``fleets`` key in the

    phase definition. The old agent-role-based lookup has been removed

    (Phase 2 clean break).



    The injection order is:



        1. Domain language preamble

        2. Engagement context bundle (file awareness)

        3. Phase prompt (role definition)

        4. Fleet guidelines (from all fleets in phase["fleets"])

        5. Injected patterns (if pattern files exist)

        6. Prior artifacts from previous phases

        7. Conversation history



    Args:

        phase: Phase definition dict with ``prompt`` and optional ``fleets``.

        root: Project root for loading fleet/pattern/context data.

        engagement_slug: Current engagement slug for context loading.

        context: Prior artifacts from previous phases.

        conversation: Conversation history from prior phases.

        engagement_context: Pre-loaded engagement context string.

            If ``None`` and ``root`` + ``engagement_slug`` are provided,

            loads from disk via ``_load_engagement_context``.

        fleet_section: Pre-formatted fleet guidelines section.

            If ``None`` and ``root`` is provided, loads from disk.

        patterns_section: Pre-formatted patterns section.

            If ``None`` and ``root`` is provided, loads from disk.

    """

    parts = [DOMAIN_LANGUAGE_PREAMBLE, phase["prompt"]]



    # Fleet guidelines + patterns injection (between phase prompt and prior artifacts)

    resolved_fleet = fleet_section

    resolved_patterns = patterns_section

    fleet_names: list[str] = phase.get("fleets", [])



    if resolved_fleet is None and root is not None and fleet_names:

        from harness.agents.context_builder import (

            get_fleet_system_prompt_section_for_phase,

        )

        from harness.agents.fleet_registry import FleetRegistry

        from harness.agents.pattern import PatternLoader



        registry = FleetRegistry(root)

        resolved_fleet = get_fleet_system_prompt_section_for_phase(

            fleet_names, registry

        )



        # Load patterns from all fleets in this phase

        loader = PatternLoader(root)

        for fleet_name in fleet_names:

            patterns = loader.load_for_fleet(fleet_name)

            if patterns:

                section = loader.format_patterns_section(patterns)

                if section:

                    if resolved_patterns:

                        resolved_patterns += "\n\n---\n\n" + section

                    else:

                        resolved_patterns = section



    if resolved_fleet:

        parts.append(resolved_fleet)

    if resolved_patterns:

        parts.append(resolved_patterns)



    # Prepend engagement context bundle (file awareness for the agent)

    resolved_context = engagement_context

    if resolved_context is None and root is not None and engagement_slug:

        resolved_context = _load_engagement_context(root, engagement_slug)



    if resolved_context:

        parts.insert(

            1,

            f"CURRENT ENGAGEMENT FILES:\n{resolved_context}\n"

            "These files exist in your engagement. Read them before writing "

            "to avoid duplication. Use the RepoTool (available via function "

            "calling) to read and write files in this engagement.",

        )



    if context:

        parts.append(f"\nPRIOR ARTIFACTS (from previous phases):\n{context}")



    if conversation:

        parts.append(

            f"\nCONVERSATION HISTORY (from prior phases -- do not repeat "

            f"what's already been discussed):\n{conversation}"

        )



    return "\n\n".join(parts)





def _phase_output_dir(root: Path, slug: str, phase_name: str) -> Path:

    """Get or create the output directory for a phase's artifacts.



    Upfront phase artifacts (requirements→design) live at the engagement

    root level. When wave-level implementation starts, artifacts will be

    nested under ``waves/<wave-slug>/<phase-name>/`` instead.

    """

    d = root / ".harness" / "engagements" / slug / phase_name

    d.mkdir(parents=True, exist_ok=True)

    return d





def _write_phase_artifact(

    root: Path, slug: str, phase_name: str, content: str

) -> Path:

    """Write the last assistant response as the phase artifact."""

    phase_def = next((p for p in PHASES if p["name"] == phase_name), None)

    filename = phase_def["artifact"] if phase_def else f"{phase_name}.md"

    out_dir = _phase_output_dir(root, slug, phase_name)

    path = out_dir / filename

    path.write_text(content)

    return path





def _print_header(text: str, char: str = "=") -> None:

    """Print a decorative header."""

    import shutil



    width = min(72, shutil.get_terminal_size().columns)

    click.echo()

    click.echo(char * width)

    click.echo(f"  {text}")

    click.echo(char * width)

    click.echo()





def _print_help() -> None:

    """Print available meta-commands."""

    click.echo()

    click.echo("Meta-commands:")

    click.echo("  /help        -- show this help")

    click.echo("  /save        -- save transcript to engagement")

    click.echo("  /write       -- write last response as phase artifact")

    click.echo("  /apply       -- write files from last response (fallback)")

    click.echo("  /models      -- list available providers and models")

    click.echo(

        "  /model <n>   -- switch to a provider by name "

        "(or \"<name> <alias>\" for a specific model alias)"

    )

    click.echo(

        "  /phase       -- show phase state diagram "

    )

    click.echo(

        "  /navigate <p>-- jump to a phase with checkpoint "

        "(design, planning, implementation, etc.)"

    )

    click.echo(

        "  /feedback <t> <r> -- send feedback packet to "

        "target phase with reason"

    )

    click.echo("  /resume      -- resume from paused checkpoint")

    click.echo("  /resume-force-- resume even if checkpoint is stale")

    if hasattr(_print_help, "_in_session") and _print_help._in_session:

        click.echo("  /next        -- advance to next phase")

        click.echo("  /approve     -- approve and advance")

        click.echo("  /changes     -- request revisions")

        click.echo(

            "  /consult-resolve <i> <r>"

            " -- resolve blocking consult"

        )

    click.echo("  /new         -- start fresh conversation")

    _print_consult_help()

    click.echo("  /exec <cmd>  -- run a shell command and display output")
    click.echo("  /eval <cmd>  -- alias for /exec")
    click.echo("  /version     -- show version info")

    click.echo("  /exit        -- exit session")

    click.echo()

    click.echo("Line editing: use Alt+Left/Right to jump words, Home/End for line ends")

    click.echo()





def _format_conversation_for_context(messages: list[dict]) -> str:

    """Format recent conversation history as a text block for system prompt."""

    lines = []

    for m in messages:

        if m["role"] in ("user", "assistant"):

            label = "You" if m["role"] == "user" else "Assistant"

            content = m["content"]

            if len(content) > 500:

                content = content[:500] + "\n[...truncated...]"

            lines.append(f"{label}: {content}")

    return "\n---\n".join(lines)





def _report_apply_results(

    results: list[tuple[str, str]], root: Path

) -> None:

    """Print a summary of file write results."""

    if not results:

        click.echo(

            "No files detected. The agent needs to format output with:\n"

            "    ## File: path/to/file.ext\n"

            "    (content)\n\n"

            "or with a code block starting with // path/to/file.ext or\n"

            "# path/to/file.ext"

        )

        return



    created = [r for r in results if r[1] == "created"]

    overwritten = [r for r in results if r[1] == "overwritten"]

    errors = [r for r in results if r[1].startswith("error:")]



    if created:

        click.echo("\nCreated files:")

        for path, _ in created:

            click.echo(f"  + {path}")

    if overwritten:

        click.echo("\nOverwritten files:")

        for path, _ in overwritten:

            click.echo(f"  ~ {path}")

    if errors:

        click.echo("\nErrors:")

        for path, status in errors:

            click.echo(f"  x {path}: {status}")





# ── Consultation command helpers ───────────────────────────────────────────





def _do_consult(

    root: Path,

    question: str,

    fleet_filter: Optional[str] = None,

    mode: Optional[str] = None,

) -> ConsultationResult:

    """Route a consultation question through the orchestrator.



    Args:

        root: Project root (for :class:`FleetRegistry` location).

        question: The question text to route.

        fleet_filter: If set, only match against this fleet.

        mode: Override the consultation mode ("advisory" or "blocking").



    Returns:

        A :class:`ConsultationResult` with the routing outcome.

    """

    registry = FleetRegistry(root)

    orch = ConsultationOrchestrator(registry)

    return orch.route(question, fleet_filter=fleet_filter, mode=mode)





def _parse_consult_flags(raw: str) -> dict:

    """Parse ``--fleet`` and ``--mode`` flags from a ``/consult`` command line.



    Returns a dict with keys ``question``, ``fleet_filter`` (str or None),

    and ``mode`` (str or None).



    Example::

        _parse_consult_flags("--fleet architecture --mode blocking check this")

        # -> {"question": "check this", "fleet_filter": "architecture", "mode": "blocking"}

    """

    fleet_filter: Optional[str] = None

    mode: Optional[str] = None



    words = raw.split()

    keep = []

    i = 0

    while i < len(words):

        w = words[i]

        if w == "--fleet" and i + 1 < len(words):

            fleet_filter = words[i + 1]

            i += 2

            continue

        if w == "--mode" and i + 1 < len(words):

            mode = words[i + 1]

            i += 2

            continue

        # Flag without value — treat as literal

        keep.append(w)

        i += 1



    question = " ".join(keep).strip()

    return {"question": question, "fleet_filter": fleet_filter, "mode": mode}





def _format_consult_result(result: ConsultationResult) -> str:

    """Format a :class:`ConsultationResult` for terminal display.



    Returns a multi-line string ready to be echoed to the user.

    """

    lines = ["── Consultation ──", f"  Question: {result.question}"]

    lines.append(f"  Status: {result.status}")

    if result.fleet_name:

        lines.append(f"  Fleet: {result.fleet_name}")

    if result.capability:

        lines.append(f"  Capability: {result.capability}")

    if result.mode == "blocking":

        lines.append(

            "  Mode: \u26a0\ufe0f BLOCKING"

            " (must be resolved before advancing)"

        )

    if result.error:

        lines.append(f"  Error: {result.error}")

    lines.append("\u2500" * 40)

    # Truncate long responses for terminal readability

    resp = result.response

    if len(resp) > 600:

        resp = resp[:597] + "..."

    lines.append(resp)

    if result.status == "unmatched":

        lines.append(

            "\n  Tip: Type /consult [--fleet <name>] [--mode <m>]"

            " <question> to ask with different phrasing."

        )

        lines.append("  Or use one of the questions listed above.")

    lines.append("\u2500" * 40)

    return "\n".join(lines)





def _print_consult_help() -> None:

    """Print consultation-related meta-commands in help output."""

    click.echo(

        "  /consult <q>        -- route a question to the matching fleet"

    )

    click.echo(

        "    --fleet <name>    scoped to a specific fleet"

    )

    click.echo(

        "    --mode <m>        override mode (advisory|blocking)"

    )

    click.echo(

        "  /consult-resolve <i> <r>"

        " -- resolve a blocking consult (session loop only)"

    )





# ── Phase jump helpers ──────────────────────────────────────────────────────





def _init_phase_jump_counts() -> dict[str, int]:

    """Create a new phase-jump counter dict.



    Tracks how many times each phase has requested a jump back to a

    specific target, preventing infinite loops. Returns a mutable dict

    that should be passed through the session loop.



    Use with ``_check_phase_jump_limit`` before executing any jump.

    """

    return {}





def _check_phase_jump_limit(

    jump_counts: dict[str, int],

    source_phase: str,

    target_phase: str,

) -> bool:

    """Check and increment the phase-jump counter for a source→target pair.



    Args:

        jump_counts: The mutable counter dict (per-phase tracking).

        source_phase: The phase requesting the jump.

        target_phase: The phase to jump to.



    Returns:

        ``True`` if the jump is allowed (under the limit).

        ``False`` if the limit is exceeded (auto-jumps disabled).

    """

    key = f"{source_phase}→{target_phase}"

    current = jump_counts.get(key, 0)

    if current >= MAX_PHASE_JUMPS_PER_PHASE:

        return False

    jump_counts[key] = current + 1

    return True





def _format_jump_marker(

    cycle_result: CycleResult,

) -> str:

    """Format a phase jump marker for terminal display."""

    if not cycle_result.is_phase_jump:

        return ""

    target = cycle_result.jump_target or "unknown"

    return (

        f"  \U0001f500 Cycle requests jump to phase: {target}\n"

        f"  Reason: {cycle_result.summary or 'No reason given'}"

    )





def _check_for_phase_jump_from_content(

    content: str,

) -> str | None:

    """Check agent output for embedded phase-jump markers.



    Looks for markers like ``PHASE_JUMP:design`` in the agent's output.

    If found, returns the target phase name. Used when phases aren't

    running through CycleRunner yet but an agent can still signal a

    jump request.



    Returns:

        The target phase name, or ``None`` if no jump marker found.

    """

    if not content:

        return None

    match = re.search(r"PHASE_JUMP:\s*(\w+)", content)

    if match:

        return match.group(1)

    return None





def _check_and_handle_phase_jump(

    content: str,

    phase_name: str,

    jump_counts: dict[str, int],

) -> str | None:

    """Check content for a phase-jump marker and handle the jump if allowed.



    Combines marker detection + limit check into one call. Returns the

    target phase name if the jump should be executed, or ``None`` if no

    jump is signaled or the limit has been exceeded.



    Args:

        content: The agent's output content.

        phase_name: The current phase name (source).

        jump_counts: The mutable jump counter dict.



    Returns:

        Target phase name if jump is allowed, else ``None``.

    """

    target = _check_for_phase_jump_from_content(content)

    if target is None:

        return None

    if _check_phase_jump_limit(jump_counts, phase_name, target):

        return target

    logger.warning(

        "Phase jump %s→%s exceeds max (%d), blocking",

        phase_name, target, MAX_PHASE_JUMPS_PER_PHASE,

    )

    return None





def _process_cycle_result_for_display(

    cycle_result: CycleResult,

) -> list[str]:

    """Extract human-readable lines from a CycleResult for terminal display.



    Returns a list of lines describing the cycle result, including

    iteration count, convergence status, and any phase jump signal.

    """

    lines = [f"Cycle completed: {cycle_result.iterations} iteration(s)"]

    if cycle_result.error:

        lines.append(f"  Error: {cycle_result.error}")

    if cycle_result.is_phase_jump:

        target = cycle_result.jump_target or "unknown"

        lines.append(f"  \U0001f500 Phase jump requested → {target}")

        if cycle_result.summary:

            lines.append(f"    Reason: {cycle_result.summary}")

    elif cycle_result.summary:

        lines.append(f"  Summary: {cycle_result.summary}")

    return lines





# ── Interactive chat loop ──────────────────────────────────────────────────





async def chat_loop(

    root: Path,

    engagement_slug: str,

    phase: str = "design",

    one_shot: str | None = None,

    context_tier: int = 2,

) -> None:

    """Run an interactive chat session using InteractiveSession."""

    from harness.session.interactive import InteractiveSession, execute_chat_effects

    from harness.session.commands import route_chat_command

    from harness.session.client import resolve_provider

    import click



    provider = resolve_provider(root)

    api_key = provider.get("api_key", "")

    if not api_key:

        click.echo("Error: No API key configured.", err=True)

        return



    phase_def = next(

        (p for p in PHASES if p["name"] == phase), PHASES[0]

    )



    # Build system prompt for one-shot or interactive use

    system_prompt = _build_system_prompt(

        phase_def, root=root, engagement_slug=engagement_slug,

    )



    session = InteractiveSession(

        root=root,

        engagement_slug=engagement_slug,

        phase=phase,

        phase_def=phase_def,

        context_tier=context_tier,

        command_router=route_chat_command,

        effect_executor=execute_chat_effects,

    )

    session.provider = provider

    session.model = provider.get("model", "deepseek-v4-pro")



    # Create client with system prompt

    from harness.session.client import SessionClient

    session.client = SessionClient(

        root=root,

        engagement_slug=engagement_slug,

        phase_def=phase_def,

        context_tier=context_tier,

        system_prompt=system_prompt,

    )



    # Create transcript

    from harness.session.client import ChatTranscript

    from datetime import datetime, timezone

    session.transcript = ChatTranscript(

        engagement_slug=engagement_slug,

        phase=phase,

        started_at=datetime.now(timezone.utc).isoformat(),

    )



    # Display header

    _print_header(

        f"Chat -- {phase_def['title']} (engagement: {engagement_slug})"

    )

    click.echo(f"Model: {session.model}")

    click.echo("Type  /help for commands, /exit to quit")

    click.echo()



    # One-shot mode: single response, no interactive loop

    if one_shot:

        _print_header("One-shot response", "-")

        click.echo(f">>> {one_shot}")

        click.echo("-" * 60)

        session.transcript.messages.append(

            ChatMessage(

                role="user",

                content=one_shot,

                timestamp=datetime.now(timezone.utc).isoformat(),

            )

        )

        async for chunk in session.client.stream(one_shot):

            click.echo(chunk, nl=False)

            sys.stdout.flush()

        click.echo()

        click.echo("-" * 60)

        session.transcript.messages.append(

            ChatMessage(

                role="assistant",

                content=session.client.get_last_response(),

                timestamp=datetime.now(timezone.utc).isoformat(),

            )

        )

        session.transcript.ended_at = datetime.now(timezone.utc).isoformat()

        saved = session.transcript.save(root)

        click.echo(f"\nTranscript saved: {saved}")

        return



    # Interactive loop via InteractiveSession

    await session.run()

def _load_assessment_findings(root: Path, slug: str) -> str:
    """Load the latest assessment findings for a get-well session.

    Reads the most recent assessment manifest from the engagement and
    returns a formatted context string describing the findings. Returns
    an empty string if no assessment exists.
    """
    import json
    from harness.paths import get_engagements_dir

    assess_dir = get_engagements_dir(root) / slug / "assessments"
    if not assess_dir.is_dir():
        return ""

    manifests = sorted(assess_dir.glob("*-manifest.json"), reverse=True)
    if not manifests:
        return ""

    try:
        manifest = json.loads(manifests[0].read_text())
    except (json.JSONDecodeError, OSError):
        return ""

    findings = manifest.get("findings", [])
    if not findings:
        return ""

    score = manifest.get("score", "unknown")
    recommendations = manifest.get("recommendations", [])

    lines = [
        "--- Assessment Findings ---",
        "Score: " + str(score),
        "Total findings: " + str(len(findings)),
        "",
    ]

    for f in findings:
        fid = f.get("id", "?")
        sev = f.get("severity", "info")
        cat = f.get("category", "")
        msg = f.get("message", "")
        filepath = f.get("file", "")
        lines.append(f"  [{sev:8s}] {fid}: {msg}")
        if cat:
            lines.append(f"           Category: {cat}")
        if filepath:
            lines.append(f"           File: {filepath}")
        lines.append("")

    if recommendations:
        lines.append("Recommendations:")
        for r in recommendations:
            lines.append(f"  - {r}")
        lines.append("")

    lines.append("--- End Assessment Findings ---")
    return "\n".join(lines)





async def session_loop(
    root: Path,
    engagement_slug: str,
    start_phase: str = "requirements",
    context_tier: int = 2,
    session_type: str | None = None,
) -> None:
    """Run a full session through all phases using InteractiveSession."""
    import click
    from harness.session.interactive import (
        InteractiveSession,
        execute_session_effects,
    )
    from harness.session.commands import route_session_command
    from harness.session.client import resolve_provider, ChatTranscript, ChatMessage
    from harness.engagement.checkpoint import CheckpointManager
    from harness.engagement.feedback import FeedbackManager, FeedbackPacket
    from harness.engagement.phase_state import PhaseState as PS
    from harness.engagement.phase_state import PhaseStateManager
    from datetime import datetime, timezone

    # ── Select phase list ─────────────────────────────
    # Resolve session type from engagement metadata (optional)
    # CLI-provided session_type takes priority
    if session_type is None:
        try:
            from harness.session.types import read_session_type
            st = read_session_type(root, engagement_slug)
            if st:
                session_type = st.value
        except Exception:
            pass

    # Determine effective phase list based on session type
    is_get_well = session_type == "get-well"
    if is_get_well:
        effective_phases: list[dict] = _build_get_well_phase_list()
        assessment_findings = _load_assessment_findings(root, engagement_slug)
    else:
        effective_phases = PHASES
        assessment_findings = None

    # Find starting index
    start_idx = 0
    for i, p in enumerate(effective_phases):
        if p["name"] == start_phase:
            start_idx = i
            break
    if start_idx == 0 and start_phase != effective_phases[0]["name"]:
        start_idx = 0

    provider = resolve_provider(root)
    api_key = provider.get("api_key", "")
    if not api_key:
        click.echo("Error: No API key configured.", err=True)
        return

    base_url = provider.get("base_url", "https://api.deepseek.com")
    model = provider.get("model", "deepseek-v4-pro")
    provider_type = provider.get("type", "openai-compatible")

    _print_header(f"Session -- {engagement_slug}")
    click.echo(f"Starting from phase: {effective_phases[start_idx]['title']}")
    if session_type:
        click.echo(f"Session type: {session_type}")
    click.echo()

    # Store session type in engagement metadata if provided
    if session_type:
        from harness.session.types import store_session_type
        try:
            store_session_type(root, engagement_slug, session_type)
        except Exception:
            pass

    # Load phase state for cross-phase navigation
    psm = PhaseStateManager(root, engagement_slug)
    ckm = CheckpointManager(root, engagement_slug)
    fbm = FeedbackManager(root, engagement_slug)

    # Shared conversation across all phases
    phase_artifacts: list[str] = []
    phase_conversations: list[str] = []
    blocking_consults: dict[str, list[ConsultationResult]] = {}
    jump_counts: dict[str, int] = _init_phase_jump_counts()

    # ── Build phase list ──────────────────────────
    _phase_list: list[dict] = []
    for phase_idx in range(start_idx, len(effective_phases)):
        phase_def = effective_phases[phase_idx]

        if phase_def["name"] == "implementation":
            from harness.plan.plan_manager import PlanManager
            from harness.wave.wave_cycle import WaveCycleConfig, WaveCycleRunner

            plan = PlanManager(root, engagement_slug).load()
            uncommitted = [w for w in plan.waves if not w.is_committed()]

            if uncommitted:
                click.echo(
                    f"\n📋 Plan defines {len(uncommitted)} uncommitted wave(s). "
                    "Running per-wave code+test cycles.\n"
                )
                for w in uncommitted:
                    click.echo()
                    click.echo("\u2500" * 50)
                    click.echo(f"  Wave {w.id}: {w.title}  [{w.type}]")
                    click.echo("\u2500" * 50)

        _phase_list.append(phase_def)

    # ── Phase execution loop ──────────────────────────
    for phase_idx in range(start_idx, len(effective_phases)):
        phase_def = effective_phases[phase_idx]
        click.echo(str(_format_jump_marker(CycleResult(status="complete"))))

        _print_header(f"  Phase {phase_idx + 1 - start_idx}/{len(effective_phases) - start_idx}"
                       f" -- {phase_def['title']}")
        click.echo()

        # Ensure phase is active
        psm.ensure_phase(phase_def["name"])
        psm.transition(phase_def["name"], PS.ACTIVE)

        # Build system prompt
        # For get-well sessions, inject assessment findings as context
        gw_context = ""
        if assessment_findings and phase_def["name"] in ("assessment-triage", "remediation-design"):
            gw_context = assessment_findings
        system_prompt = _build_system_prompt(
            phase_def, root=root, engagement_slug=engagement_slug,
            context=gw_context,
        )

        phase_done = False
        phase_conv: list[str] = []

        # Create InteractiveSession for this phase
        session = InteractiveSession(
            root=root,
            engagement_slug=engagement_slug,
            phase=phase_def["name"],
            phase_def=phase_def,
            context_tier=context_tier,
            command_router=route_session_command,
            effect_executor=execute_session_effects,
        )
        session.provider = provider
        session.model = model
        session._blocking_consults = blocking_consults
        session._phase_artifacts = phase_artifacts
        session._phase_conv = phase_conv
        session._phase_done = False

        from harness.session.client import SessionClient
        session.client = SessionClient(
            root=root,
            engagement_slug=engagement_slug,
            phase_def=phase_def,
            context_tier=context_tier,
            system_prompt=system_prompt,
        )

        session.transcript = ChatTranscript(
            engagement_slug=engagement_slug,
            phase=phase_def["name"],
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        click.echo(f"Model: {model}")
        click.echo(
            "Type /help for commands, /next to advance, "
            "/changes to request revisions, /exit to quit"
        )
        click.echo()

        # Run the interactive session for this phase
        await session.run()

        # Phase completed — capture output
        last_resp = session.client.get_last_response() if session.client else ""
        if last_resp:
            phase_artifacts.append(
                f"## {phase_def['title']}\n\n{last_resp}"
            )

        phase_conversations.append("\n".join(phase_conv))

    # All phases complete
    _print_header("Session Complete!")
    click.echo("All phases have been processed.")
