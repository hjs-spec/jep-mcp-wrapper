"""Browser/search delegation example without modifying MCP protocol payloads."""

from pathlib import Path
from tempfile import TemporaryDirectory

from jep_mcp_wrapper import JEPMCPWrapper, ReplayVerifier


def browser_fetch(url: str) -> str:
    return f"<html><title>{url}</title></html>"


def search(query: str, fetch) -> list[str]:
    page = fetch(f"https://example.test/search?q={query}")
    return [page]


def main() -> None:
    with TemporaryDirectory() as directory:
        archive = Path(directory) / "events.jsonl"
        wrapper = JEPMCPWrapper(
            archive,
            default_actor="agent:researcher",
            default_authority_scope={"network": "example.test"},
        )
        fetch = wrapper.wrap_tool("browser.fetch", browser_fetch, authority_scope={"http_method": "GET"})
        accountable_search = wrapper.wrap_tool("search.query", search, authority_scope={"purpose": "research"})

        print(accountable_search("jep", fetch=fetch))
        replay = ReplayVerifier(archive).replay()
        print(replay.verified)
        print(replay.lineage_by_call)


if __name__ == "__main__":
    main()
