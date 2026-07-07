# Storage Architecture

UPII uses LanceDB as its local, embedded vector store — no external database
server is required. Document and chunk metadata (paths, hashes, offsets) live in a
SQLite database alongside it. Everything is content-addressed so re-ingesting the
same corpus converges to an identical on-disk state.
