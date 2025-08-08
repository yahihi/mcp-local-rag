#!/usr/bin/env python3
"""
Test direct ChromaDB search vs SearchEngine
"""

import asyncio
from src.vectordb import VectorDB
from src.embeddings import EmbeddingGenerator
from src.search import SearchEngine
from src.utils import load_config

async def test_direct_search():
    """Test direct ChromaDB search"""
    config = load_config()
    vectordb = VectorDB(config)
    embeddings = EmbeddingGenerator(config)
    search_engine = SearchEngine(vectordb, config)
    
    # Test different queries
    queries = [
        "test_new_file.py",
        "python test function",
        "def test_new_file",
        "NEW_FILE_MARKER"
    ]
    
    for query in queries:
        print(f"\nTesting search for: '{query}'")
        print("=" * 50)
        
        # Test SearchEngine search method  
        print(f"SearchEngine.search results:")
        try:
            search_results = await search_engine.search(query, limit=5)
            
            print(f"   Returned {len(search_results)} results")
            for i, result in enumerate(search_results):
                file_path = result.get('file_path', 'unknown')
                score = result.get('score', 0)
                print(f"     {i+1}. {file_path} (score: {score:.4f})")
                
                # Show more details for non-metadata results
                if 'file_metadata.json' not in file_path:
                    preview = result.get('preview', 'NO_PREVIEW')[:200]
                    print(f"         Preview: {preview}...")
                    
        except Exception as e:
            print(f"   Error in SearchEngine.search: {e}")
        
        print() # spacing between queries

if __name__ == "__main__":
    asyncio.run(test_direct_search())