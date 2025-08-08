#!/usr/bin/env python3
"""
Direct search script for MCP Local RAG
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from search import SearchEngine
from vectordb import VectorDB
from utils import load_config

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Reduce noise
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main function to search codebase"""
    
    if len(sys.argv) < 2:
        print("Usage: python search_codebase.py '<search query>' [limit]")
        print("Examples:")
        print("  python search_codebase.py 'embedding function'")
        print("  python search_codebase.py 'file indexing' 5")
        sys.exit(1)
    
    query = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    
    try:
        # Load config
        config = load_config()
        
        # Initialize components
        vectordb = VectorDB(config)
        search_engine = SearchEngine(vectordb, config)
        
        print(f"Searching for: '{query}' (limit: {limit})")
        print("=" * 50)
        
        # Search the codebase
        results = await search_engine.search(
            query=query,
            limit=limit
        )
        
        if not results:
            print("No results found. Make sure the codebase is indexed first.")
            return
        
        # Display results
        for i, result in enumerate(results, 1):
            print(f"\n{i}. {result['file_path']} (score: {result['score']:.3f})")
            print(f"   Lines {result['start_line']}-{result['end_line']}")
            print(f"   Preview: {result['preview'][:300]}...")
            print("-" * 40)
        
    except Exception as e:
        logger.error(f"Error during search: {e}", exc_info=True)
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())