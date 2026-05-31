from sentence_transformers import SentenceTransformer
import torch
print("Imported.")
print(f"Torch MPS available: {torch.backends.mps.is_available()}")
model = SentenceTransformer('all-MiniLM-L6-v2')
print("Model loaded.")
emb = model.encode("Hello world")
print(f"Embedding shape: {emb.shape}")
