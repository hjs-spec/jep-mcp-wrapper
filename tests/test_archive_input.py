import pytest
from jep_mcp_wrapper.archive import AppendOnlyEventArchive, ArchiveTamperError


def test_non_object_archive_record_is_reported_as_corruption(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text("null\n")
    with pytest.raises(ArchiveTamperError): AppendOnlyEventArchive(path)
