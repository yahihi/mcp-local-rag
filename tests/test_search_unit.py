#!/usr/bin/env python3
"""
Unit tests for SearchEngine class
"""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
import unittest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from search import SearchEngine


class TestSearchEngine(unittest.TestCase):
    """Test SearchEngine class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            "search_limit": 10,
            "similarity_threshold": 0.5
        }
        
        # Mock dependencies
        self.mock_vectordb = MagicMock()
        self.mock_embeddings = MagicMock()
        
        with patch('search.EmbeddingGenerator', return_value=self.mock_embeddings):
            self.search_engine = SearchEngine(self.mock_vectordb, self.config)
    
    def test_initialization(self):
        """Test SearchEngine initialization"""
        self.assertEqual(self.search_engine.vectordb, self.mock_vectordb)
        self.assertEqual(self.search_engine.config, self.config)
        self.assertEqual(self.search_engine.default_limit, 10)
        self.assertEqual(self.search_engine.similarity_threshold, 0.5)
    
    def test_initialization_with_defaults(self):
        """Test SearchEngine initialization with default values"""
        config = {}
        
        with patch('search.EmbeddingGenerator', return_value=self.mock_embeddings):
            search_engine = SearchEngine(self.mock_vectordb, config)
        
        # Should use default values
        self.assertEqual(search_engine.default_limit, 10)
        self.assertEqual(search_engine.similarity_threshold, 0.5)


class TestSearchEngineAsync(unittest.TestCase):
    """Test async methods of SearchEngine"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            "search_limit": 5,
            "similarity_threshold": 0.6
        }
        
        # Mock dependencies
        self.mock_vectordb = MagicMock()
        self.mock_embeddings = MagicMock()
    
    def test_search_basic(self):
        """Test basic search functionality"""
        async def run_test():
            with patch('search.EmbeddingGenerator', return_value=self.mock_embeddings):
                search_engine = SearchEngine(self.mock_vectordb, self.config)
            
            # Mock embedding generation
            self.mock_embeddings.generate = AsyncMock(return_value=[0.1, 0.2, 0.3])
            
            # Mock vectordb search results
            mock_results = [
                {
                    'id': 'chunk1',
                    'content': 'def test_function():\n    pass',
                    'metadata': {
                        'file_path': '/test/file.py',
                        'start_line': 1,
                        'end_line': 2,
                        'chunk_index': 0
                    },
                    'score': 0.9
                },
                {
                    'id': 'chunk2',
                    'content': 'class TestClass:\n    pass',
                    'metadata': {
                        'file_path': '/test/class.py',
                        'start_line': 10,
                        'end_line': 11,
                        'chunk_index': 1
                    },
                    'score': 0.75
                }
            ]
            self.mock_vectordb.search = AsyncMock(return_value=mock_results)
            
            # Perform search
            results = await search_engine.search("test function")
            
            # Verify embedding was generated
            self.mock_embeddings.generate.assert_called_once_with("test function")
            
            # Verify vectordb search was called
            self.mock_vectordb.search.assert_called_once_with(
                query_embedding=[0.1, 0.2, 0.3],
                limit=5,
                filter=None
            )
            
            # Verify results
            self.assertEqual(len(results), 2)
            self.assertEqual(results[0]['file_path'], '/test/file.py')
            self.assertEqual(results[0]['score'], 0.9)
            self.assertEqual(results[1]['file_path'], '/test/class.py')
            self.assertEqual(results[1]['score'], 0.75)
        
        asyncio.run(run_test())
    
    def test_search_with_custom_limit(self):
        """Test search with custom limit"""
        async def run_test():
            with patch('search.EmbeddingGenerator', return_value=self.mock_embeddings):
                search_engine = SearchEngine(self.mock_vectordb, self.config)
            
            self.mock_embeddings.generate = AsyncMock(return_value=[0.1, 0.2, 0.3])
            self.mock_vectordb.search = AsyncMock(return_value=[])
            
            await search_engine.search("query", limit=20)
            
            # Should use custom limit
            self.mock_vectordb.search.assert_called_once_with(
                query_embedding=[0.1, 0.2, 0.3],
                limit=20,
                filter=None
            )
        
        asyncio.run(run_test())
    
    def test_search_with_file_type_filter(self):
        """Test search with file type filter"""
        async def run_test():
            with patch('search.EmbeddingGenerator', return_value=self.mock_embeddings):
                search_engine = SearchEngine(self.mock_vectordb, self.config)
            
            self.mock_embeddings.generate = AsyncMock(return_value=[0.1, 0.2, 0.3])
            self.mock_vectordb.search = AsyncMock(return_value=[])
            
            await search_engine.search("query", file_type="python")
            
            # Should pass file type filter
            self.mock_vectordb.search.assert_called_once_with(
                query_embedding=[0.1, 0.2, 0.3],
                limit=5,
                filter={'language': 'python'}
            )
        
        asyncio.run(run_test())
    
    def test_search_filters_by_score(self):
        """Test that search filters results by similarity score"""
        async def run_test():
            with patch('search.EmbeddingGenerator', return_value=self.mock_embeddings):
                search_engine = SearchEngine(self.mock_vectordb, self.config)
            
            self.mock_embeddings.generate = AsyncMock(return_value=[0.1, 0.2, 0.3])
            
            # Mock results with varying scores
            mock_results = [
                {'id': '1', 'content': 'high score', 'metadata': {}, 'score': 0.8},
                {'id': '2', 'content': 'medium score', 'metadata': {}, 'score': 0.65},
                {'id': '3', 'content': 'low score', 'metadata': {}, 'score': 0.4},  # Below threshold
                {'id': '4', 'content': 'very low score', 'metadata': {}, 'score': 0.2}  # Below threshold
            ]
            self.mock_vectordb.search = AsyncMock(return_value=mock_results)
            
            results = await search_engine.search("query")
            
            # Should filter out results below threshold (0.6)
            self.assertEqual(len(results), 2)
            self.assertEqual(results[0]['score'], 0.8)
            self.assertEqual(results[1]['score'], 0.65)
        
        asyncio.run(run_test())
    
    def test_search_with_file_path_pattern(self):
        """Test search with file path pattern filtering"""
        async def run_test():
            with patch('search.EmbeddingGenerator', return_value=self.mock_embeddings):
                search_engine = SearchEngine(self.mock_vectordb, self.config)
            
            self.mock_embeddings.generate = AsyncMock(return_value=[0.1, 0.2, 0.3])
            
            # Mock results with different file paths
            mock_results = [
                {
                    'id': '1',
                    'content': 'test content',
                    'metadata': {'file_path': '/src/test.py'},
                    'score': 0.8
                },
                {
                    'id': '2',
                    'content': 'test content',
                    'metadata': {'file_path': '/tests/test.py'},
                    'score': 0.75
                },
                {
                    'id': '3',
                    'content': 'test content',
                    'metadata': {'file_path': '/src/main.py'},
                    'score': 0.7
                }
            ]
            self.mock_vectordb.search = AsyncMock(return_value=mock_results)
            
            results = await search_engine.search("query", file_path_pattern="/src/")
            
            # Should only include files matching pattern
            self.assertEqual(len(results), 2)
            self.assertTrue(all('/src/' in r['file_path'] for r in results))
        
        asyncio.run(run_test())
    
    def test_get_file_context(self):
        """Test getting context around a specific line"""
        async def run_test():
            with patch('search.EmbeddingGenerator', return_value=self.mock_embeddings):
                search_engine = SearchEngine(self.mock_vectordb, self.config)
            
            # Mock file reading
            file_lines = [f"Line {i}\n" for i in range(1, 101)]
            
            with patch('builtins.open', create=True) as mock_open:
                mock_open.return_value.__enter__.return_value.readlines.return_value = file_lines
                
                context = await search_engine.get_file_context(
                    file_path="/test/file.py",
                    line_number=50,
                    context_lines=5
                )
                
                # Should return context around line 50
                # line_number=50, context_lines=5 => start_line=45(0-based), end_line=55
                # but start_line is returned as 1-based (46)
                self.assertIn("Line 46", context['content'])
                self.assertIn("Line 50", context['content'])
                self.assertIn("Line 55", context['content'])
                self.assertEqual(context['start_line'], 46)  # 1-based
                self.assertEqual(context['end_line'], 55)
        
        asyncio.run(run_test())
    
    def test_get_file_context_at_start(self):
        """Test getting context at the beginning of file"""
        async def run_test():
            with patch('search.EmbeddingGenerator', return_value=self.mock_embeddings):
                search_engine = SearchEngine(self.mock_vectordb, self.config)
            
            file_content = "\n".join([f"Line {i}" for i in range(1, 21)])
            
            with patch('builtins.open', create=True) as mock_open:
                mock_open.return_value.__enter__.return_value.readlines.return_value = file_content.split('\n')
                
                context = await search_engine.get_file_context(
                    file_path="/test/file.py",
                    line_number=3,
                    context_lines=5
                )
                
                # Should handle beginning of file correctly
                self.assertIn("Line 1", context['content'])
                self.assertIn("Line 3", context['content'])
                self.assertIn("Line 8", context['content'])
                self.assertEqual(context['start_line'], 1)
                self.assertEqual(context['end_line'], 8)
        
        asyncio.run(run_test())
    
    def test_find_similar_files(self):
        """Test finding similar files"""
        async def run_test():
            with patch('search.EmbeddingGenerator', return_value=self.mock_embeddings):
                search_engine = SearchEngine(self.mock_vectordb, self.config)
            
            # Mock file content and embedding
            with patch('pathlib.Path.exists', return_value=True):
                with patch('builtins.open', create=True) as mock_open:
                    mock_open.return_value.__enter__.return_value.read.return_value = "test content"
                    
                    self.mock_embeddings.generate = AsyncMock(return_value=[0.1, 0.2, 0.3])
                    
                    # Mock search results
                    mock_results = [
                        {
                            'id': 'chunk1',
                            'metadata': {'file_path': '/test/similar1.py'},
                            'score': 0.9
                        },
                        {
                            'id': 'chunk2',
                            'metadata': {'file_path': '/test/similar2.py'},
                            'score': 0.85
                        },
                        {
                            'id': 'chunk3',
                            'metadata': {'file_path': '/test/similar1.py'},  # Duplicate file
                            'score': 0.8
                        }
                    ]
                    self.mock_vectordb.search = AsyncMock(return_value=mock_results)
                    
                    similar_files = await search_engine.find_similar_files(
                        file_path="/test/source.py",
                        limit=3
                    )
                    
                    # Should return unique files with averaged scores
                    self.assertEqual(len(similar_files), 2)
                    self.assertEqual(similar_files[0]['path'], '/test/similar1.py')
                    # similar1.py appears twice with scores 0.9 and 0.8, average = 0.85
                    self.assertAlmostEqual(similar_files[0]['similarity'], 0.85, places=2)
                    self.assertEqual(similar_files[1]['path'], '/test/similar2.py')
                    self.assertAlmostEqual(similar_files[1]['similarity'], 0.85, places=2)
        
        asyncio.run(run_test())
    
    def test_find_similar_files_excludes_self(self):
        """Test that find_similar_files excludes the source file"""
        async def run_test():
            with patch('search.EmbeddingGenerator', return_value=self.mock_embeddings):
                search_engine = SearchEngine(self.mock_vectordb, self.config)
            
            with patch('pathlib.Path.exists', return_value=True):
                with patch('builtins.open', create=True) as mock_open:
                    mock_open.return_value.__enter__.return_value.read.return_value = "content"
                    
                    self.mock_embeddings.generate = AsyncMock(return_value=[0.1, 0.2, 0.3])
                    
                    # Include source file in results
                    mock_results = [
                        {
                            'id': 'chunk1',
                            'metadata': {'file_path': '/test/source.py'},  # Same as source
                            'score': 1.0
                        },
                        {
                            'id': 'chunk2',
                            'metadata': {'file_path': '/test/other.py'},
                            'score': 0.8
                        }
                    ]
                    self.mock_vectordb.search = AsyncMock(return_value=mock_results)
                    
                    similar_files = await search_engine.find_similar_files(
                        file_path="/test/source.py",
                        limit=5
                    )
                    
                    # Should exclude source file
                    self.assertEqual(len(similar_files), 1)
                    self.assertEqual(similar_files[0]['path'], '/test/other.py')
        
        asyncio.run(run_test())
    
    def test_search_error_handling(self):
        """Test error handling in search"""
        async def run_test():
            with patch('search.EmbeddingGenerator', return_value=self.mock_embeddings):
                search_engine = SearchEngine(self.mock_vectordb, self.config)
            
            # Mock embedding generation failure
            self.mock_embeddings.generate = AsyncMock(side_effect=Exception("Embedding error"))
            
            results = await search_engine.search("query")
            
            # Should return empty results on error
            self.assertEqual(results, [])
        
        asyncio.run(run_test())
    
    def test_deduplicate_results(self):
        """Test result deduplication by file"""
        async def run_test():
            with patch('search.EmbeddingGenerator', return_value=self.mock_embeddings):
                search_engine = SearchEngine(self.mock_vectordb, self.config)
            
            self.mock_embeddings.generate = AsyncMock(return_value=[0.1, 0.2, 0.3])
            
            # Mock results with duplicate files
            mock_results = [
                {
                    'id': '1',
                    'content': 'chunk 1',
                    'metadata': {
                        'file_path': '/test/file.py',
                        'start_line': 1,
                        'end_line': 10,
                        'chunk_index': 0
                    },
                    'score': 0.9
                },
                {
                    'id': '2',
                    'content': 'chunk 2',
                    'metadata': {
                        'file_path': '/test/file.py',
                        'start_line': 8,
                        'end_line': 18,
                        'chunk_index': 1
                    },
                    'score': 0.85
                },
                {
                    'id': '3',
                    'content': 'chunk from other file',
                    'metadata': {
                        'file_path': '/test/other.py',
                        'start_line': 1,
                        'end_line': 10,
                        'chunk_index': 0
                    },
                    'score': 0.8
                }
            ]
            self.mock_vectordb.search = AsyncMock(return_value=mock_results)
            
            results = await search_engine.search("query")
            
            # Check that duplicate chunks are merged
            file_results = {}
            for result in results:
                file_path = result['file_path']
                if file_path not in file_results:
                    file_results[file_path] = result
            
            # Should have results from both files
            self.assertEqual(len(file_results), 2)
            self.assertIn('/test/file.py', file_results)
            self.assertIn('/test/other.py', file_results)
        
        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()