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
import os
from pathlib import Path
import argparse

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from indexer import FileIndexer
from utils import load_config
import logging

level_name = os.getenv("LOGLEVEL", "INFO").upper()
level = getattr(logging, level_name, logging.INFO)
logging.basicConfig(level=level)
logger = logging.getLogger(__name__)


async def main():
    """Create initial index for specified or configured directories"""
    
    parser = argparse.ArgumentParser(description="Initial index setup for MCP Local RAG")
    parser.add_argument("directories", nargs="*", help="Directories to index (optional; otherwise from config)")
    parser.add_argument("--config", "-c", dest="config_path", help="Path to config JSON (overrides global)")
    args = parser.parse_args()

    # Load configuration (with optional path)
    config = load_config(args.config_path)
    
    # Get directories from command line args or config
    if args.directories:
        watch_dirs = args.directories
        print(f"📁 Using directories from command line arguments")
    else:
        # Fall back to config.json (prefer top-level 'watch_directories')
        watch_dirs = (
            config.get('watch_directories')
            or config.get('auto_index', {}).get('watch_directories', [])
        )
        if config.get('watch_directories'):
            print(f"📁 Using directories from config.json (watch_directories)")
        else:
            print(f"📁 Using directories from config.json (auto_index.watch_directories)")
    
    if not watch_dirs:
        print("❌ No directories configured in config.json")
        print("Please add directories to 'watch_directories' or 'auto_index.watch_directories'")
        return 1
    
    print(f"📁 Found {len(watch_dirs)} directories to index:")
    for dir in watch_dirs:
        print(f"  - {dir}")
    
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
            # Per-project config override if present
            project_cfg_path = Path(directory) / '.mcp-local-rag.json'
            if project_cfg_path.exists():
                try:
                    import json
                    with open(project_cfg_path) as f:
                        override = json.load(f)
                    cfg = dict(config)
                    cfg.update(override)
                    idx = FileIndexer(cfg)
                    logger.info(f"Using project config: {project_cfg_path}")
                except Exception as e:
                    print(f"  ⚠️  Could not load project config {project_cfg_path}: {e}")
                    idx = FileIndexer(config)
            else:
                idx = FileIndexer(config)
            stats = await idx.index_directory(directory)
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
