#!/usr/bin/env python3
"""
Unit tests for VectorDB class
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import unittest
import shutil

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from vectordb import VectorDB


class TestVectorDB(unittest.TestCase):
    """Test VectorDB class"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        
        self.config = {
            "index_path": self.temp_dir,
            "collection_name": "test_collection"
        }
        
        # Mock ChromaDB client
        self.mock_client = MagicMock()
        self.mock_collection = MagicMock()
    
    def tearDown(self):
        """Clean up test fixtures"""
        # Remove temporary directory
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('vectordb.chromadb.PersistentClient')
    def test_initialization(self, mock_chromadb):
        """Test VectorDB initialization"""
        mock_chromadb.return_value = self.mock_client
        self.mock_client.get_collection.return_value = self.mock_collection
        
        vectordb = VectorDB(self.config)
        
        # Check that client was created with correct path
        mock_chromadb.assert_called_once()
        call_args = mock_chromadb.call_args
        self.assertIn('chroma', str(call_args[1]['path']))
        
        # Check that collection was retrieved or created
        self.mock_client.get_collection.assert_called_with(name="test_collection")
        
        # Check attributes
        self.assertEqual(vectordb.collection_name, "test_collection")
        self.assertEqual(vectordb.collection, self.mock_collection)
    
    @patch('vectordb.chromadb.PersistentClient')
    def test_initialization_creates_collection(self, mock_chromadb):
        """Test VectorDB creates collection if it doesn't exist"""
        mock_chromadb.return_value = self.mock_client
        self.mock_client.get_collection.side_effect = Exception("Collection not found")
        self.mock_client.create_collection.return_value = self.mock_collection
        
        vectordb = VectorDB(self.config)
        
        # Should try to get collection first
        self.mock_client.get_collection.assert_called_with(name="test_collection")
        
        # Should create collection when get fails
        self.mock_client.create_collection.assert_called_once()
        call_args = self.mock_client.create_collection.call_args
        self.assertEqual(call_args[1]['name'], "test_collection")
        self.assertIn('metadata', call_args[1])
    
    @patch('vectordb.chromadb.PersistentClient')
    def test_custom_collection_name(self, mock_chromadb):
        """Test using custom collection name"""
        mock_chromadb.return_value = self.mock_client
        self.mock_client.get_collection.return_value = self.mock_collection
        
        vectordb = VectorDB(self.config, collection_name="custom_collection")
        
        self.assertEqual(vectordb.collection_name, "custom_collection")
        self.mock_client.get_collection.assert_called_with(name="custom_collection")
    
    @patch('vectordb.chromadb.PersistentClient')
    def test_get_or_create_collection(self, mock_chromadb):
        """Test get_or_create_collection method"""
        mock_chromadb.return_value = self.mock_client
        mock_new_collection = MagicMock()
        
        # Setup: First get_collection for init, then for new_collection
        self.mock_client.get_collection.side_effect = [
            Exception("Not found"),  # Init call fails
            Exception("Not found"),  # new_collection call fails
        ]
        self.mock_client.create_collection.return_value = mock_new_collection
        
        vectordb = VectorDB(self.config)
        collection = vectordb.get_or_create_collection("new_collection")
        
        # Check the second create_collection call (first is for test_collection)
        calls = self.mock_client.create_collection.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1][1]['name'], "new_collection")
        self.assertEqual(calls[1][1]['metadata'], {"description": "Project index: new_collection"})
        self.assertEqual(collection, mock_new_collection)
        self.assertIn("new_collection", vectordb.collections_cache)
    
    @patch('vectordb.chromadb.PersistentClient')
    def test_get_or_create_collection_cached(self, mock_chromadb):
        """Test get_or_create_collection uses cache"""
        mock_chromadb.return_value = self.mock_client
        mock_cached_collection = MagicMock()
        
        vectordb = VectorDB(self.config)
        vectordb.collections_cache["cached_collection"] = mock_cached_collection
        
        collection = vectordb.get_or_create_collection("cached_collection")
        
        # Should return cached collection without creating
        self.assertEqual(collection, mock_cached_collection)
        self.mock_client.create_collection.assert_not_called()


