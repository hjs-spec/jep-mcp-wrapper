# jep-mcp-wrapper

`jep-mcp-wrapper` records MCP tool execution for inspection and replay without changing the MCP protocol. It wraps existing tool callables, tracks declared actors and delegation context, and writes lifecycle records to a local hash-linked JSONL archive.

## Event format and verification scope

This package emits **local runtime envelopes**, not signed [JEP-Core v0.6](https://github.com/hjs-spec/jep-v06) wire events. Its lifecycle fields and hash serialization belong to this adapter. It does not produce detached-JWS signatures or perform JEP-Core signature and key-trust validation; interoperable Core events require a separately specified mapping and signing implementation.

`ReplayVerifier.replay().verified` reports the archive checks listed below: hashes, sequence, lifecycle, and recorded lineage. It does not authenticate the declared actor, establish that a delegation was authorized, or verify a tool result against the external world. Authority scope is recorded context.

## What it provides

- `JEPMCPWrapper` wraps sync and async MCP tool callables.
- `MCPExecutionTracer` writes lifecycle events (`requested`, `running`, `succeeded`, `failed`).
- `ToolDelegationRuntime` tracks the active actor, delegation lineage, parent context, and authority scope across nested tool calls.
- `ReplayVerifier` checks archived execution chains for inconsistent hashes, links, lifecycle transitions, and recorded lineage.
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

## Replay and archive consistency

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

The writer appends records, but an unkeyed hash chain alone cannot rule out a complete rewrite or removal of a valid suffix. Detecting those changes requires an independently trusted checkpoint or other external evidence of the expected history.

## Examples

- `examples/filesystem_tool.py` wraps a filesystem read tool.
- `examples/browser_search_chain.py` wraps browser and search tools with chained delegation.

## Non-goals

- It does not modify MCP protocol schemas or wire semantics.
- It does not implement an orchestration framework.
- It does not decide whether a tool is authorized; it records the declared authority scope so execution can be audited and replayed.

## Runtime and verification notes

See [HARDENING.md](HARDENING.md) for concurrency, cancellation, archive validation, and compatibility boundaries.
