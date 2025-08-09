#!/usr/bin/env python3
"""
Unit tests for FileChangeHandler (file watcher) class
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock
import unittest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from indexer import FileChangeHandler, FileIndexer


class TestFileChangeHandler(unittest.TestCase):
    """Test FileChangeHandler class for file system monitoring"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock FileIndexer
        self.mock_indexer = MagicMock(spec=FileIndexer)
        self.mock_indexer.SUPPORTED_EXTENSIONS = {
            '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c',
            '.h', '.hpp', '.cs', '.go', '.rs', '.rb', '.php', '.swift',
            '.kt', '.scala', '.r', '.m', '.mm', '.sh', '.bash', '.zsh',
            '.fish', '.ps1', '.bat', '.cmd', '.yaml', '.yml', '.json',
            '.xml', '.html', '.css', '.scss', '.sass', '.less', '.sql',
            '.md', '.markdown', '.rst', '.txt', '.ini', '.cfg', '.conf',
            '.toml', '.env', '.gitignore', '.dockerignore', '.editorconfig'
        }
        # Add enabled_extensions attribute (new in updated implementation)
        self.mock_indexer.enabled_extensions = self.mock_indexer.SUPPORTED_EXTENSIONS
        # Mock _is_excluded method
        self.mock_indexer._is_excluded = MagicMock(return_value=False)
        
        # Create handler
        self.handler = FileChangeHandler(self.mock_indexer)
    
    def test_initialization(self):
        """Test FileChangeHandler initialization"""
        self.assertEqual(self.handler.indexer, self.mock_indexer)
    
    def test_on_modified_supported_file(self):
        """Test handling modification of supported file"""
        # Create mock event for Python file
        mock_event = Mock()
        mock_event.is_directory = False
        mock_event.src_path = "/test/project/main.py"
        
        with patch('indexer.logger') as mock_logger:
            self.handler.on_modified(mock_event)
            
            # Should log the modification
            mock_logger.info.assert_called_once()
            log_message = mock_logger.info.call_args[0][0]
            self.assertIn("File modified", log_message)
            self.assertIn("main.py", log_message)
    
    def test_on_modified_unsupported_file(self):
        """Test handling modification of unsupported file"""
        # Create mock event for unsupported file
        mock_event = Mock()
        mock_event.is_directory = False
        mock_event.src_path = "/test/project/image.png"
        
        with patch('indexer.logger') as mock_logger:
            self.handler.on_modified(mock_event)
            
            # Should not log anything for unsupported files
            mock_logger.info.assert_not_called()
    
    def test_on_modified_directory(self):
        """Test handling modification of directory"""
        # Create mock event for directory
        mock_event = Mock()
        mock_event.is_directory = True
        mock_event.src_path = "/test/project/src"
        
        with patch('indexer.logger') as mock_logger:
            self.handler.on_modified(mock_event)
            
            # Should not process directories
            mock_logger.info.assert_not_called()
    
    def test_on_created_supported_file(self):
        """Test handling creation of supported file"""
        # Create mock event for new JavaScript file
        mock_event = Mock()
        mock_event.is_directory = False
        mock_event.src_path = "/test/project/app.js"
        
        with patch('indexer.logger') as mock_logger:
            self.handler.on_created(mock_event)
            
            # Should log the creation
            mock_logger.info.assert_called_once()
            log_message = mock_logger.info.call_args[0][0]
            self.assertIn("File created", log_message)
            self.assertIn("app.js", log_message)
    
    def test_on_created_unsupported_file(self):
        """Test handling creation of unsupported file"""
        # Create mock event for unsupported file
        mock_event = Mock()
        mock_event.is_directory = False
        mock_event.src_path = "/test/project/data.dat"
        
        with patch('indexer.logger') as mock_logger:
            self.handler.on_created(mock_event)
            
            # Should not log anything for unsupported files
            mock_logger.info.assert_not_called()
    
    def test_on_created_directory(self):
        """Test handling creation of directory"""
        # Create mock event for directory
        mock_event = Mock()
        mock_event.is_directory = True
        mock_event.src_path = "/test/project/new_folder"
        
        with patch('indexer.logger') as mock_logger:
            self.handler.on_created(mock_event)
            
            # Should not process directories
            mock_logger.info.assert_not_called()
    
    def test_on_deleted_file(self):
        """Test handling deletion of file"""
        # Create mock event for deleted file
        mock_event = Mock()
        mock_event.is_directory = False
        mock_event.src_path = "/test/project/old.py"
        
        with patch('indexer.logger') as mock_logger:
            self.handler.on_deleted(mock_event)
            
            # Should log the deletion
            mock_logger.info.assert_called_once()
            log_message = mock_logger.info.call_args[0][0]
            self.assertIn("File deleted", log_message)
            self.assertIn("old.py", log_message)
    
    def test_on_deleted_directory(self):
        """Test handling deletion of directory"""
        # Create mock event for directory
        mock_event = Mock()
        mock_event.is_directory = True
        mock_event.src_path = "/test/project/removed_folder"
        
        with patch('indexer.logger') as mock_logger:
            self.handler.on_deleted(mock_event)
            
            # Should not process directories
            mock_logger.info.assert_not_called()
    
    def test_supported_extensions_check(self):
        """Test that handler correctly checks supported extensions"""
        test_files = [
            ("/test/file.py", True),
            ("/test/file.PY", True),  # Case insensitive
            ("/test/file.js", True),
            ("/test/file.tsx", True),
            ("/test/file.md", True),
            ("/test/file.json", True),
            ("/test/file.yaml", True),
            ("/test/file.xml", True),
            ("/test/file.sql", True),
            ("/test/file.sh", True),
            ("/test/file.png", False),
            ("/test/file.jpg", False),
            ("/test/file.mp4", False),
            ("/test/file.exe", False),
            ("/test/file.bin", False),
            ("/test/file", False),  # No extension
        ]
        
        for file_path, should_process in test_files:
            mock_event = Mock()
            mock_event.is_directory = False
            mock_event.src_path = file_path
            
            with patch('indexer.logger') as mock_logger:
                self.handler.on_modified(mock_event)
                
                if should_process:
                    mock_logger.info.assert_called_once()
                else:
                    mock_logger.info.assert_not_called()
    
    def test_multiple_events_handling(self):
        """Test handling multiple file events in sequence"""
        events = [
            (self.handler.on_created, "/test/new.py", "File created"),
            (self.handler.on_modified, "/test/new.py", "File modified"),
            (self.handler.on_deleted, "/test/old.js", "File deleted"),
            (self.handler.on_created, "/test/another.ts", "File created")
        ]
        
        with patch('indexer.logger') as mock_logger:
            for handler_method, file_path, expected_message in events:
                mock_event = Mock()
                mock_event.is_directory = False
                mock_event.src_path = file_path
                
                handler_method(mock_event)
                
                # Check that appropriate message was logged
                last_log = mock_logger.info.call_args[0][0]
                self.assertIn(expected_message, last_log)
                self.assertIn(Path(file_path).name, last_log)
            
            # Should have logged all 4 events
            self.assertEqual(mock_logger.info.call_count, 4)


