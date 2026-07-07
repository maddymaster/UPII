# Retrieval Performance SLO

Our service-level objective for context retrieval is a p95 latency of 100ms for a
top-10 query on a warm index. Cold-start (first query after launch) is allowed up
to 800ms while the embedding model loads. Memory budget for the resident index is
capped at 500MB. These targets are what the rehydrator must meet before the grant
demo.
