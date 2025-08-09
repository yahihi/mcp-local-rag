#!/usr/bin/env python3
"""
Unit tests for discovery module
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open
import shutil
import subprocess

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from discovery import (
    resolve_project_config,
    effective_filters,
    discover_files,
    _is_excluded_parts
)


class TestResolveProjectConfig(unittest.TestCase):
    """Test resolve_project_config function"""
    
    def test_no_project_config(self):
        """Test when no project config exists"""
        base_config = {
            "chunk_size": 1000,
            "exclude_dirs": [".git", "node_modules"]
        }
        
        with patch('pathlib.Path.exists', return_value=False):
            result = resolve_project_config(base_config, Path("/test/project"))
            
        # Should return base config unchanged
        self.assertEqual(result, base_config)
        self.assertEqual(result["chunk_size"], 1000)
        self.assertEqual(result["exclude_dirs"], [".git", "node_modules"])
    
    def test_with_project_config(self):
        """Test when project config exists"""
        base_config = {
            "chunk_size": 1000,
            "exclude_dirs": [".git", "node_modules"],
            "search_limit": 10
        }
        
        project_config = {
            "chunk_size": 2000,  # Override
            "new_setting": "value"  # Add new
        }
        
        mock_file = mock_open(read_data=json.dumps(project_config))
        
        with patch('pathlib.Path.exists', return_value=True):
            with patch('builtins.open', mock_file):
                result = resolve_project_config(base_config, Path("/test/project"))
        
        # Should merge configs (project overrides base)
        self.assertEqual(result["chunk_size"], 2000)  # Overridden
        self.assertEqual(result["exclude_dirs"], [".git", "node_modules"])  # Kept from base
        self.assertEqual(result["search_limit"], 10)  # Kept from base
        self.assertEqual(result["new_setting"], "value")  # Added from project
    
    def test_invalid_project_config(self):
        """Test when project config is invalid JSON"""
        base_config = {"chunk_size": 1000}
        
        mock_file = mock_open(read_data="invalid json{")
        
        with patch('pathlib.Path.exists', return_value=True):
            with patch('builtins.open', mock_file):
                result = resolve_project_config(base_config, Path("/test/project"))
        
        # Should return base config on error
        self.assertEqual(result, base_config)


class TestEffectiveFilters(unittest.TestCase):
    """Test effective_filters function"""
    
    def test_with_valid_extensions(self):
        """Test with valid extensions in config"""
        config = {
            "file_extensions": [".py", ".js", ".md"],
            "exclude_dirs": ["node_modules", ".git"]
        }
        supported = {".py", ".js", ".ts", ".md", ".txt"}
        
        enabled, excludes = effective_filters(config, supported)
        
        # Should only include supported extensions
        self.assertEqual(enabled, {".py", ".js", ".md"})
        self.assertEqual(excludes, {"node_modules", ".git"})
    
    def test_with_unsupported_extensions(self):
        """Test with some unsupported extensions"""
        config = {
            "file_extensions": [".py", ".xyz", ".abc"],  # .xyz and .abc not supported
            "exclude_dirs": ["dist"]
        }
        supported = {".py", ".js", ".ts"}
        
        enabled, excludes = effective_filters(config, supported)
        
        # Should only include .py (the only supported one)
        self.assertEqual(enabled, {".py"})
        self.assertEqual(excludes, {"dist"})
    
    def test_no_extensions_in_config(self):
        """Test when no extensions specified in config"""
        config = {
            "exclude_dirs": ["build"]
        }
        supported = {".py", ".js", ".ts"}
        
        enabled, excludes = effective_filters(config, supported)
        
        # Should use all supported extensions
        self.assertEqual(enabled, {".py", ".js", ".ts"})
        self.assertEqual(excludes, {"build"})
    
    def test_empty_config(self):
        """Test with empty config"""
        config = {}
        supported = {".py", ".js"}
        
        enabled, excludes = effective_filters(config, supported)
        
        # Should use all supported extensions and no excludes
        self.assertEqual(enabled, {".py", ".js"})
        self.assertEqual(excludes, set())
    
    def test_case_insensitive_extensions(self):
        """Test that extensions are case-insensitive"""
        config = {
            "file_extensions": [".PY", ".JS", ".Md"],  # Mixed case
        }
        supported = {".py", ".js", ".md"}
        
        enabled, excludes = effective_filters(config, supported)
        
        # Should normalize to lowercase
        self.assertEqual(enabled, {".py", ".js", ".md"})


class TestIsExcludedParts(unittest.TestCase):
    """Test _is_excluded_parts helper function"""
    
    def test_excluded_directory(self):
        """Test path with excluded directory"""
        path = Path("/project/node_modules/package/file.js")
        exclude_patterns = ["node_modules", ".git"]
        
        result = _is_excluded_parts(path, exclude_patterns)
        self.assertTrue(result)
    
    def test_not_excluded_directory(self):
        """Test path without excluded directories"""
        path = Path("/project/src/components/file.js")
        exclude_patterns = ["node_modules", ".git"]
        
        result = _is_excluded_parts(path, exclude_patterns)
        self.assertFalse(result)
    
    def test_pattern_matching(self):
        """Test wildcard pattern matching"""
        path = Path("/project/.pytest_cache/file.py")
        exclude_patterns = [".*_cache", "node_modules"]
        
        result = _is_excluded_parts(path, exclude_patterns)
        self.assertTrue(result)
    
    def test_nested_excluded_directory(self):
        """Test deeply nested excluded directory"""
        path = Path("/project/src/vendor/node_modules/lib/file.js")
        exclude_patterns = ["node_modules"]
        
        result = _is_excluded_parts(path, exclude_patterns)
        self.assertTrue(result)


class TestDiscoverFiles(unittest.TestCase):
    """Test discover_files function"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_path = Path(self.temp_dir)
        
        # Create test file structure with old timestamps
        import time
        import os
        old_time = time.time() - 3600  # 1 hour ago
        
        (self.test_path / "src").mkdir()
        (self.test_path / "src" / "main.py").touch()
        os.utime(self.test_path / "src" / "main.py", (old_time, old_time))
        
        (self.test_path / "src" / "utils.js").touch()
        os.utime(self.test_path / "src" / "utils.js", (old_time, old_time))
        
        (self.test_path / "src" / "test.txt").touch()
        os.utime(self.test_path / "src" / "test.txt", (old_time, old_time))
        
        (self.test_path / "node_modules").mkdir()
        (self.test_path / "node_modules" / "package.js").touch()
        os.utime(self.test_path / "node_modules" / "package.js", (old_time, old_time))
        
        (self.test_path / ".git").mkdir()
        (self.test_path / ".git" / "config").touch()
        
        (self.test_path / "README.md").touch()
        os.utime(self.test_path / "README.md", (old_time, old_time))
    
    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_full_scan_with_filters(self):
        """Test full scan with extension and exclude filters"""
        files = discover_files(
            dir_path=self.test_path,
            enabled_extensions={".py", ".js"},
            exclude_dirs={"node_modules", ".git"},
            changed_within_seconds=None
        )
        
        # Convert to relative paths for easier assertion
        rel_files = sorted(str(f.relative_to(self.test_path)) for f in files)
        
        # Should find main.py and utils.js, but not package.js (in node_modules)
        self.assertEqual(len(rel_files), 2)
        self.assertIn("src/main.py", rel_files)
        self.assertIn("src/utils.js", rel_files)
        self.assertNotIn("node_modules/package.js", rel_files)
    
    def test_full_scan_all_extensions(self):
        """Test full scan with all extensions"""
        files = discover_files(
            dir_path=self.test_path,
            enabled_extensions={".py", ".js", ".txt", ".md"},
            exclude_dirs={"node_modules", ".git"},
            changed_within_seconds=None
        )
        
        rel_files = sorted(str(f.relative_to(self.test_path)) for f in files)
        
        # Should find all files except those in excluded dirs
        self.assertEqual(len(rel_files), 4)
        self.assertIn("src/main.py", rel_files)
        self.assertIn("src/utils.js", rel_files)
        self.assertIn("src/test.txt", rel_files)
        self.assertIn("README.md", rel_files)
    
    def test_changed_scan_with_mtime(self):
        """Test changed scan with Python mtime fallback"""
        import time
        # Create a new file (all existing files are old from setUp)
        new_file = self.test_path / "recent.py"
        new_file.touch()
        
        # Mock fd and find not available
        with patch('shutil.which', return_value=None):
            files = discover_files(
                dir_path=self.test_path,
                enabled_extensions={".py"},
                exclude_dirs={"node_modules"},
                changed_within_seconds=5  # Only files changed in last 5 seconds
            )
        
        rel_files = sorted(str(f.relative_to(self.test_path)) for f in files)
        
        # Should only find the recently created file
        self.assertEqual(len(rel_files), 1)
        self.assertIn("recent.py", rel_files)
        # Old files should not be included
        self.assertNotIn("src/main.py", rel_files)
    
    @patch('subprocess.run')
    @patch('shutil.which')
    def test_changed_scan_with_fd(self, mock_which, mock_run):
        """Test changed scan using fd command"""
        # Mock fd is available
        mock_which.side_effect = lambda cmd: '/usr/bin/fd' if cmd == 'fd' else None
        
        # Mock fd output
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = f"{self.test_path}/src/main.py\n{self.test_path}/src/utils.js"
        mock_run.return_value = mock_result
        
        files = discover_files(
            dir_path=self.test_path,
            enabled_extensions={".py", ".js"},
            exclude_dirs={"node_modules"},
            changed_within_seconds=3600
        )
        
        # Should return files from fd output
        self.assertEqual(len(files), 2)
        
        # Check fd was called with correct arguments
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        self.assertEqual(call_args[0], 'fd')
        self.assertIn('--changed-within', call_args)
        self.assertIn('3600s', call_args)
    
    @patch('subprocess.run')
    @patch('shutil.which')
    def test_changed_scan_with_find(self, mock_which, mock_run):
        """Test changed scan using find command with timestamp file"""
        # Mock only find is available
        mock_which.side_effect = lambda cmd: '/usr/bin/find' if cmd == 'find' else None
        
        # Create timestamp file
        timestamp_file = self.test_path / "timestamp"
        timestamp_file.touch()
        
        # Mock find output
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = f"{self.test_path}/src/main.py"
        mock_run.return_value = mock_result
        
        files = discover_files(
            dir_path=self.test_path,
            enabled_extensions={".py"},
            exclude_dirs={"node_modules"},
            changed_within_seconds=3600,
            since_timestamp_file=timestamp_file
        )
        
        # Should return files from find output
        self.assertEqual(len(files), 1)
        
        # Check find was called with -newer
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        self.assertEqual(call_args[0], 'find')
        self.assertIn('-newer', call_args)
        self.assertIn(str(timestamp_file), call_args)
    
    def test_empty_directory(self):
        """Test with empty directory"""
        empty_dir = self.test_path / "empty"
        empty_dir.mkdir()
        
        files = discover_files(
            dir_path=empty_dir,
            enabled_extensions={".py"},
            exclude_dirs=set(),
            changed_within_seconds=None
        )
        
        self.assertEqual(len(files), 0)
    
    def test_nonexistent_directory(self):
        """Test with non-existent directory"""
        files = discover_files(
            dir_path=Path("/nonexistent/directory"),
            enabled_extensions={".py"},
            exclude_dirs=set(),
            changed_within_seconds=None
        )
        
        # Should return empty list without error
        self.assertEqual(len(files), 0)


if __name__ == "__main__":
    unittest.main()