"""Public wrapper for accountable MCP tool execution."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from functools import wraps
from typing import Any, Awaitable, Callable, Mapping, TypeVar
from uuid import uuid4

from .archive import AppendOnlyEventArchive
from .events import JEPEvent, ToolExecutionState
from .runtime import ToolDelegationRuntime
from .tracer import MCPExecutionTracer

T = TypeVar("T")


@dataclass(frozen=True)
class ToolCallResult:
    """Tool result plus trace metadata emitted by the wrapper."""

    value: Any
    call_id: str
    start_event: JEPEvent
    end_event: JEPEvent


class JEPMCPWrapper:
    """Wrap MCP tools with verifiable JEP accountability semantics.

    The wrapper decorates existing callables and keeps all accountability state in
    a side-channel event archive, so MCP protocol request/response schemas remain
    untouched.
    """

    def __init__(
        self,
        archive: AppendOnlyEventArchive | str,
        *,
        default_actor: str = "mcp-client",
        default_authority_scope: Mapping[str, Any] | None = None,
        return_trace: bool = False,
    ):
        self.archive = archive if isinstance(archive, AppendOnlyEventArchive) else AppendOnlyEventArchive(archive)
        self.runtime = ToolDelegationRuntime(
            default_actor=default_actor,
            default_authority_scope=default_authority_scope,
        )
        self.tracer = MCPExecutionTracer(self.archive, self.runtime)
        self.return_trace = return_trace

    def wrap_tool(
        self,
        tool_name: str,
        tool: Callable[..., T],
        *,
        authority_scope: Mapping[str, Any] | None = None,
        actor: str | None = None,
    ) -> Callable[..., T | ToolCallResult] | Callable[..., Awaitable[T | ToolCallResult]]:
        """Return a callable that records requested/running/succeeded/failed events."""

        if inspect.iscoroutinefunction(tool):

            @wraps(tool)
            async def async_wrapped(*args: Any, **kwargs: Any) -> T | ToolCallResult:
                return await self._execute_async(tool_name, tool, args, kwargs, authority_scope=authority_scope, actor=actor)

            return async_wrapped

        @wraps(tool)
        def wrapped(*args: Any, **kwargs: Any) -> T | ToolCallResult:
            return self._execute(tool_name, tool, args, kwargs, authority_scope=authority_scope, actor=actor)

        return wrapped

    def call_tool(
        self,
        tool_name: str,
        tool: Callable[..., T],
        *args: Any,
        authority_scope: Mapping[str, Any] | None = None,
        actor: str | None = None,
        **kwargs: Any,
    ) -> T | ToolCallResult:
        """Execute a synchronous tool once under accountability tracing."""

        return self._execute(tool_name, tool, args, kwargs, authority_scope=authority_scope, actor=actor)

    async def call_tool_async(
        self,
        tool_name: str,
        tool: Callable[..., Awaitable[T]],
        *args: Any,
        authority_scope: Mapping[str, Any] | None = None,
        actor: str | None = None,
        **kwargs: Any,
    ) -> T | ToolCallResult:
        """Execute an async tool once under accountability tracing."""

        return await self._execute_async(tool_name, tool, args, kwargs, authority_scope=authority_scope, actor=actor)

    def _execute(
        self,
        tool_name: str,
        tool: Callable[..., T],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        *,
        authority_scope: Mapping[str, Any] | None,
        actor: str | None,
    ) -> T | ToolCallResult:
        call_id = uuid4().hex
        with self.runtime.delegate(tool_name, actor=actor, authority_scope=authority_scope):
            start_event = self.tracer.record(
                tool_name=tool_name,
                state=ToolExecutionState.REQUESTED,
                call_id=call_id,
            )
            try:
                running_event = self.tracer.record(
                    tool_name=tool_name,
                    state=ToolExecutionState.RUNNING,
                    call_id=call_id,
                    parent_event_id=start_event.event_id,
                )
                value = tool(*args, **kwargs)
                end_event = self.tracer.record(
                    tool_name=tool_name,
                    state=ToolExecutionState.SUCCEEDED,
                    call_id=call_id,
                    parent_event_id=running_event.event_id,
                )
            except Exception as exc:
                end_event = self.tracer.record(
                    tool_name=tool_name,
                    state=ToolExecutionState.FAILED,
                    call_id=call_id,
                    parent_event_id=start_event.event_id,
                    metadata={"error_type": type(exc).__name__, "error": str(exc)},
                )
                raise
        if self.return_trace:
            return ToolCallResult(value=value, call_id=call_id, start_event=start_event, end_event=end_event)
        return value

    async def _execute_async(
        self,
        tool_name: str,
        tool: Callable[..., Awaitable[T]],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        *,
        authority_scope: Mapping[str, Any] | None,
        actor: str | None,
    ) -> T | ToolCallResult:
        call_id = uuid4().hex
        with self.runtime.delegate(tool_name, actor=actor, authority_scope=authority_scope):
            start_event = self.tracer.record(
                tool_name=tool_name,
                state=ToolExecutionState.REQUESTED,
                call_id=call_id,
            )
            try:
                running_event = self.tracer.record(
                    tool_name=tool_name,
                    state=ToolExecutionState.RUNNING,
                    call_id=call_id,
                    parent_event_id=start_event.event_id,
                )
                value = await tool(*args, **kwargs)
                end_event = self.tracer.record(
                    tool_name=tool_name,
                    state=ToolExecutionState.SUCCEEDED,
                    call_id=call_id,
                    parent_event_id=running_event.event_id,
                )
            except Exception as exc:
                end_event = self.tracer.record(
                    tool_name=tool_name,
                    state=ToolExecutionState.FAILED,
                    call_id=call_id,
                    parent_event_id=start_event.event_id,
                    metadata={"error_type": type(exc).__name__, "error": str(exc)},
                )
                raise
        if self.return_trace:
            return ToolCallResult(value=value, call_id=call_id, start_event=start_event, end_event=end_event)
        return value
