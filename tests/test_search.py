#!/usr/bin/env python3
"""
Test search functionality after periodic indexing
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from search import SearchEngine
from vectordb import VectorDB
from utils import load_config

async def test_search():
    """Test searching for specific markers"""
    config = load_config()
    vectordb = VectorDB(config)
    search_engine = SearchEngine(vectordb, config)
    
    # Test for NEW_FILE_MARKER_19_35
    print("Searching for NEW_FILE_MARKER_19_35...")
    results1 = await search_engine.search("NEW_FILE_MARKER_19_35", limit=3)
    print(f"Found {len(results1)} results")
    for i, result in enumerate(results1):
        print(f"  {i+1}. {result.get('file_path', 'unknown')}: {result.get('preview', '')[:100]}...")
    
    print("\nSearching for FINAL_UPDATE_TEST_19_35...")
    results2 = await search_engine.search("FINAL_UPDATE_TEST_19_35", limit=3)
    print(f"Found {len(results2)} results")
    for i, result in enumerate(results2):
        print(f"  {i+1}. {result.get('file_path', 'unknown')}: {result.get('preview', '')[:100]}...")
    
    # Test simple terms that should exist
    print("\nSearching for 'test_new_file'...")
    results3 = await search_engine.search("test_new_file", limit=3)
    print(f"Found {len(results3)} results")
    for i, result in enumerate(results3):
        print(f"  {i+1}. {result.get('file_path', 'unknown')}: {result.get('preview', '')[:100]}...")
    
    # Show search details  
    print(f"\nFirst result details:")
    if results3:
        result = results3[0]
        print(f"Keys: {result.keys()}")
        print(f"Preview: {result.get('preview', 'NO_PREVIEW')[:200]}")
        print(f"Score: {result.get('score', 'NO_SCORE')}")
        print(f"Chunk ID: {result.get('chunk_id', 'NO_CHUNK_ID')}")

if __name__ == "__main__":
    asyncio.run(test_search())