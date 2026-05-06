# jep-mcp-wrapper

`jep-mcp-wrapper` adds verifiable accountability semantics to MCP tool execution without changing the MCP protocol. Existing tool callables are wrapped in a side-channel JEP runtime that emits deterministic, append-only events for each execution lifecycle step.

## What it provides

- `JEPMCPWrapper` wraps sync and async MCP tool callables.
- `MCPExecutionTracer` writes lifecycle events (`requested`, `running`, `succeeded`, `failed`).
- `ToolDelegationRuntime` tracks the active actor, delegation lineage, parent context, and authority scope across nested tool calls.
- `ReplayVerifier` replays archived execution chains, verifies lineage, validates deterministic hashes, and detects archive tampering.
- `AppendOnlyEventArchive` stores JSONL events as an append-only hash chain.

The wrapper records:

- `tool_name`
- `actor`
- delegation lineage
- authority scope
- execution state
- parent event linkage
- deterministic event hash and previous hash

## Quick start

```python
from pathlib import Path
from jep_mcp_wrapper import JEPMCPWrapper, ReplayVerifier

archive = "jep-events.jsonl"
wrapper = JEPMCPWrapper(
    archive,
    default_actor="agent:file-reader",
    default_authority_scope={"filesystem": "read-only"},
)

def read_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")

read_file = wrapper.wrap_tool("filesystem.read_file", read_file)
print(read_file("README.md"))

replay = ReplayVerifier(archive).replay()
assert replay.verified
```

## Chained delegation

Nested wrapped calls automatically extend lineage. A `search.query` tool that calls a wrapped `browser.fetch` tool produces two execution chains: one with `("search.query",)` and one with `("search.query", "browser.fetch")`.

```python
from jep_mcp_wrapper import JEPMCPWrapper

wrapper = JEPMCPWrapper("events.jsonl", default_actor="agent:researcher")

def browser_fetch(url: str) -> str:
    return f"page:{url}"

def search(query: str, fetch) -> str:
    return fetch(f"https://example.test?q={query}")

fetch = wrapper.wrap_tool("browser.fetch", browser_fetch, authority_scope={"network": "example.test"})
search = wrapper.wrap_tool("search.query", search, authority_scope={"purpose": "research"})
search("accountability", fetch=fetch)
```

## Replay and tamper detection

```python
from jep_mcp_wrapper import ReplayVerifier

verifier = ReplayVerifier("events.jsonl")
result = verifier.replay()
print(result.verified)
print(result.lineage_by_call)
print(verifier.detect_tampering())
```

Replay verification checks:

1. deterministic hash equality for every event,
2. previous-hash continuity across the append-only archive,
3. monotonic event sequence numbers,
4. valid tool lifecycle transitions,
5. stable lineage for every tool call,
6. parent/child lineage consistency when parent links are present.

## Examples

- `examples/filesystem_tool.py` wraps a filesystem read tool.
- `examples/browser_search_chain.py` wraps browser and search tools with chained delegation.

## Non-goals

- It does not modify MCP protocol schemas or wire semantics.
- It does not implement an orchestration framework.
- It does not decide whether a tool is authorized; it records the declared authority scope so execution can be audited and replayed.
