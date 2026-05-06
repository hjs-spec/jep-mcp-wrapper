"""Event tracer for MCP tool execution."""

from __future__ import annotations

from typing import Any, Mapping

from .archive import AppendOnlyEventArchive
from .events import JEPEvent, ToolExecutionState
from .runtime import DelegationContext, ToolDelegationRuntime


class MCPExecutionTracer:
    """Creates JEP events for tool lifecycle transitions."""

    def __init__(self, archive: AppendOnlyEventArchive, runtime: ToolDelegationRuntime):
        self.archive = archive
        self.runtime = runtime

    def record(
        self,
        *,
        tool_name: str,
        state: ToolExecutionState,
        context: DelegationContext | None = None,
        call_id: str | None = None,
        parent_event_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> JEPEvent:
        """Create and append a lifecycle event to the archive."""

        active = context or self.runtime.current()
        event = JEPEvent.create(
            tool_name=tool_name,
            actor=active.actor,
            delegation_lineage=active.delegation_lineage,
            authority_scope=active.authority_scope,
            execution_state=state,
            sequence=self.archive.next_sequence,
            prev_hash=self.archive.last_hash,
            parent_event_id=parent_event_id or active.parent_event_id,
            call_id=call_id,
            metadata=metadata,
        )
        return self.archive.append(event)
