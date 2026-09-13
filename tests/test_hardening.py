import asyncio
from concurrent.futures import ThreadPoolExecutor
import pytest
from jep_mcp_wrapper import JEPMCPWrapper
from jep_mcp_wrapper.archive import validate_events


def test_multiple_instances_append_to_one_valid_archive(tmp_path):
    path = str(tmp_path / "events.jsonl")
    wrappers = [JEPMCPWrapper(path) for _ in range(4)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(lambda w: w.call_tool("read", lambda: 42), wrappers)) == [42] * 4
    events = wrappers[0].archive.read_events()
    assert len(events) == 12
    validate_events(events)


@pytest.mark.asyncio
async def test_cancelled_call_records_terminal_failure(tmp_path):
    wrapper = JEPMCPWrapper(str(tmp_path / "events.jsonl"))
    started = asyncio.Event()

    async def tool():
        started.set()
        await asyncio.Event().wait()

    task = asyncio.create_task(wrapper.call_tool_async("wait", tool))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    events = wrapper.archive.read_events()
    assert events[-1].execution_state.value == "failed"
    assert events[-1].metadata["error_type"] == "CancelledError"
    validate_events(events)


def test_terminal_only_call_does_not_verify(tmp_path):
    from jep_mcp_wrapper.events import ToolExecutionState
    from jep_mcp_wrapper.verifier import ReplayVerifier
    wrapper = JEPMCPWrapper(str(tmp_path / "events.jsonl"))
    wrapper.tracer.record(tool_name="tool", state=ToolExecutionState.SUCCEEDED, call_id="orphan")
    result = ReplayVerifier(wrapper.archive).replay()
    assert result.verified is False
    assert any("missing initial request" in error for error in result.errors)
