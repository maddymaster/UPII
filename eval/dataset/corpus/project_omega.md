# Project Omega — Embedding Model Decision

For Project Omega we evaluated several sentence-embedding models and chose
`all-MiniLM-L6-v2`. The deciding factor was on-device inference latency: it runs
in well under our budget on a laptop CPU while still producing 384-dimensional
vectors with strong retrieval quality. Larger models (e5-large, bge-large) scored
marginally higher on recall but were 4-6x slower and too big to ship locally.
Decision owner: Maddy. Status: accepted.
