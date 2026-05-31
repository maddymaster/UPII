# Project Omega: Kickoff Meeting
Date: 2025-10-15

## Overview
Project Omega aims to revolutionize personal memory through local-first AI.
We agreed on a hybrid architecture using LanceDB and SQLite.


## Key Decisions
- Decision: Use `sentence-transformers` for embeddings to keep latency under 100ms.
- Decision: No cloud syncing in v1.0. Privacy is paramount.
- Decision: The CLI name will be `upii`.
- Discussed with Veena that we have to purchase a new license for our cloud service.

## Action Items
- [ ] Research optimal chunk header size
- [ ] Select quantization level for LLM
- [ ] Send email to buy subscription
