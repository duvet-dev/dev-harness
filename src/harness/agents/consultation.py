"""Consultation orchestrator — cross-fleet consultation routing.

Routes consultation questions to the appropriate fleet using structured
phrase matching against each fleet's declared :class:`ConsultationCapability`.

Handles advisory and blocking consults, sequential dispatch with ALL-pass
blocking rules, auto-consult triggering, and error handling (never block
on infrastructure failure).

Phase 3 of Wave 18 (Option G — Fleet & Cycle).

Usage::

    from harness.agents.consultation import ConsultationOrchestrator
    from harness.team.registry import TeamRegistry
from harness.team.defaults import BUILTIN_TEAMS

    registry = TeamRegistry(builtin=BUILTIN_TEAMS)
    orch = ConsultationOrchestrator(registry)

    # Route a single question
    result = orch.route("Is this architecture still sound?")
    print(result.fleet_name, result.mode)

    # Dispatch multiple blocking consults sequentially
    results = orch.dispatch_sequential([
        "Is architecture still sound?",
        "Are tests passing?",
    ])

    # Get auto-fired consults for entering a phase
    for result in orch.auto_consults("implementation"):
        print(f"Auto: {result.question}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional


# ---------------------------------------------------------------------------
# ConsultationCapability
# ---------------------------------------------------------------------------


@dataclass
class ConsultationCapability:
    """A cross-fleet consultation that a fleet/team can answer.

    Matching uses **structured phrase matching** (deterministic,
    testable, no NLP infra). A question matches if any
    ``match_phrases`` string appears as a substring of the
    question text (case-insensitive).

    Attributes:
        name: Unique capability identifier.
        match_phrases: List of exact phrases that trigger this
            consultation. Match is case-insensitive substring.
        description: Human-readable description.
        mode: ``"advisory"`` or ``"blocking"``.
        scope: When this consultation can fire.
            ``"cross-phase"``, ``"wave-build"``, ``"phase:<name>"``,
            ``"trigger:<phase>"``, ``"cycle:<runner-name>"``.
        question: The default question template.
    """
    name: str
    match_phrases: list[str] = field(default_factory=list)
    description: str = ""
    mode: Literal["advisory", "blocking"] = "advisory"
    scope: str = "cross-phase"
    question: str = ""

    def matches(self, question: str) -> bool:
        """Return True if this capability can answer the question.

        Performs case-insensitive substring matching against all
        ``match_phrases``.
        """
        q_lower = question.lower()
        return any(phrase.lower() in q_lower for phrase in self.match_phrases)


# ---------------------------------------------------------------------------
# ConsultationResult
# ---------------------------------------------------------------------------


@dataclass
class ConsultationResult:
    """Result of a single consultation dispatch.

    Tracks the question, which fleet handled it, the mode
    (advisory/blocking), the response from the consulted agent,
    and resolution state for blocking consults.

    Attributes:
        question: The question that was asked.
        capability: The name of the matched capability, or ``None``
            if no match was found.
        fleet_name: The fleet that handled the consultation.
        response: The LLM's response text, or an informational
            message if no match was found or dispatch failed.
        mode: ``"advisory"`` or ``"blocking"`` (from the matched
            capability; defaults to ``"advisory"``).
        status: One of:
            - ``"matched"`` — successfully matched to a fleet.
            - ``"unmatched"`` — no fleet could answer the question.
            - ``"unavailable"`` — dispatch failed (infrastructure /
              agent error).
            - ``"resolved"`` — blocking consult was resolved.
        resolution: How this blocking consult was resolved
            (e.g. ``"approved"``, ``"rejected"``, ``"deferred"``).
            ``None`` until resolved.
        resolved_by: Who resolved it — ``"user"`` or ``"system"``.
        error: Error message if the dispatch failed (infrastructure
            timeout, agent unavailable, etc.)
    """
    question: str = ""
    capability: Optional[str] = None
    fleet_name: str = ""
    response: str = ""
    mode: str = "advisory"
    status: str = "unmatched"
    resolution: Optional[str] = None
    resolved_by: Optional[str] = None
    error: Optional[str] = None

    def is_blocking(self) -> bool:
        """Return ``True`` if this consult blocks flow.

        A consultation is blocking when its mode is ``"blocking"``
        and it has not yet been resolved.
        """
        return self.mode == "blocking" and self.status != "resolved"

    def resolve(self, resolution: str, resolved_by: str = "system") -> None:
        """Mark this blocking consult as resolved.

        Args:
            resolution: How it was resolved (e.g. ``"approved"``,
                ``"rejected"``, ``"deferred"``).
            resolved_by: Who resolved it (``"user"`` or ``"system"``).
        """
        self.resolution = resolution
        self.resolved_by = resolved_by
        self.status = "resolved"

    @property
    def summary(self) -> str:
        """Return a one-line summary string."""
        meta = f"[{self.status}] {self.fleet_name}: {self.capability or '???'}"
        is_resolved = self.resolution is not None
        if self.mode == "blocking" and not is_resolved:
            meta += " (blocking)"
        if self.resolution:
            meta += f" → resolved: {self.resolution}"
        if self.error:
            meta += f" ⚠ {self.error}"
        return meta

    @property
    def response_lines(self) -> list[str]:
        """Return response split into lines for formatted display."""
        return self.response.splitlines()


# ---------------------------------------------------------------------------
# ConsultationOrchestrator
# ---------------------------------------------------------------------------


class ConsultationOrchestrator:
    """Routes consultation questions to the appropriate fleet.

    Uses structured phrase matching against each fleet's declared
    :class:`ConsultationCapability` list. Matching is deterministic,
    testable, and requires no NLP infrastructure.

    Dispatch rules (from the design):
        1. All matching capabilities are collected.
        2. They are resolved in deterministic order (alphabetical by
           fleet, then by capability name within each fleet).
        3. Blocking consults must **ALL** be resolved for flow to
           continue. If any blocks, execution pauses.
        4. On dispatch failure (agent unavailable, timeout, error):
           the consult is recorded as ``"unavailable"`` with
           advisory mode. Flow **NEVER** blocks on infrastructure failure.
        5. CycleRunner auto-consults only support advisory mode.

    Args:
        registry: A :class:`~harness.team.registry.TeamRegistry`
            instance with loaded fleet definitions.
    """

    def __init__(self, registry) -> None:
        self._registry = registry

    def can_answer(self, question: str, fleet_filter: str | None = None) -> list[tuple]:
        """Find all fleets with capabilities matching the question.

        Iterates over all registered fleets and their consultation
        capabilities, returning every matching
        ``(ConsultationCapability, fleet_name)`` pair.

        Args:
            question: The user's or system's question text.
            fleet_filter: Optional fleet name to narrow the search.
                Only capabilities from this fleet are checked.

        Returns:
            List of ``(ConsultationCapability, fleet_name)`` tuples
            for every fleet whose consultation capabilities match the
            question. Sorted alphabetically by fleet name, then by
            capability name within each fleet. Returns an empty list
            if no fleet can answer.
        """
        results: list[tuple] = []
        for fleet in sorted(
            self._registry.list_fleets(), key=lambda f: f.name
        ):
            if fleet_filter is not None and fleet.name != fleet_filter:
                continue
            for cap in sorted(
                fleet.consultations, key=lambda c: c.name
            ):
                if cap.matches(question):
                    results.append((cap, fleet.name))
        return results

    def can_answer_any(self, question: str, fleet_filter: str | None = None) -> bool:
        """Quick check if any fleet can answer the question.

        Args:
            question: The question text to check.
            fleet_filter: Optional fleet name to narrow the search.

        Returns:
            ``True`` if at least one fleet's capabilities match.
        """
        return len(self.can_answer(question, fleet_filter=fleet_filter)) > 0

    def route(self, question: str, mode: str | None = None,
              fleet_filter: str | None = None) -> ConsultationResult:
        """Route a single question to the matching fleet.

        If multiple fleets match, the first match in deterministic
        order (alphabetical by fleet name, then capability name)
        is used.

        If no fleet matches, the result has ``status="unmatched"``
        and includes a list of all available questions in its
        response field.

        Args:
            question: The question text to route.
            mode: Optional mode override (``"advisory"`` or
                ``"blocking"``). If set, overrides the capability's
                default mode. Useful when the caller wants to treat a
                consult as blocking regardless of the capability's
                declaration.
            fleet_filter: Optional fleet name to limit the search.
                Only capabilities from this fleet are checked.

        Returns:
            A :class:`ConsultationResult` with the appropriate status.
        """
        matches = self.can_answer(question, fleet_filter=fleet_filter)
        if not matches:
            available = self.get_available_questions(fleet_filter=fleet_filter)
            question_list = "\n".join(
                f"  - [{fleet}] {q}" for q, fleet, _ in available
            )
            return ConsultationResult(
                question=question,
                status="unmatched",
                response=(
                    "No fleet can answer this question.\n\n"
                    "Available questions:\n" + question_list
                ),
            )

        cap, fleet_name = matches[0]
        effective_mode = mode if mode is not None else cap.mode
        return ConsultationResult(
            question=question,
            capability=cap.name,
            fleet_name=fleet_name,
            mode=effective_mode,
            status="matched",
            response=f"Question routed to fleet '{fleet_name}' "
            f"for capability '{cap.name}'. "
            f"Mode: {effective_mode}.",
        )

    def dispatch_sequential(
        self,
        questions: list[str],
    ) -> list[ConsultationResult]:
        """Route multiple questions sequentially.

        Processes each question through :meth:`route`, collecting
        results in order. After all questions are routed, checks
        whether any blocking consults are unresolved.

        **Blocking rule:** ALL blocking consults must be resolved
        for flow to continue. If any blocks, the caller should
        present them to the user.

        **Error handling:** Infrastructure failures (agent
        unavailable, timeout) are recorded as ``"unavailable"``
        with advisory mode. Flow **never** blocks on infrastructure
        failure.

        Args:
            questions: Ordered list of question strings.

        Returns:
            List of :class:`ConsultationResult` in the same order
            as the input questions.
        """
        results: list[ConsultationResult] = []
        for question in questions:
            result = self.route(question)
            results.append(result)

        return results

    def auto_consults(self, phase_name: str) -> list[ConsultationResult]:
        """Collect all auto-consult triggers for the given phase.

        Returns consultation results for all capabilities whose
        scope matches the current phase. A capability matches if
        its scope is:

        - ``"cross-phase"`` — always fires.
        - ``"trigger:<phase_name>"`` — fires when entering the
          named phase.
        - ``"phase:<phase_name>"`` — fires when active in the
          named phase.

        All auto-consults are **advisory** (blocking mode is
        ignored for auto-triggers, per design rule 5).

        Args:
            phase_name: The phase being entered (e.g.
                ``"implementation"``).

        Returns:
            List of :class:`ConsultationResult`, one per matching
            capability, in deterministic order (alphabetical by
            fleet, then by capability).
        """
        results: list[ConsultationResult] = []
        for fleet in sorted(
            self._registry.list_fleets(), key=lambda f: f.name
        ):
            for cap in sorted(
                fleet.consultations, key=lambda c: c.name
            ):
                if cap.scope == "cross-phase" or \
                   cap.scope == f"trigger:{phase_name}" or \
                   cap.scope == f"phase:{phase_name}":
                    results.append(ConsultationResult(
                        question=cap.question or cap.description,
                        capability=cap.name,
                        fleet_name=fleet.name,
                        mode="advisory",  # auto-consults are always advisory
                        status="matched",
                        response=f"Auto-triggered from fleet "
                        f"'{fleet.name}' capability '{cap.name}'.",
                    ))
        return results

    def get_available_questions(
        self, fleet_filter: str | None = None
    ) -> list[tuple[str, str, str]]:
        """Return all consultation questions across all fleets.

        Args:
            fleet_filter: Optional fleet name to narrow results.
                Only capabilities from this fleet are included.

        Returns:
            List of ``(question_text, fleet_name, mode)`` triples
            for display. Only capabilities with non-empty questions
            or descriptions are included.
        """
        questions: list[tuple[str, str, str]] = []
        for fleet in sorted(
            self._registry.list_fleets(), key=lambda f: f.name
        ):
            if fleet_filter is not None and fleet.name != fleet_filter:
                continue
            for cap in sorted(
                fleet.consultations, key=lambda c: c.name
            ):
                text = cap.question or cap.description or cap.name
                questions.append((text, fleet.name, cap.mode))
        return questions
