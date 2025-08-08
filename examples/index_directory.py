#!/usr/bin/env python3
"""
Direct indexing script for MCP Local RAG
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from indexer import FileIndexer
from vectordb import VectorDB
from utils import load_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main function to index directory"""
    
    if len(sys.argv) != 2:
        print("Usage: python index_directory.py <directory_path>")
        sys.exit(1)
    
    directory_path = sys.argv[1]
    
    # Check if directory exists
    if not Path(directory_path).exists():
        print(f"Error: Directory '{directory_path}' does not exist")
        sys.exit(1)
    
    try:
        # Load config
        config = load_config()
        
        # Initialize components
        vectordb = VectorDB(config)
        indexer = FileIndexer(config)
        
        print(f"Starting indexing of directory: {directory_path}")
        
        # Index the directory
        stats = await indexer.index_directory(
            directory_path,
            force_reindex=False  # Set to True to force reindexing
        )
        
        print("\n=== Indexing Complete ===")
        print(f"Files processed: {stats['files_processed']}")
        print(f"Files skipped: {stats['files_skipped']}")
        print(f"Chunks created: {stats['chunks_created']}")
        print(f"Index path: {config['index_path']}")
        
    except Exception as e:
        logger.error(f"Error during indexing: {e}", exc_info=True)
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())