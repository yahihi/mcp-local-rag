#!/usr/bin/env python3
"""
Initial index setup script for MCP Local RAG
Run this before using the MCP server to create the initial index

Usage:
    python setup_index.py [directories...]
    
Examples:
    python setup_index.py                           # Use config.json
    python setup_index.py /path/to/project         # Index specific directory
    python setup_index.py /path1 /path2 /path3     # Index multiple directories
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from indexer import FileIndexer
from utils import load_config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Create initial index for specified or configured directories"""
    
    # Load configuration
    config = load_config()
    
    # Get directories from command line args or config
    if len(sys.argv) > 1:
        # Use command line arguments
        watch_dirs = sys.argv[1:]
        print(f"📁 Using directories from command line arguments")
    else:
        # Fall back to config.json
        watch_dirs = config.get('auto_index', {}).get('watch_directories', [])
        print(f"📁 Using directories from config.json")
    
    if not watch_dirs:
        print("❌ No directories configured in config.json")
        print("Please edit config.json and add directories to auto_index.watch_directories")
        return 1
    
    print(f"📁 Found {len(watch_dirs)} directories to index:")
    for dir in watch_dirs:
        print(f"  - {dir}")
    
    # Initialize indexer
    indexer = FileIndexer(config)
    
    # Index each directory
    total_stats = {
        "files_processed": 0,
        "chunks_created": 0,
        "errors": 0
    }
    
    for directory in watch_dirs:
        if not Path(directory).exists():
            print(f"⚠️  Skipping {directory} - directory not found")
            continue
            
        print(f"\n🔍 Indexing {directory}...")
        try:
            stats = await indexer.index_directory(directory)
            print(f"  ✅ Processed {stats['files_processed']} files, created {stats['chunks_created']} chunks")
            
            total_stats["files_processed"] += stats["files_processed"]
            total_stats["chunks_created"] += stats["chunks_created"]
            total_stats["errors"] += stats.get("errors", 0)
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            total_stats["errors"] += 1
    
    # Summary
    print("\n" + "="*50)
    print("📊 Indexing Complete!")
    print(f"  Files processed: {total_stats['files_processed']}")
    print(f"  Chunks created: {total_stats['chunks_created']}")
    if total_stats["errors"] > 0:
        print(f"  Errors: {total_stats['errors']}")
    
    print("\n✨ Your MCP server is ready to use!")
    print("Run: claude mcp add local-rag $(pwd)/run.sh")
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)