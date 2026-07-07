# Observability

We log per-query latency and the source signal (vector / calendar / entity) that
produced each result. Daily metrics roll up query counts and ingest counts into a
local SQLite table; nothing is exported.
