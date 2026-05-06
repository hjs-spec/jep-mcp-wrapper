"""Deterministic JEP event model and hashing utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
from typing import Any, Mapping
from uuid import uuid4


class ToolExecutionState(str, Enum):
    """Lifecycle states recorded for MCP tool execution."""

    REQUESTED = "requested"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DELEGATED = "delegated"


def _canonical_json(payload: Mapping[str, Any]) -> str:
    """Serialize a mapping into deterministic JSON for stable event hashes."""

    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def deterministic_hash(payload: Mapping[str, Any]) -> str:
    """Return a SHA-256 digest for a canonical JSON payload."""

    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class JEPEvent:
    """Append-only accountability event for an MCP tool execution step."""

    event_id: str
    tool_name: str
    actor: str
    delegation_lineage: tuple[str, ...]
    authority_scope: Mapping[str, Any]
    execution_state: ToolExecutionState
    sequence: int
    prev_hash: str | None = None
    parent_event_id: str | None = None
    call_id: str = field(default_factory=lambda: uuid4().hex)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    event_hash: str | None = None

    @classmethod
    def create(
        cls,
        *,
        tool_name: str,
        actor: str,
        delegation_lineage: tuple[str, ...],
        authority_scope: Mapping[str, Any],
        execution_state: ToolExecutionState,
        sequence: int,
        prev_hash: str | None,
        parent_event_id: str | None = None,
        call_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "JEPEvent":
        """Create an event and deterministically seal it with an event hash."""

        event = cls(
            event_id=uuid4().hex,
            tool_name=tool_name,
            actor=actor,
            delegation_lineage=delegation_lineage,
            authority_scope=dict(authority_scope),
            execution_state=execution_state,
            sequence=sequence,
            prev_hash=prev_hash,
            parent_event_id=parent_event_id,
            call_id=call_id or uuid4().hex,
            metadata=dict(metadata or {}),
        )
        return event.with_hash()

    def hash_payload(self) -> dict[str, Any]:
        """Return the exact event fields covered by the deterministic hash."""

        return {
            "actor": self.actor,
            "authority_scope": dict(self.authority_scope),
            "call_id": self.call_id,
            "delegation_lineage": list(self.delegation_lineage),
            "event_id": self.event_id,
            "execution_state": self.execution_state.value,
            "metadata": dict(self.metadata),
            "parent_event_id": self.parent_event_id,
            "prev_hash": self.prev_hash,
            "sequence": self.sequence,
            "tool_name": self.tool_name,
        }

    def compute_hash(self) -> str:
        """Compute this event's deterministic hash."""

        return deterministic_hash(self.hash_payload())

    def with_hash(self) -> "JEPEvent":
        """Return a copy with its event_hash populated from sealed fields."""

        return JEPEvent(
            event_id=self.event_id,
            tool_name=self.tool_name,
            actor=self.actor,
            delegation_lineage=self.delegation_lineage,
            authority_scope=dict(self.authority_scope),
            execution_state=self.execution_state,
            sequence=self.sequence,
            prev_hash=self.prev_hash,
            parent_event_id=self.parent_event_id,
            call_id=self.call_id,
            metadata=dict(self.metadata),
            event_hash=self.compute_hash(),
        )

    def to_record(self) -> dict[str, Any]:
        """Serialize this event for JSONL archive storage."""

        event_hash = self.event_hash or self.compute_hash()
        return {**self.hash_payload(), "event_hash": event_hash}

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "JEPEvent":
        """Deserialize an event record from JSONL archive storage."""

        return cls(
            event_id=str(record["event_id"]),
            tool_name=str(record["tool_name"]),
            actor=str(record["actor"]),
            delegation_lineage=tuple(record.get("delegation_lineage", ())),
            authority_scope=dict(record.get("authority_scope", {})),
            execution_state=ToolExecutionState(record["execution_state"]),
            sequence=int(record["sequence"]),
            prev_hash=record.get("prev_hash"),
            parent_event_id=record.get("parent_event_id"),
            call_id=str(record["call_id"]),
            metadata=dict(record.get("metadata", {})),
            event_hash=record.get("event_hash"),
        )
