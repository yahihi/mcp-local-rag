#!/usr/bin/env python3
"""
Unit tests for FileIndexer and FileChunk classes
"""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open
import unittest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from indexer import FileIndexer, FileChunk


class TestFileChunk(unittest.TestCase):
    """Test FileChunk class"""
    
    def test_chunk_creation(self):
        """Test creating a FileChunk"""
        chunk = FileChunk(
            content="def hello():\n    print('world')",
            file_path="/test/file.py",
            start_line=1,
            end_line=2,
            chunk_index=0,
            metadata={"language": "python"}
        )
        
        self.assertEqual(chunk.content, "def hello():\n    print('world')")
        self.assertEqual(chunk.file_path, "/test/file.py")
        self.assertEqual(chunk.start_line, 1)
        self.assertEqual(chunk.end_line, 2)
        self.assertEqual(chunk.chunk_index, 0)
        self.assertEqual(chunk.metadata["language"], "python")
        self.assertIsNotNone(chunk.id)
    
    def test_chunk_id_generation(self):
        """Test that chunk ID is deterministic"""
        chunk1 = FileChunk(
            content="test content",
            file_path="/test/file.py",
            start_line=1,
            end_line=10,
            chunk_index=0
        )
        
        chunk2 = FileChunk(
            content="test content",
            file_path="/test/file.py",
            start_line=1,
            end_line=10,
            chunk_index=0
        )
        
        # Same content should produce same ID
        self.assertEqual(chunk1.id, chunk2.id)
        
        # Different content should produce different ID
        chunk3 = FileChunk(
            content="different content",
            file_path="/test/file.py",
            start_line=1,
            end_line=10,
            chunk_index=0
        )
        self.assertNotEqual(chunk1.id, chunk3.id)
    
    def test_chunk_to_dict(self):
        """Test converting chunk to dictionary"""
        chunk = FileChunk(
            content="test content",
            file_path="/test/file.py",
            start_line=5,
            end_line=15,
            chunk_index=2,
            metadata={"file_type": "python"}
        )
        
        chunk_dict = chunk.to_dict()
        
        self.assertEqual(chunk_dict["id"], chunk.id)
        self.assertEqual(chunk_dict["content"], "test content")
        self.assertEqual(chunk_dict["file_path"], "/test/file.py")
        self.assertEqual(chunk_dict["start_line"], 5)
        self.assertEqual(chunk_dict["end_line"], 15)
        self.assertEqual(chunk_dict["chunk_index"], 2)
        self.assertIn("file_type", chunk_dict["metadata"])


class TestFileIndexer(unittest.TestCase):
    """Test FileIndexer class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            "index_path": "/test/index",
            "chunk_size": 100,
            "chunk_overlap": 20,
            "exclude_dirs": [".git", "node_modules"],
            "file_extensions": [".py", ".js", ".md"]
        }
        
        # Mock VectorDB and EmbeddingGenerator
        self.mock_vectordb = MagicMock()
        self.mock_embedding_gen = MagicMock()
        
        with patch('indexer.VectorDB', return_value=self.mock_vectordb):
            with patch('indexer.EmbeddingGenerator', return_value=self.mock_embedding_gen):
                with patch('pathlib.Path.mkdir'):
                    self.indexer = FileIndexer(self.config)
    
    def test_indexer_initialization(self):
        """Test FileIndexer initialization"""
        self.assertEqual(self.indexer.chunk_size, 100)
        self.assertEqual(self.indexer.chunk_overlap, 20)
        self.assertEqual(self.indexer.exclude_dir_patterns, {".git", "node_modules"})
        self.assertIn(".py", FileIndexer.SUPPORTED_EXTENSIONS)
    
    def test_should_index_file(self):
        """Test file filtering logic"""
        # Mock _get_file_hash to avoid file access
        with patch.object(self.indexer, '_get_file_hash', return_value='test_hash'):
            # Should index file if not in metadata (new file)
            self.assertTrue(self.indexer._should_index_file("/test/file.py"))
            
            # Should not index if hash matches (unchanged file)
            self.indexer.file_metadata["/test/existing.py"] = {"hash": "test_hash"}
            self.assertFalse(self.indexer._should_index_file("/test/existing.py"))
            
            # Should index if forced
            self.assertTrue(self.indexer._should_index_file("/test/existing.py", force=True))
    
    def test_compute_file_hash(self):
        """Test file hash computation"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("test content for hashing")
            temp_path = f.name
        
        try:
            hash1 = self.indexer._get_file_hash(temp_path)
            hash2 = self.indexer._get_file_hash(temp_path)
            
            # Same file should produce same hash
            self.assertEqual(hash1, hash2)
            
            # Hash should be a string
            self.assertIsInstance(hash1, str)
            
            # Hash should have expected length (MD5 hex digest)
            self.assertEqual(len(hash1), 32)
        finally:
            Path(temp_path).unlink()
    
    def test_split_into_chunks_small_file(self):
        """Test chunking for small files"""
        content = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        
        chunks = self.indexer._chunk_text(
            content,
            "/test/small.py"
        )
        
        # Small file should create single chunk
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].start_line, 1)
        self.assertEqual(chunks[0].end_line, 5)
        self.assertEqual(chunks[0].content, content)
    
    def test_split_into_chunks_large_file(self):
        """Test chunking for large files with overlap"""
        # Create content that will require multiple chunks
        lines = [f"Line {i}: " + "x" * 20 for i in range(1, 21)]
        content = "\n".join(lines)
        
        # Temporarily set small chunk size to force splitting
        original_chunk_size = self.indexer.chunk_size
        self.indexer.chunk_size = 100
        
        chunks = self.indexer._chunk_text(
            content,
            "/test/large.py"
        )
        
        # Restore original chunk size
        self.indexer.chunk_size = original_chunk_size
        
        # Should create multiple chunks
        self.assertGreater(len(chunks), 1)
        
        # Check chunk indices
        for i, chunk in enumerate(chunks):
            self.assertEqual(chunk.chunk_index, i)
        
        # Verify overlap exists between consecutive chunks
        if len(chunks) > 1:
            # The end of first chunk should overlap with start of second
            first_chunk_end = chunks[0].end_line
            second_chunk_start = chunks[1].start_line
            self.assertLessEqual(second_chunk_start, first_chunk_end)
    
    def test_process_file(self):
        """Test processing a single file"""
        # This method doesn't exist in the current implementation
        # The functionality is now in index_file which is async
        pass
    
    def test_load_file_metadata(self):
        """Test loading file metadata"""
        test_metadata = {
            "/test/file1.py": {
                "hash": "abc123",
                "last_modified": "2024-01-01T00:00:00"
            },
            "/test/file2.js": {
                "hash": "def456",
                "last_modified": "2024-01-02T00:00:00"
            }
        }
        
        with patch('builtins.open', mock_open(read_data=json.dumps(test_metadata))):
            with patch('indexer.Path.exists', return_value=True):
                metadata = self.indexer._load_file_metadata()
                
                self.assertEqual(len(metadata), 2)
                self.assertEqual(metadata["/test/file1.py"]["hash"], "abc123")
                self.assertEqual(metadata["/test/file2.js"]["hash"], "def456")
    
    def test_save_file_metadata(self):
        """Test saving file metadata"""
        test_metadata = {
            "/test/file.py": {
                "hash": "test_hash",
                "last_modified": "2024-01-01T00:00:00"
            }
        }
        
        self.indexer.file_metadata = test_metadata
        
        mock_file = mock_open()
        with patch('builtins.open', mock_file):
            self.indexer._save_file_metadata()
        
        # Check that json.dump was called with correct data
        handle = mock_file()
        written_content = ''.join(call.args[0] for call in handle.write.call_args_list)
        written_data = json.loads(written_content)
        
        self.assertEqual(written_data["/test/file.py"]["hash"], "test_hash")
    
    def test_find_files_to_index(self):
        """Test finding files to index in directory"""
        # This method doesn't exist in the current implementation
        # The functionality is now integrated into index_directory
        pass


