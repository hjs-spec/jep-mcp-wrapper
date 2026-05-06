"""Append-only event archive for JEP MCP wrapper events."""

from __future__ import annotations

import json
from pathlib import Path
from threading import RLock
from typing import Iterable

from .events import JEPEvent


class ArchiveTamperError(RuntimeError):
    """Raised when an archive's existing hash chain is invalid."""


class AppendOnlyEventArchive:
    """JSONL archive that only appends events and validates existing chains."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._last_hash: str | None = None
        self._next_sequence = 0
        self._load_and_validate()

    @property
    def last_hash(self) -> str | None:
        return self._last_hash

    @property
    def next_sequence(self) -> int:
        return self._next_sequence

    def append(self, event: JEPEvent) -> JEPEvent:
        """Append a single event after enforcing sequence and hash continuity."""

        with self._lock:
            self._load_and_validate()
            if event.sequence != self._next_sequence:
                raise ArchiveTamperError(
                    f"event sequence {event.sequence} does not match next sequence {self._next_sequence}"
                )
            if event.prev_hash != self._last_hash:
                raise ArchiveTamperError("event prev_hash does not match archive tail")
            sealed = event.with_hash()
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(sealed.to_record(), sort_keys=True, ensure_ascii=False) + "\n")
            self._last_hash = sealed.event_hash
            self._next_sequence += 1
            return sealed

    def read_events(self) -> list[JEPEvent]:
        """Read all events from the archive."""

        if not self.path.exists():
            return []
        events: list[JEPEvent] = []
        with self.path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(JEPEvent.from_record(json.loads(line)))
                except (KeyError, json.JSONDecodeError, ValueError) as exc:
                    raise ArchiveTamperError(f"invalid archive record at line {line_number}") from exc
        return events

    def _load_and_validate(self) -> None:
        previous_hash: str | None = None
        expected_sequence = 0
        for event in self.read_events():
            _validate_event(event, expected_sequence, previous_hash)
            previous_hash = event.event_hash
            expected_sequence += 1
        self._last_hash = previous_hash
        self._next_sequence = expected_sequence


def _validate_event(event: JEPEvent, expected_sequence: int, previous_hash: str | None) -> None:
    if event.sequence != expected_sequence:
        raise ArchiveTamperError(
            f"event sequence {event.sequence} does not match expected sequence {expected_sequence}"
        )
    if event.prev_hash != previous_hash:
        raise ArchiveTamperError("event prev_hash breaks archive hash chain")
    if event.event_hash != event.compute_hash():
        raise ArchiveTamperError("event_hash does not match deterministic event payload")


def validate_events(events: Iterable[JEPEvent]) -> None:
    """Validate sequence numbers, event hashes, and hash-chain continuity."""

    previous_hash: str | None = None
    for expected_sequence, event in enumerate(events):
        _validate_event(event, expected_sequence, previous_hash)
        previous_hash = event.event_hash
