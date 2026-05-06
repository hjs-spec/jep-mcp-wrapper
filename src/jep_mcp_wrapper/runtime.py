"""Delegation context runtime for accountable MCP tool calls."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Iterator, Mapping


@dataclass(frozen=True)
class DelegationContext:
    """Actor, lineage, and authority scope active for a tool call."""

    actor: str
    delegation_lineage: tuple[str, ...] = field(default_factory=tuple)
    authority_scope: Mapping[str, Any] = field(default_factory=dict)
    parent_event_id: str | None = None


_current_context: ContextVar[DelegationContext | None] = ContextVar("jep_mcp_delegation_context", default=None)


class ToolDelegationRuntime:
    """Maintains nested tool delegation lineage without changing MCP payloads."""

    def __init__(self, *, default_actor: str = "mcp-client", default_authority_scope: Mapping[str, Any] | None = None):
        self.default_actor = default_actor
        self.default_authority_scope = dict(default_authority_scope or {})

    def current(self) -> DelegationContext:
        """Return active context or a default root context."""

        context = _current_context.get()
        if context is not None:
            return context
        return DelegationContext(actor=self.default_actor, authority_scope=self.default_authority_scope)

    @contextmanager
    def as_actor(
        self,
        actor: str,
        *,
        authority_scope: Mapping[str, Any] | None = None,
        parent_event_id: str | None = None,
    ) -> Iterator[DelegationContext]:
        """Run code under a root actor context."""

        context = DelegationContext(
            actor=actor,
            authority_scope=dict(authority_scope or self.default_authority_scope),
            parent_event_id=parent_event_id,
        )
        token = _current_context.set(context)
        try:
            yield context
        finally:
            _current_context.reset(token)

    @contextmanager
    def delegate(
        self,
        tool_name: str,
        *,
        actor: str | None = None,
        authority_scope: Mapping[str, Any] | None = None,
        parent_event_id: str | None = None,
    ) -> Iterator[DelegationContext]:
        """Enter a nested delegation context for chained tool execution."""

        parent = self.current()
        delegated_actor = actor or parent.actor
        delegated_scope = dict(parent.authority_scope)
        delegated_scope.update(dict(authority_scope or {}))
        context = DelegationContext(
            actor=delegated_actor,
            delegation_lineage=(*parent.delegation_lineage, tool_name),
            authority_scope=delegated_scope,
            parent_event_id=parent_event_id or parent.parent_event_id,
        )
        token = _current_context.set(context)
        try:
            yield context
        finally:
            _current_context.reset(token)
