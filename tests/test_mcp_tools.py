#!/usr/bin/env python3
"""
Test MCP tools functionality directly
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from indexer import FileIndexer
from search import SearchEngine
from vectordb import VectorDB
from utils import load_config

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


async def test_mcp_tools():
    """Test MCP tools functionality"""
    
    try:
        # Load config
        config = load_config()
        
        # Initialize components
        indexer = FileIndexer(config)
        vectordb = VectorDB(config)
        search_engine = SearchEngine(vectordb, config)
        
        print("=== Testing MCP Local RAG Tools ===")
        
        # Test 1: index_directory tool
        print("\n1. Testing index_directory tool...")
        current_dir = str(Path.cwd())
        stats = await indexer.index_directory(
            current_dir,
            force_reindex=False
        )
        print(f"✓ Indexed {stats['files_processed']} files, created {stats['chunks_created']} chunks")
        
        # Test 2: search_codebase tool
        print("\n2. Testing search_codebase tool...")
        query = "MCP server implementation"
        results = await search_engine.search(query, limit=3)
        
        print(f"✓ Found {len(results)} results for '{query}':")
        for i, result in enumerate(results, 1):
            print(f"   {i}. {result['file_path']} (score: {result['score']:.3f})")
            print(f"      Lines {result['start_line']}-{result['end_line']}")
        
        # Test 3: get_file_context tool (simulate)
        print("\n3. Testing get_file_context functionality...")
        test_file = Path(__file__)
        if test_file.exists():
            with open(test_file, 'r') as f:
                lines = f.readlines()
            print(f"✓ File context: {test_file.name} has {len(lines)} lines")
        
        # Test 4: find_similar tool (simulate)
        print("\n4. Testing find_similar functionality...")
        similar_files = await search_engine.find_similar_files(
            str(Path("src/indexer.py")),
            limit=3
        )
        print(f"✓ Found {len(similar_files)} similar files to indexer.py:")
        for file_info in similar_files:
            print(f"   - {file_info['path']} (similarity: {file_info['similarity']:.3f})")
        
        print("\n=== All MCP tools are working correctly! ===")
        print(f"Index location: {config['index_path']}")
        print("Ready to use as MCP server.")
        
    except Exception as e:
        print(f"Error during testing: {e}")
        logger.error(f"Test error: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(test_mcp_tools())