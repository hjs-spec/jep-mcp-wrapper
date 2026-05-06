"""JEP accountability semantics for MCP tool execution.

The package wraps existing MCP tool callables without changing the MCP protocol.
"""

from .archive import AppendOnlyEventArchive, ArchiveTamperError
from .events import JEPEvent, ToolExecutionState, deterministic_hash
from .runtime import DelegationContext, ToolDelegationRuntime
from .tracer import MCPExecutionTracer
from .verifier import ReplayResult, ReplayVerifier
from .wrapper import JEPMCPWrapper, ToolCallResult

__all__ = [
    "AppendOnlyEventArchive",
    "ArchiveTamperError",
    "DelegationContext",
    "JEPEvent",
    "JEPMCPWrapper",
    "MCPExecutionTracer",
    "ReplayResult",
    "ReplayVerifier",
    "ToolCallResult",
    "ToolDelegationRuntime",
    "ToolExecutionState",
    "deterministic_hash",
]
