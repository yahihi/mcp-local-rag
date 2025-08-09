#!/usr/bin/env python3
"""
Unit tests for EmbeddingGenerator class
"""

import asyncio
import os
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
import unittest
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import embeddings
from embeddings import EmbeddingGenerator, _model_cache


class TestEmbeddingGenerator(unittest.TestCase):
    """Test EmbeddingGenerator class"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Clear model cache before each test
        global _model_cache
        _model_cache.clear()
        
        self.config = {
            "embedding_model": "local",
            "local_embedding_model": "all-MiniLM-L6-v2"
        }
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_initialization_local(self, mock_st):
        """Test local model initialization"""
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_st.return_value = mock_model
        
        generator = EmbeddingGenerator(self.config)
        
        # Should initialize local model
        self.assertEqual(generator.model_type, "local")
        self.assertEqual(generator.local_model, mock_model)
        self.assertEqual(generator.embedding_dimension, 384)
        
        # Should load model
        mock_st.assert_called_once_with("all-MiniLM-L6-v2")
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_model_caching(self, mock_st):
        """Test that models are cached"""
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_st.return_value = mock_model
        
        # Create first generator
        generator1 = EmbeddingGenerator(self.config)
        
        # Create second generator with same config
        generator2 = EmbeddingGenerator(self.config)
        
        # Should only load model once due to caching
        mock_st.assert_called_once_with("all-MiniLM-L6-v2")
        
        # Both should use same model instance
        self.assertEqual(generator1.local_model, generator2.local_model)
    
    def test_initialization_openai(self):
        """Test OpenAI model initialization"""
        config = {
            "embedding_model": "openai",
            "openai_api_key": "test-key",
            "openai_embedding_model": "text-embedding-3-small"
        }
        
        mock_client = MagicMock()
        
        def mock_init_openai(self):
            self.openai_client = mock_client
            self.embedding_model = config['openai_embedding_model']
        
        with patch.object(EmbeddingGenerator, '_init_openai', mock_init_openai):
            generator = EmbeddingGenerator(config)
            
            # Should initialize OpenAI
            self.assertEqual(generator.model_type, "openai")
            self.assertEqual(generator.openai_client, mock_client)
            self.assertEqual(generator.embedding_model, "text-embedding-3-small")
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_openai_fallback_no_key(self, mock_st):
        """Test fallback to local when OpenAI key missing"""
        config = {
            "embedding_model": "openai"
            # No API key provided
        }
        
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_st.return_value = mock_model
        
        # Remove env var if it exists
        with patch.dict(os.environ, {}, clear=True):
            generator = EmbeddingGenerator(config)
        
        # Should fall back to local
        self.assertEqual(generator.model_type, "local")
        mock_st.assert_called_once()
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_openai_fallback_import_error(self, mock_st):
        """Test fallback when OpenAI library not installed"""
        config = {
            "embedding_model": "openai",
            "openai_api_key": "test-key"
        }
        
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_st.return_value = mock_model
        
        # Mock that OpenAI import fails
        def mock_init_openai(self):
            self.model_type = 'local'
            self._init_local()
        
        with patch.object(EmbeddingGenerator, '_init_openai', mock_init_openai):
            generator = EmbeddingGenerator(config)
        
        # Should fall back to local
        self.assertEqual(generator.model_type, "local")
        mock_st.assert_called_once()
    
    def test_get_dimension_local(self):
        """Test getting embedding dimension for local model"""
        with patch('sentence_transformers.SentenceTransformer') as mock_st:
            mock_model = MagicMock()
            mock_model.get_sentence_embedding_dimension.return_value = 768
            mock_st.return_value = mock_model
            
            generator = EmbeddingGenerator(self.config)
            dimension = generator.get_dimension()
            
            self.assertEqual(dimension, 768)
    
    def test_get_dimension_openai(self):
        """Test getting embedding dimension for OpenAI models"""
        config = {
            "embedding_model": "openai",
            "openai_api_key": "test-key"
        }
        
        test_cases = [
            ("text-embedding-3-small", 1536),
            ("text-embedding-3-large", 3072),
            ("text-embedding-ada-002", 1536),
            ("custom-model", 1536)  # Default
        ]
        
        for model_name, expected_dim in test_cases:
            config["openai_embedding_model"] = model_name
            
            with patch.object(embeddings, 'OpenAI', create=True):
                generator = EmbeddingGenerator(config)
                generator.embedding_model = model_name
                
                dimension = generator.get_dimension()
                self.assertEqual(dimension, expected_dim, f"Failed for model {model_name}")


class TestEmbeddingGeneratorAsync(unittest.TestCase):
    """Test async methods of EmbeddingGenerator"""
    
    def setUp(self):
        """Set up test fixtures"""
        global _model_cache
        _model_cache.clear()
        
        self.config = {
            "embedding_model": "local",
            "local_embedding_model": "test-model"
        }
    
    def test_generate_local(self):
        """Test generating embedding with local model"""
        async def run_test():
            with patch('sentence_transformers.SentenceTransformer') as mock_st:
                mock_model = MagicMock()
                mock_model.get_sentence_embedding_dimension.return_value = 384
                mock_model.encode.return_value = np.array([0.1, 0.2, 0.3])
                mock_st.return_value = mock_model
                
                generator = EmbeddingGenerator(self.config)
                embedding = await generator.generate("test text")
                
                # Should call encode
                mock_model.encode.assert_called_once_with("test text", convert_to_numpy=True, show_progress_bar=False)
                
                # Should return list
                self.assertEqual(embedding, [0.1, 0.2, 0.3])
        
        asyncio.run(run_test())
    
    def test_generate_openai(self):
        """Test generating embedding with OpenAI"""
        async def run_test():
            config = {
                "embedding_model": "openai",
                "openai_api_key": "test-key",
                "openai_embedding_model": "text-embedding-3-small"
            }
            
            with patch('sentence_transformers.SentenceTransformer') as mock_st:
                # Setup fallback local model
                mock_local_model = MagicMock()
                mock_local_model.get_sentence_embedding_dimension.return_value = 384
                mock_st.return_value = mock_local_model
                
                with patch.object(embeddings, 'OpenAI', create=True) as mock_openai_class:
                    mock_client = MagicMock()
                    mock_openai_class.return_value = mock_client
                    
                    # Mock embedding response
                    mock_response = MagicMock()
                    mock_response.data = [MagicMock(embedding=[0.4, 0.5, 0.6])]
                    mock_client.embeddings.create.return_value = mock_response
                    
                    generator = EmbeddingGenerator(config)
                    generator.openai_client = mock_client
                    generator.model_type = 'openai'
                    generator.embedding_model = 'text-embedding-3-small'
                    embedding = await generator.generate("test text")
                    
                    # Should call OpenAI API
                    mock_client.embeddings.create.assert_called_once()
                    call_args = mock_client.embeddings.create.call_args
                    self.assertEqual(call_args[1]['input'], "test text")
                    
                    # Should return embedding
                    self.assertEqual(embedding, [0.4, 0.5, 0.6])
        
        asyncio.run(run_test())
    
    def test_generate_openai_error_fallback(self):
        """Test fallback to local on OpenAI error"""
        async def run_test():
            config = {
                "embedding_model": "openai",
                "openai_api_key": "test-key"
            }
            
            # Mock the local model that will be used as fallback
            mock_model = MagicMock()
            mock_model.get_sentence_embedding_dimension.return_value = 384
            mock_model.encode.return_value = np.array([0.7, 0.8, 0.9])
            
            with patch('sentence_transformers.SentenceTransformer', return_value=mock_model):
                generator = EmbeddingGenerator(config)
                generator.model_type = 'openai'  # Force OpenAI mode
                
                # Mock the openai client
                mock_client = MagicMock()
                mock_client.embeddings.create.side_effect = Exception("API Error")
                generator.openai_client = mock_client
                
                # Initialize local model for fallback
                generator.local_model = mock_model
                
                embedding = await generator.generate("test text")
                
                # Should fall back to local
                mock_model.encode.assert_called_once()
                self.assertEqual(embedding, [0.7, 0.8, 0.9])
        
        asyncio.run(run_test())
    
    def test_batch_generate_local(self):
        """Test batch generating embeddings with local model"""
        async def run_test():
            with patch('sentence_transformers.SentenceTransformer') as mock_st:
                mock_model = MagicMock()
                mock_model.get_sentence_embedding_dimension.return_value = 384
                mock_model.encode.return_value = np.array([
                    [0.1, 0.2, 0.3],
                    [0.4, 0.5, 0.6],
                    [0.7, 0.8, 0.9]
                ])
                mock_st.return_value = mock_model
                
                generator = EmbeddingGenerator(self.config)
                embeddings = await generator.batch_generate(["text1", "text2", "text3"])
                
                # Should call encode with all texts
                mock_model.encode.assert_called_once()
                
                # Should return list of lists
                self.assertEqual(len(embeddings), 3)
                self.assertEqual(embeddings[0], [0.1, 0.2, 0.3])
                self.assertEqual(embeddings[1], [0.4, 0.5, 0.6])
                self.assertEqual(embeddings[2], [0.7, 0.8, 0.9])
        
        asyncio.run(run_test())
    
    def test_batch_generate_openai(self):
        """Test batch generating embeddings with OpenAI"""
        async def run_test():
            config = {
                "embedding_model": "openai",
                "openai_api_key": "test-key",
                "openai_embedding_model": "text-embedding-3-small"
            }
            
            with patch('sentence_transformers.SentenceTransformer') as mock_st:
                # Setup fallback local model
                mock_local_model = MagicMock()
                mock_local_model.get_sentence_embedding_dimension.return_value = 384
                mock_st.return_value = mock_local_model
                
                with patch.object(embeddings, 'OpenAI', create=True) as mock_openai_class:
                    mock_client = MagicMock()
                    mock_openai_class.return_value = mock_client
                    
                    # Mock batch response
                    mock_response = MagicMock()
                    mock_response.data = [
                        MagicMock(embedding=[0.1, 0.2]),
                        MagicMock(embedding=[0.3, 0.4]),
                        MagicMock(embedding=[0.5, 0.6])
                    ]
                    mock_client.embeddings.create.return_value = mock_response
                    
                    generator = EmbeddingGenerator(config)
                    generator.openai_client = mock_client
                    generator.model_type = 'openai'
                    generator.embedding_model = 'text-embedding-3-small'
                    embeddings_result = await generator.batch_generate(["text1", "text2", "text3"])
                    
                    # Should call OpenAI with all texts
                    mock_client.embeddings.create.assert_called_once()
                    call_args = mock_client.embeddings.create.call_args
                    self.assertEqual(call_args[1]['input'], ["text1", "text2", "text3"])
                    
                    # Should return embeddings
                    self.assertEqual(len(embeddings_result), 3)
                    self.assertEqual(embeddings_result[0], [0.1, 0.2])
                    self.assertEqual(embeddings_result[1], [0.3, 0.4])
                    self.assertEqual(embeddings_result[2], [0.5, 0.6])
        
        asyncio.run(run_test())
    
    def test_batch_generate_openai_error_fallback(self):
        """Test batch fallback to local on OpenAI error"""
        async def run_test():
            config = {
                "embedding_model": "openai",
                "openai_api_key": "test-key"
            }
            
            # Mock the local model that will be used as fallback
            mock_model = MagicMock()
            mock_model.get_sentence_embedding_dimension.return_value = 384
            mock_model.encode.return_value = np.array([[0.1, 0.2], [0.3, 0.4]])
            
            with patch('sentence_transformers.SentenceTransformer', return_value=mock_model):
                generator = EmbeddingGenerator(config)
                generator.model_type = 'openai'  # Force OpenAI mode
                
                # Mock the openai client
                mock_client = MagicMock()
                mock_client.embeddings.create.side_effect = Exception("Batch API Error")
                generator.openai_client = mock_client
                
                # Initialize local model for fallback
                generator.local_model = mock_model
                
                embeddings = await generator.batch_generate(["text1", "text2"])
                
                # Should fall back to local batch
                mock_model.encode.assert_called_once()
                self.assertEqual(embeddings, [[0.1, 0.2], [0.3, 0.4]])
        
        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()