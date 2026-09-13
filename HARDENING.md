# Implementation hardening — September 2026

Append concurrent tool traces without stale sequence/hash state.

## Changes

Sequence assignment, archive refresh and append run under one file lock shared across instances and processes. Readers also acquire that lock. Async cancellation records a terminal failure. Replay rejects a terminal-only call and requires parent events to precede children.

## Validation

```sh
python -m pytest -q
```

## Compatibility and remaining limits

A sidecar .lock file is created beside archives. Existing event hashes are retained. The archive still scans existing records on append; large-archive indexing and distributed storage are follow-up work. These are runtime envelopes, not signed v0.6 wire events.
