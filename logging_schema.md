# Inkly JSONL Logging Schema (v1)

Each line in a log file is a single JSON object.

## Required top-level fields

- schema_version: int
- event_type: string
- timestamp: ISO 8601 UTC string
- session: object
- payload: object

## Event types (v1)

- session_start
- session_end
- user_prompt
- ai_response
- guardrail_block
- error

## Session object

- session_id: string (random per ink invocation)
- user_id: string or null (hashed username or null)
- host: string (hostname)
- pid: int (process ID)

## Payload rules

- Payload is event-type specific
- Payload must not include secrets or raw filesystem dumps
- Payload must be JSON-serializable
