"""Filesystem tool example wrapped with JEP accountability semantics."""

from pathlib import Path
from tempfile import TemporaryDirectory

from jep_mcp_wrapper import JEPMCPWrapper, ReplayVerifier


def read_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def main() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        target = root / "note.txt"
        target.write_text("accountable filesystem read", encoding="utf-8")
        archive = root / "events.jsonl"

        wrapper = JEPMCPWrapper(
            archive,
            default_actor="agent:file-reader",
            default_authority_scope={"filesystem": "read-only", "root": str(root)},
        )
        wrapped_read_file = wrapper.wrap_tool("filesystem.read_file", read_file)
        print(wrapped_read_file(str(target)))
        print(ReplayVerifier(archive).replay().verified)


if __name__ == "__main__":
    main()