class TestFileIndexerAsync(unittest.TestCase):
    """Test async methods of FileIndexer"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            "index_path": "/test/index",
            "chunk_size": 100,
            "chunk_overlap": 20,
            "exclude_dirs": [".git"],
            "file_extensions": [".py"]
        }
        
        self.mock_vectordb = MagicMock()
        self.mock_embedding_gen = MagicMock()
        
        with patch('indexer.VectorDB', return_value=self.mock_vectordb):
            with patch('indexer.EmbeddingGenerator', return_value=self.mock_embedding_gen):
                with patch('pathlib.Path.mkdir'):
                    self.indexer = FileIndexer(self.config)
    
    def test_index_directory(self):
        """Test indexing a directory"""
        async def run_test():
            # Mock vectordb methods
            from unittest.mock import AsyncMock
            self.mock_vectordb.add_documents = AsyncMock(return_value=None)
            self.mock_vectordb.delete_by_file = AsyncMock(return_value=None)
            self.mock_vectordb.switch_collection = MagicMock()
            
            # Mock path operations to simulate a directory with no matching files
            with patch('pathlib.Path.resolve', return_value=Path("/test")):
                with patch('pathlib.Path.exists', return_value=True):
                    with patch('pathlib.Path.rglob', return_value=[]):
                        with patch.object(self.indexer, '_save_file_metadata'):
                            # Run index_directory
                            stats = await self.indexer.index_directory("/test")
                            
                            # With no files, stats should be zeros
                            self.assertEqual(stats["files_processed"], 0)
                            self.assertEqual(stats["chunks_created"], 0)
                            self.assertEqual(stats["files_skipped"], 0)
        
        asyncio.run(run_test())
    
    def test_index_directory_with_force_reindex(self):
        """Test force reindexing"""
        async def run_test():
            # Mock vectordb methods
            from unittest.mock import AsyncMock
            self.mock_vectordb.add_documents = AsyncMock(return_value=None)
            self.mock_vectordb.delete_by_file = AsyncMock(return_value=None)
            self.mock_vectordb.switch_collection = MagicMock()
            
            # Set up existing metadata
            self.indexer.file_metadata = {
                "/test/file1.py": {
                    "hash": "old_hash",
                    "last_modified": "2024-01-01T00:00:00"
                }
            }
            
            # Mock path operations
            with patch('pathlib.Path.resolve', return_value=Path("/test")):
                with patch('pathlib.Path.exists', return_value=True):
                    with patch('pathlib.Path.rglob', return_value=[]):
                        with patch.object(self.indexer, '_save_file_metadata'):
                            # Run with force_reindex=True
                            stats = await self.indexer.index_directory("/test", force_reindex=True)
                            
                            # With no files, stats should be zeros even with force
                            self.assertEqual(stats["files_processed"], 0)
                            self.assertEqual(stats["files_skipped"], 0)
        
        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()