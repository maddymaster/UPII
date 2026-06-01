import sys
import os
import shutil
import uuid
import datetime

# Ensure we use local src if running from repo root
sys.path.insert(0, os.path.abspath("src"))

from upii.storage.db import DB
from upii.storage.vector import LocalVectorStore
from upii.ingestion.chunker import RecursiveChunker
from upii.analysis.embeddings import Embedder
from upii.core.types import Document

def reset_and_seed():
    print(">>> 1. Cleaning up Databases...")
    if os.path.exists("upii.db"):
        os.remove("upii.db")
        print("    Removed upii.db")
    
    if os.path.exists("upii_vectors"):
        shutil.rmtree("upii_vectors")
        print("    Removed upii_vectors/")

    print("\n>>> 2. Initializing Fresh DB...")
    db = DB()
    db.init_db()

    print("\n>>> 3. Creating Demo Content (Ambee Dataset)...")
    
    DEMO_DIR = "demo_data_v2"
    if not os.path.exists(DEMO_DIR):
        print(f"    ERROR: {DEMO_DIR} does not exist.")
        sys.exit(1)
        
    files = [f for f in os.listdir(DEMO_DIR) if f.endswith(".md") or f.endswith(".txt")]
    print(f"    Found {len(files)} files to ingest.")
    
    docs_to_embed = []
    
    for filename in files:
        path = os.path.join(DEMO_DIR, filename)
        with open(path, "r") as f:
            content = f.read()

        # Honour YAML frontmatter (e.g. author:) so self-authored style works.
        from upii.ingestion.loader import parse_frontmatter
        fm_meta, body = parse_frontmatter(content)

        meta = {"demo": "true", "filename": filename}
        meta.update(fm_meta)

        doc = Document(
            path=path,
            content_hash=f"seed_{filename}_{uuid.uuid4()}",
            content=body,
            created_at=datetime.datetime.now(),
            source_type="md",
            metadata=meta
        )
        doc.doc_id = str(uuid.uuid4())
        docs_to_embed.append(doc)
        print(f"    Prepared: {filename}")

    # Process all docs
    for doc in docs_to_embed:
        print(f"    Processing {doc.metadata['filename']}...")
        chunker = RecursiveChunker()
        chunks = chunker.chunk(doc)
        
        embedder = Embedder()
        texts = [c.text for c in chunks]
        embeddings = embedder.embed(texts)
        
        for i, c in enumerate(chunks):
            c.embedding = embeddings[i]

        db.upsert_document(doc, doc.doc_id)
        db.add_chunks(chunks)
        
        vec_store = LocalVectorStore()
        vec_store.add(chunks)
    
    print("\n>>> 4. Verifying Search...")
    from upii.analysis.search import SearchEngine
    se = SearchEngine()
    results = se.search("ICEYE", limit=1) # Updated check for new data
    if results:
        print(f"    SUCCESS: Found {len(results)} chunk(s).")
        print(f"    Preview: {results[0].text[:50]}...")
    else:
        print("    FAIL: No results found after seed.")
        sys.exit(1)

    print("\n>>> DEMO RESET COMPLETE. <<<")

if __name__ == "__main__":
    try:
        reset_and_seed()
    except Exception as e:
        print(f"\nCRASH: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
