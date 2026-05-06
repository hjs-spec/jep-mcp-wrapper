from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from jep_mcp_wrapper import JEPMCPWrapper, ReplayVerifier, ToolExecutionState


def test_wrap_tool_records_accountability_events(tmp_path: Path) -> None:
    archive = tmp_path / "events.jsonl"
    wrapper = JEPMCPWrapper(
        archive,
        default_actor="agent:test",
        default_authority_scope={"filesystem": "read-only"},
        return_trace=True,
    )

    def read_file(path: str) -> str:
        return Path(path).read_text(encoding="utf-8")

    target = tmp_path / "note.txt"
    target.write_text("hello", encoding="utf-8")
    result = wrapper.wrap_tool("filesystem.read_file", read_file)(str(target))

    assert result.value == "hello"
    replay = ReplayVerifier(archive).replay()
    assert replay.verified, replay.errors
    assert len(replay.events) == 3
    assert [event.execution_state for event in replay.events] == [
        ToolExecutionState.REQUESTED,
        ToolExecutionState.RUNNING,
        ToolExecutionState.SUCCEEDED,
    ]
    assert all(event.tool_name == "filesystem.read_file" for event in replay.events)
    assert all(event.actor == "agent:test" for event in replay.events)
    assert all(event.delegation_lineage == ("filesystem.read_file",) for event in replay.events)
    assert all(event.authority_scope["filesystem"] == "read-only" for event in replay.events)


def test_chained_tool_delegation_replays_lineage(tmp_path: Path) -> None:
    archive = tmp_path / "events.jsonl"
    wrapper = JEPMCPWrapper(archive, default_actor="agent:researcher")

    def browser_fetch(url: str) -> str:
        return f"page:{url}"

    def search(query: str, fetch) -> str:
        return fetch(f"https://example.test?q={query}")

    fetch = wrapper.wrap_tool("browser.fetch", browser_fetch, authority_scope={"network": "example.test"})
    accountable_search = wrapper.wrap_tool("search.query", search, authority_scope={"purpose": "test"})

    assert accountable_search("jep", fetch=fetch) == "page:https://example.test?q=jep"
    replay = ReplayVerifier(archive).replay()

    assert replay.verified, replay.errors
    lineages = set(replay.lineage_by_call.values())
    assert ("search.query",) in lineages
    assert ("search.query", "browser.fetch") in lineages
    assert ReplayVerifier(archive).verify_tool_lineage(("search.query",))


def test_failed_tool_records_failure_state(tmp_path: Path) -> None:
    archive = tmp_path / "events.jsonl"
    wrapper = JEPMCPWrapper(archive)

    def broken() -> None:
        raise ValueError("boom")

    with pytest.raises(ValueError):
        wrapper.call_tool("broken.tool", broken)

    replay = ReplayVerifier(archive).replay()
    assert replay.verified, replay.errors
    assert replay.events[-1].execution_state == ToolExecutionState.FAILED
    assert replay.events[-1].metadata["error_type"] == "ValueError"


def test_tampering_is_detected_by_deterministic_hash(tmp_path: Path) -> None:
    archive = tmp_path / "events.jsonl"
    wrapper = JEPMCPWrapper(archive)
    wrapper.call_tool("search.query", lambda: "ok")

    records = archive.read_text(encoding="utf-8").splitlines()
    first = json.loads(records[0])
    first["actor"] = "attacker"
    records[0] = json.dumps(first, sort_keys=True)
    archive.write_text("\n".join(records) + "\n", encoding="utf-8")

    replay = ReplayVerifier(archive).replay()
    assert not replay.verified
    assert ReplayVerifier(archive).detect_tampering()
    assert "tampering detected" in replay.errors[0]


def test_async_tool_is_wrapped(tmp_path: Path) -> None:
    archive = tmp_path / "events.jsonl"
    wrapper = JEPMCPWrapper(archive, default_actor="agent:async")

    async def browser_fetch(url: str) -> str:
        return f"async:{url}"

    async def run_wrapped() -> str:
        wrapped = wrapper.wrap_tool("browser.fetch", browser_fetch)
        return await wrapped("https://example.test")

    assert asyncio.run(run_wrapped()) == "async:https://example.test"

    replay = ReplayVerifier(archive).replay()
    assert replay.verified, replay.errors
    assert all(event.actor == "agent:async" for event in replay.events)
