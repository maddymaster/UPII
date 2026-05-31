import hashlib

def compute_hash(content: str) -> str:
    """Computes SHA-256 hash of the content string."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()
