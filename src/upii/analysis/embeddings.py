from typing import List
from sentence_transformers import SentenceTransformer
from upii.core.config import config

class Embedder:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            model_name = getattr(config, 'embedding_model', 'all-MiniLM-L6-v2')
            cls._instance = SentenceTransformer(model_name)
        return cls._instance
        
    def embed(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        model = self.get_instance()
        embeddings = model.encode(texts, batch_size=batch_size, show_progress_bar=False)
        return embeddings.tolist()
