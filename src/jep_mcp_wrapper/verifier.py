"""Replay and verification for archived JEP MCP tool events."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .archive import AppendOnlyEventArchive, ArchiveTamperError, validate_events
from .events import JEPEvent, ToolExecutionState


_VALID_TRANSITIONS = {
    ToolExecutionState.REQUESTED: {ToolExecutionState.RUNNING},
    ToolExecutionState.RUNNING: {ToolExecutionState.SUCCEEDED, ToolExecutionState.FAILED},
    ToolExecutionState.SUCCEEDED: set(),
    ToolExecutionState.FAILED: set(),
    ToolExecutionState.DELEGATED: {ToolExecutionState.REQUESTED, ToolExecutionState.RUNNING},
}


@dataclass(frozen=True)
class ReplayResult:
    """Result of replaying and verifying an archive."""

    verified: bool
    events: tuple[JEPEvent, ...]
    terminal_states: dict[str, ToolExecutionState]
    lineage_by_call: dict[str, tuple[str, ...]]
    errors: tuple[str, ...] = field(default_factory=tuple)


class ReplayVerifier:
    """Replays execution chains, verifies lineages, and detects tampering."""

    def __init__(self, archive: AppendOnlyEventArchive | str):
        self.archive = archive

    def replay(self) -> ReplayResult:
        """Replay archive events and return chain state with validation errors."""

        try:
            archive = self.archive if isinstance(self.archive, AppendOnlyEventArchive) else AppendOnlyEventArchive(self.archive)
            events = archive.read_events()
            validate_events(events)
        except ArchiveTamperError as exc:
            return ReplayResult(
                verified=False,
                events=(),
                terminal_states={},
                lineage_by_call={},
                errors=(f"tampering detected: {exc}",),
            )

        errors: list[str] = []
        events_by_call: dict[str, list[JEPEvent]] = defaultdict(list)
        for event in events:
            events_by_call[event.call_id].append(event)

        terminal_states: dict[str, ToolExecutionState] = {}
        lineage_by_call: dict[str, tuple[str, ...]] = {}
        for call_id, call_events in events_by_call.items():
            previous_state: ToolExecutionState | None = None
            expected_lineage = call_events[0].delegation_lineage
            for event in call_events:
                if event.delegation_lineage != expected_lineage:
                    errors.append(f"call {call_id} changed delegation lineage")
                if previous_state is not None and event.execution_state not in _VALID_TRANSITIONS[previous_state]:
                    errors.append(
                        f"call {call_id} invalid transition {previous_state.value}->{event.execution_state.value}"
                    )
                previous_state = event.execution_state
            terminal_states[call_id] = call_events[-1].execution_state
            lineage_by_call[call_id] = expected_lineage
            if call_events[-1].execution_state not in {ToolExecutionState.SUCCEEDED, ToolExecutionState.FAILED}:
                errors.append(f"call {call_id} did not reach a terminal state")

        self._verify_parent_lineage(events, errors)
        return ReplayResult(
            verified=not errors,
            events=tuple(events),
            terminal_states=terminal_states,
            lineage_by_call=lineage_by_call,
            errors=tuple(errors),
        )

    def verify_tool_lineage(self, expected_prefix: tuple[str, ...] | None = None) -> bool:
        """Return True when replay succeeds and every call matches an optional lineage prefix."""

        result = self.replay()
        if not result.verified:
            return False
        if expected_prefix is None:
            return True
        return all(lineage[: len(expected_prefix)] == expected_prefix for lineage in result.lineage_by_call.values())

    def detect_tampering(self) -> bool:
        """Return True when deterministic hashes or replay semantics fail."""

        return not self.replay().verified

    def _verify_parent_lineage(self, events: list[JEPEvent], errors: list[str]) -> None:
        by_event_id = {event.event_id: event for event in events}
        for event in events:
            if event.parent_event_id is None:
                continue
            parent = by_event_id.get(event.parent_event_id)
            if parent is None:
                errors.append(f"event {event.event_id} references missing parent_event_id")
                continue
            parent_lineage = parent.delegation_lineage
            lineage = event.delegation_lineage
            if lineage != parent_lineage and lineage[:-1] != parent_lineage:
                errors.append(f"event {event.event_id} lineage does not descend from parent")
