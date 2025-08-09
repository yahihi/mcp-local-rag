"""
Embedding generation for text chunks
"""

import logging
import os
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


# Global cache for the model to avoid multiple loads
_model_cache = {}


class EmbeddingGenerator:
    """Generate embeddings using OpenAI or local models"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.model_type = config.get('embedding_model', 'local')
        
        if self.model_type == 'openai':
            self._init_openai()
        else:
            self._init_local()
    
    def _init_openai(self):
        """Initialize OpenAI embeddings"""
        try:
            import openai
            from openai import OpenAI
            
            api_key = self.config.get('openai_api_key') or os.getenv('OPENAI_API_KEY')
            if not api_key:
                logger.warning("OpenAI API key not found, falling back to local model")
                self.model_type = 'local'
                self._init_local()
                return
            
            self.openai_client = OpenAI(api_key=api_key)
            self.embedding_model = self.config.get('openai_embedding_model', 'text-embedding-3-small')
            logger.info(f"Using OpenAI embeddings: {self.embedding_model}")
            
        except ImportError:
            logger.warning("OpenAI library not installed, falling back to local model")
            self.model_type = 'local'
            self._init_local()
    
    def _init_local(self):
        """Initialize local sentence-transformers model (with caching)"""
        global _model_cache
        
        try:
            from sentence_transformers import SentenceTransformer
            
            model_name = self.config.get('local_embedding_model', 'all-MiniLM-L6-v2')
            # Allow tuning batch size via config
            self.batch_size = int(self.config.get('embedding_batch_size', 32))
            
            # Check cache first
            if model_name not in _model_cache:
                logger.info(f"Loading embedding model: {model_name}")
                _model_cache[model_name] = SentenceTransformer(model_name)
                logger.info(f"Model loaded and cached: {model_name}")
            else:
                logger.info(f"Using cached embedding model: {model_name}")
            
            self.local_model = _model_cache[model_name]
            self.embedding_dimension = self.local_model.get_sentence_embedding_dimension()
            
        except ImportError:
            raise ImportError(
                "sentence-transformers not installed. "
                "Please install with: pip install sentence-transformers"
            )
    
    async def generate(self, text: str) -> List[float]:
        """Generate embedding for text"""
        if self.model_type == 'openai':
            return await self._generate_openai(text)
        else:
            return await self._generate_local(text)
    
    async def _generate_openai(self, text: str) -> List[float]:
        """Generate embedding using OpenAI"""
        try:
            response = self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error generating OpenAI embedding: {e}")
            # Fall back to local model
            return await self._generate_local(text)
    
    async def _generate_local(self, text: str) -> List[float]:
        """Generate embedding using local model"""
        # SentenceTransformer.encode() is synchronous
        embedding = self.local_model.encode(
            text,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return embedding.tolist()
    
    async def batch_generate(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        if self.model_type == 'openai':
            return await self._batch_generate_openai(texts)
        else:
            return await self._batch_generate_local(texts)
    
    async def _batch_generate_openai(self, texts: List[str]) -> List[List[float]]:
        """Batch generate embeddings using OpenAI"""
        try:
            response = self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=texts
            )
            return [data.embedding for data in response.data]
        except Exception as e:
            logger.error(f"Error generating OpenAI embeddings: {e}")
            # Fall back to local model
            return await self._batch_generate_local(texts)
    
    async def _batch_generate_local(self, texts: List[str]) -> List[List[float]]:
        """Batch generate embeddings using local model"""
        import time
        start = time.perf_counter()
        
        batch_size = getattr(self, 'batch_size', 32)
        logger.debug(f"Encoding {len(texts)} texts with batch_size={batch_size}")
        
        embeddings = self.local_model.encode(
            texts,
            convert_to_numpy=True,
            batch_size=batch_size,
            show_progress_bar=False,
        )
        
        elapsed = (time.perf_counter() - start) * 1000
        logger.debug(f"Encoded {len(texts)} texts in {elapsed:.1f}ms ({elapsed/len(texts):.1f}ms per text)")
        
        return embeddings.tolist()
    
    def get_dimension(self) -> int:
        """Get embedding dimension"""
        if self.model_type == 'openai':
            # OpenAI embeddings dimensions
            if 'ada' in self.embedding_model:
                return 1536
            elif 'text-embedding-3-small' in self.embedding_model:
                return 1536
            elif 'text-embedding-3-large' in self.embedding_model:
                return 3072
            else:
                return 1536  # default
        else:
            return self.embedding_dimension