class TestFileIndexerWatching(unittest.TestCase):
    """Test FileIndexer's directory watching functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            "index_path": "/test/index",
            "chunk_size": 100,
            "chunk_overlap": 20,
            "exclude_dirs": [".git"],
            "file_extensions": [".py", ".js"]
        }
        
        self.mock_vectordb = MagicMock()
        self.mock_embedding_gen = MagicMock()
    
    @patch('pathlib.Path.mkdir')
    @patch('indexer.Observer')
    @patch('indexer.VectorDB')
    @patch('indexer.EmbeddingGenerator')
    def test_watch_directory(self, mock_embedding_gen, mock_vectordb, mock_observer_class, mock_mkdir):
        """Test setting up directory watching"""
        mock_vectordb.return_value = self.mock_vectordb
        mock_embedding_gen.return_value = self.mock_embedding_gen
        
        mock_observer = MagicMock()
        mock_observer_class.return_value = mock_observer
        
        indexer = FileIndexer(self.config)
        
        # Watch a directory
        test_dir = "/test/project"
        indexer.start_watching(test_dir)
        
        # Should create observer
        mock_observer_class.assert_called_once()
        
        # Should schedule handler
        mock_observer.schedule.assert_called_once()
        call_args = mock_observer.schedule.call_args
        
        # Check handler type
        handler = call_args[0][0]
        self.assertIsInstance(handler, FileChangeHandler)
        self.assertEqual(handler.indexer, indexer)
        
        # Check watched path
        watched_path = call_args[0][1]
        self.assertEqual(watched_path, test_dir)
        
        # Check recursive flag
        recursive = call_args[1].get('recursive', False)
        self.assertTrue(recursive)
        
        # Should start observer
        mock_observer.start.assert_called_once()
    
    @patch('pathlib.Path.mkdir')
    @patch('indexer.Observer')
    @patch('indexer.VectorDB')
    @patch('indexer.EmbeddingGenerator')
    def test_stop_watching(self, mock_embedding_gen, mock_vectordb, mock_observer_class, mock_mkdir):
        """Test stopping directory watching"""
        mock_vectordb.return_value = self.mock_vectordb
        mock_embedding_gen.return_value = self.mock_embedding_gen
        
        mock_observer = MagicMock()
        mock_observer_class.return_value = mock_observer
        
        indexer = FileIndexer(self.config)
        
        # Start watching
        indexer.start_watching("/test/project")
        
        # Stop watching
        indexer.stop_watching()
        
        # Should stop and join observer
        mock_observer.stop.assert_called_once()
        mock_observer.join.assert_called_once()
    
    @patch('pathlib.Path.mkdir')
    @patch('indexer.Observer')
    @patch('indexer.VectorDB')
    @patch('indexer.EmbeddingGenerator')
    def test_no_stop_when_not_watching(self, mock_embedding_gen, mock_vectordb, mock_observer_class, mock_mkdir):
        """Test that stop_watching handles case when not watching"""
        mock_vectordb.return_value = self.mock_vectordb
        mock_embedding_gen.return_value = self.mock_embedding_gen
        
        indexer = FileIndexer(self.config)
        
        # Should not raise error when stopping without watching
        try:
            indexer.stop_watching()
        except Exception as e:
            self.fail(f"stop_watching raised {e} when not watching")


if __name__ == "__main__":
    unittest.main()