class TestVectorDBAsync(unittest.TestCase):
    """Test async methods of VectorDB"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            "index_path": self.temp_dir,
            "collection_name": "test_collection"
        }
        
        self.mock_client = MagicMock()
        self.mock_collection = MagicMock()
    
    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('vectordb.chromadb.PersistentClient')
    def test_add_documents(self, mock_chromadb):
        """Test adding documents to collection"""
        mock_chromadb.return_value = self.mock_client
        self.mock_client.get_collection.return_value = self.mock_collection
        
        async def run_test():
            vectordb = VectorDB(self.config)
            
            documents = [
                {
                    "id": "doc1",
                    "content": "Test content 1",
                    "embedding": [0.1, 0.2, 0.3],
                    "metadata": {"file_path": "/test/file1.py"}
                },
                {
                    "id": "doc2",
                    "content": "Test content 2",
                    "embedding": [0.4, 0.5, 0.6],
                    "metadata": {"file_path": "/test/file2.py"}
                }
            ]
            
            await vectordb.add_documents(documents)
            
            # Check that add was called with correct parameters
            self.mock_collection.add.assert_called_once()
            call_args = self.mock_collection.add.call_args[1]
            
            self.assertEqual(call_args['ids'], ["doc1", "doc2"])
            self.assertEqual(call_args['documents'], ["Test content 1", "Test content 2"])
            self.assertEqual(len(call_args['embeddings']), 2)
            self.assertEqual(len(call_args['metadatas']), 2)
        
        asyncio.run(run_test())
    
    @patch('vectordb.chromadb.PersistentClient')
    def test_add_documents_to_specific_collection(self, mock_chromadb):
        """Test adding documents to a specific collection"""
        mock_chromadb.return_value = self.mock_client
        self.mock_client.get_collection.return_value = self.mock_collection
        mock_other_collection = MagicMock()
        
        async def run_test():
            vectordb = VectorDB(self.config)
            vectordb.collections_cache["other_collection"] = mock_other_collection
            
            documents = [
                {
                    "id": "doc1",
                    "content": "Test content",
                    "embedding": [0.1, 0.2, 0.3],
                    "metadata": {"file_path": "/test/file.py"}
                }
            ]
            
            await vectordb.add_documents(documents, collection_name="other_collection")
            
            # Should add to the specified collection, not default
            mock_other_collection.add.assert_called_once()
            self.mock_collection.add.assert_not_called()
        
        asyncio.run(run_test())
    
    @patch('vectordb.chromadb.PersistentClient')
    def test_search(self, mock_chromadb):
        """Test searching documents"""
        mock_chromadb.return_value = self.mock_client
        self.mock_client.get_collection.return_value = self.mock_collection
        
        # Mock query results
        self.mock_collection.query.return_value = {
            'ids': [['doc1', 'doc2']],
            'documents': [['Content 1', 'Content 2']],
            'metadatas': [[{'file_path': '/test/file1.py'}, {'file_path': '/test/file2.py'}]],
            'distances': [[0.1, 0.2]]
        }
        
        async def run_test():
            vectordb = VectorDB(self.config)
            
            results = await vectordb.search(
                query_embedding=[0.1, 0.2, 0.3],
                limit=5
            )
            
            # Check query was called correctly
            self.mock_collection.query.assert_called_once_with(
                query_embeddings=[[0.1, 0.2, 0.3]],
                n_results=5,
                where=None
            )
            
            # Check results format
            self.assertEqual(len(results), 2)
            self.assertEqual(results[0]['id'], 'doc1')
            self.assertEqual(results[0]['content'], 'Content 1')
            self.assertEqual(results[0]['metadata']['file_path'], '/test/file1.py')
            self.assertEqual(results[0]['score'], 0.9)  # 1 - distance
        
        asyncio.run(run_test())
    
    @patch('vectordb.chromadb.PersistentClient')
    def test_search_with_filter(self, mock_chromadb):
        """Test searching with metadata filter"""
        mock_chromadb.return_value = self.mock_client
        self.mock_client.get_collection.return_value = self.mock_collection
        
        self.mock_collection.query.return_value = {
            'ids': [['doc1']],
            'documents': [['Filtered content']],
            'metadatas': [[{'file_type': 'python'}]],
            'distances': [[0.15]]
        }
        
        async def run_test():
            vectordb = VectorDB(self.config)
            
            results = await vectordb.search(
                query_embedding=[0.1, 0.2, 0.3],
                limit=10,
                filter={'file_type': 'python'}
            )
            
            # Check filter was passed to query
            self.mock_collection.query.assert_called_once_with(
                query_embeddings=[[0.1, 0.2, 0.3]],
                n_results=10,
                where={'file_type': 'python'}
            )
            
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]['metadata']['file_type'], 'python')
        
        asyncio.run(run_test())
    
    @patch('vectordb.chromadb.PersistentClient')
    def test_delete_by_file(self, mock_chromadb):
        """Test deleting documents by file path"""
        mock_chromadb.return_value = self.mock_client
        self.mock_client.get_collection.return_value = self.mock_collection
        
        async def run_test():
            vectordb = VectorDB(self.config)
            
            await vectordb.delete_by_file("/test/file.py")
            
            # Check delete was called with correct filter
            self.mock_collection.delete.assert_called_once_with(
                where={"file_path": "/test/file.py"}
            )
        
        asyncio.run(run_test())
    
    @patch('vectordb.chromadb.PersistentClient')
    def test_delete_by_file_specific_collection(self, mock_chromadb):
        """Test deleting documents from specific collection"""
        mock_chromadb.return_value = self.mock_client
        self.mock_client.get_collection.return_value = self.mock_collection
        mock_other_collection = MagicMock()
        
        async def run_test():
            vectordb = VectorDB(self.config)
            vectordb.collections_cache["other_collection"] = mock_other_collection
            
            await vectordb.delete_by_file("/test/file.py", collection_name="other_collection")
            
            # Should delete from specified collection
            mock_other_collection.delete.assert_called_once_with(
                where={"file_path": "/test/file.py"}
            )
            self.mock_collection.delete.assert_not_called()
        
        asyncio.run(run_test())
    
    @patch('vectordb.chromadb.PersistentClient')
    def test_get_all_files(self, mock_chromadb):
        """Test getting all indexed files"""
        mock_chromadb.return_value = self.mock_client
        self.mock_client.get_collection.return_value = self.mock_collection
        
        # Mock getting all documents
        self.mock_collection.get.return_value = {
            'metadatas': [
                {'file_path': '/test/file1.py'},
                {'file_path': '/test/file2.py'},
                {'file_path': '/test/file1.py'},  # Duplicate
                {'file_path': '/test/file3.js'}
            ]
        }
        
        async def run_test():
            vectordb = VectorDB(self.config)
            
            files = await vectordb.get_all_files()
            
            # Should return unique file paths
            self.assertEqual(len(files), 3)
            self.assertIn('/test/file1.py', files)
            self.assertIn('/test/file2.py', files)
            self.assertIn('/test/file3.js', files)
            
            # Check that get was called
            self.mock_collection.get.assert_called_once()
        
        asyncio.run(run_test())
    
    @patch('vectordb.chromadb.PersistentClient')
    def test_clear_collection(self, mock_chromadb):
        """Test clearing a collection"""
        mock_chromadb.return_value = self.mock_client
        self.mock_client.get_collection.return_value = self.mock_collection
        
        async def run_test():
            vectordb = VectorDB(self.config)
            
            await vectordb.clear()
            
            # Should delete collection
            self.mock_client.delete_collection.assert_called_once_with(name="test_collection")
        
        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()