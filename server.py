#!/usr/bin/env python3
"""
MCP Server for Local RAG System - Simplified version
"""

import asyncio
import json
import logging
import os
import platform
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool

from indexer import FileIndexer
from search import SearchEngine
from vectordb import VectorDB
from utils import load_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Main entry point for MCP server"""
    
    # Initialize server
    server = Server("mcp-local-rag")
    
    # Load configuration
    config = load_config()
    
    # Initialize components
    indexer = FileIndexer(config)
    vectordb = VectorDB(config)
    search_engine = SearchEngine(vectordb, config)
    
    # Track project collections
    project_collections = {}
    
    # Get watched directories from config and environment variables
    watched_dirs = set(config.get('watch_directories', []))
    
    # Add directories from environment variables MCP_WATCH_DIR_1, MCP_WATCH_DIR_2, etc.
    for i in range(1, 20):
        watch_dir = os.getenv(f'MCP_WATCH_DIR_{i}')
        if watch_dir and Path(watch_dir).exists():
            watched_dirs.add(watch_dir)
    
    # Log watched directories
    if watched_dirs:
        logger.info(f"Watching {len(watched_dirs)} directories for changes")
        for dir in watched_dirs:
            logger.info(f"  - {dir}")
    else:
        logger.info("No watched directories configured. Use index_directory tool or set MCP_WATCH_DIR_* env vars.")
    
    # Check which file search command is available (prefer fd over find)
    file_search_cmd = None
    system_platform = platform.system()
    
    if system_platform == "Windows":
        logger.warning("Windows detected - periodic re-indexing not supported natively")
        logger.info("To enable auto-update functionality, consider:")
        logger.info("  1. Using WSL (Windows Subsystem for Linux)")
        logger.info("  2. Installing Git Bash which includes find")
        logger.info("  3. Installing fd (https://github.com/sharkdp/fd)")
        logger.info("  4. Using the manual index_directory tool")
    else:
        # Try fd first (respects .gitignore automatically)
        try:
            result = subprocess.run(['fd', '--version'], capture_output=True, text=True)
            file_search_cmd = 'fd'
            logger.info(f"Running on {system_platform} - using fd (respects .gitignore) for file change detection")
        except FileNotFoundError:
            # Fall back to find
            try:
                result = subprocess.run(['find', '--version'], capture_output=True, text=True)
                file_search_cmd = 'find'
                logger.info(f"Running on {system_platform} - using find for file change detection")
                logger.info("Tip: Install fd (https://github.com/sharkdp/fd) for better performance and .gitignore support")
            except FileNotFoundError:
                logger.warning(f"Neither fd nor find command available on {system_platform}")
                logger.warning("Periodic re-indexing will be disabled")
                logger.info("Install fd: brew install fd (macOS) or apt install fd-find (Linux)")
    
    # Start periodic re-indexing task with find-based change detection
    reindex_interval = config.get('reindex_interval_seconds', 300)
    reindex_running = False  # Flag to prevent concurrent re-indexing
    shutdown_event = asyncio.Event()  # Event for graceful shutdown
    
    # Create timestamp file for tracking last check
    timestamp_file = Path(tempfile.gettempdir()) / 'mcp_local_rag_last_check'
    if not timestamp_file.exists():
        timestamp_file.touch()
    
    async def periodic_reindex():
        """Periodically re-index changed files using fd/find command"""
        nonlocal reindex_running
        
        while not shutdown_event.is_set():
            logger.info(f"Sleeping for {reindex_interval} seconds...")
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=reindex_interval)
                break  # Shutdown requested
            except asyncio.TimeoutError:
                pass  # Continue with re-indexing
            
            # Skip if previous re-index is still running
            if reindex_running:
                logger.warning("Previous re-index still running, skipping this cycle")
                continue
            
            reindex_running = True
            logger.info(f"Starting periodic re-index using {file_search_cmd}... timestamp_file: {timestamp_file}")
            logger.info(f"Watched directories: {watched_dirs}")
            
            try:
                any_files_processed = False
                
                for directory in watched_dirs:
                    try:
                        # Find files modified since last check
                        if file_search_cmd == 'fd':
                            # fd respects .gitignore by default
                            search_cmd = ['fd', '--type', 'f', '--changed-within', 
                                        f"{int(time.time() - timestamp_file.stat().st_mtime)}s",
                                        '.', directory]
                        elif file_search_cmd == 'find':
                            search_cmd = ['find', directory, '-type', 'f', '-newer', str(timestamp_file)]
                        else:
                            logger.warning("No file search command available, skipping re-index")
                            return
                        
                        logger.info(f"Running {file_search_cmd} command: {' '.join(search_cmd)}")
                        result = subprocess.run(
                            search_cmd,
                            capture_output=True,
                            text=True,
                            check=False  # Don't raise exception on non-zero return
                        )
                        
                        # Check for command not found error
                        if result.returncode == 127 or 'not found' in result.stderr.lower():
                            logger.error(f"{file_search_cmd} command not available on this system")
                            logger.info("Periodic re-indexing will be disabled")
                            return  # Exit the periodic_reindex function
                        
                        logger.info(f"{file_search_cmd.capitalize()} command result - returncode: {result.returncode}, stdout: '{result.stdout}', stderr: '{result.stderr}'")
                        
                        if result.returncode == 0 and result.stdout:
                            changed_files = result.stdout.strip().split('\n')
                            changed_files = [f for f in changed_files if f]  # Remove empty strings
                            
                            # Filter by supported extensions
                            supported_files = []
                            for file_path in changed_files:
                                ext = Path(file_path).suffix.lower()
                                if ext in indexer.SUPPORTED_EXTENSIONS:
                                    # Skip files in excluded directories
                                    if not any(exc in file_path for exc in config.get('exclude_dirs', [])):
                                        supported_files.append(file_path)
                            
                            if supported_files:
                                logger.info(f"Found {len(supported_files)} changed files in {directory}")
                                any_files_processed = True
                                
                                # Get collection name for this directory
                                import re
                                dir_path = Path(directory).resolve()
                                collection_name = re.sub(r'[^a-zA-Z0-9_-]', '_', dir_path.name)
                                if not collection_name:
                                    collection_name = "default"
                                
                                # Index each changed file with the appropriate collection
                                for file_path in supported_files:
                                    try:
                                        chunks = await indexer.index_file(file_path, force_reindex=True, collection_name=collection_name)
                                        if chunks > 0:
                                            logger.info(f"Re-indexed {file_path}: {chunks} chunks in collection '{collection_name}'")
                                    except Exception as e:
                                        logger.error(f"Error indexing {file_path}: {e}")
                            else:
                                logger.debug(f"No changed files in {directory}")
                        
                    except Exception as e:
                        logger.error(f"Error checking directory {directory}: {e}")
                
                # Check for deleted files
                try:
                    metadata_path = Path(config.get('index_path', './data/index')) / 'file_metadata.json'
                    if metadata_path.exists():
                        with open(metadata_path) as f:
                            file_metadata = json.load(f)
                        
                        # Check each indexed file still exists
                        deleted_files = []
                        for file_path in list(file_metadata.keys()):
                            # Only check files in watched directories
                            if any(str(file_path).startswith(str(dir)) for dir in watched_dirs):
                                if not Path(file_path).exists():
                                    deleted_files.append(file_path)
                        
                        if deleted_files:
                            logger.info(f"Found {len(deleted_files)} deleted files to remove from index")
                            
                            # Group deleted files by their project directory
                            import re
                            files_by_collection = {}
                            for file_path in deleted_files:
                                # Find which watched directory this file belongs to
                                for watched_dir in watched_dirs:
                                    if str(file_path).startswith(str(watched_dir)):
                                        dir_path = Path(watched_dir).resolve()
                                        collection_name = re.sub(r'[^a-zA-Z0-9_-]', '_', dir_path.name)
                                        if not collection_name:
                                            collection_name = "default"
                                        if collection_name not in files_by_collection:
                                            files_by_collection[collection_name] = []
                                        files_by_collection[collection_name].append(file_path)
                                        break
                            
                            # Delete from appropriate collections
                            for collection_name, files in files_by_collection.items():
                                vectordb.switch_collection(collection_name)
                                for file_path in files:
                                    try:
                                        # Remove from vector database
                                        await vectordb.delete_by_file(file_path)
                                        # Remove from metadata
                                        del file_metadata[file_path]
                                        logger.info(f"Removed deleted file from collection '{collection_name}': {file_path}")
                                        any_files_processed = True
                                    except Exception as e:
                                        logger.error(f"Error removing deleted file {file_path}: {e}")
                            
                            # Save updated metadata
                            if any_files_processed:
                                with open(metadata_path, 'w') as f:
                                    json.dump(file_metadata, f, indent=2)
                                logger.info("Updated file_metadata.json after removing deleted files")
                
                except Exception as e:
                    logger.error(f"Error checking for deleted files: {e}")
                
                # Update timestamp only if files were actually processed
                if any_files_processed:
                    logger.info("Files were processed, updating timestamp")
                    timestamp_file.touch()
                else:
                    logger.info("No files were processed, keeping old timestamp")
                
            finally:
                reindex_running = False
                logger.info("Periodic re-index completed")
    
    # Create background task for periodic re-indexing
    if reindex_interval > 0 and file_search_cmd:
        asyncio.create_task(periodic_reindex())
        logger.info(f"Periodic re-indexing enabled (every {reindex_interval} seconds)")
    elif reindex_interval > 0 and not file_search_cmd:
        logger.warning("Periodic re-indexing requested but find command not available")
        logger.info("Use manual index_directory tool to update the index")
    else:
        logger.info("Periodic re-indexing disabled (set reindex_interval_seconds > 0 to enable)")
    
    @server.list_tools()
    async def list_tools() -> List[Tool]:
        """List available tools"""
        return [
            Tool(
                name="index_directory",
                description="Index a directory for semantic search",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the directory to index"
                        },
                        "extensions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "File extensions to index (e.g., ['.py', '.js'])"
                        },
                        "force_reindex": {
                            "type": "boolean",
                            "description": "Force reindexing even if files haven't changed",
                            "default": False
                        }
                    },
                    "required": ["path"]
                }
            ),
            Tool(
                name="search_codebase",
                description="Search the indexed codebase using semantic search",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results",
                            "default": 10
                        },
                        "file_type": {
                            "type": "string",
                            "description": "Filter by file type (e.g., 'python', 'javascript')"
                        },
                        "collection": {
                            "type": "string",
                            "description": "Collection name (project) to search. If not specified, uses current directory's project"
                        }
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="get_file_context",
                description="Get context around a specific file or line",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to the file"
                        },
                        "line_number": {
                            "type": "integer",
                            "description": "Line number to get context around"
                        },
                        "context_lines": {
                            "type": "integer",
                            "description": "Number of lines of context to include",
                            "default": 50
                        }
                    },
                    "required": ["file_path"]
                }
            ),
            Tool(
                name="find_similar",
                description="Find files similar to a given file",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to the reference file"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of similar files",
                            "default": 5
                        }
                    },
                    "required": ["file_path"]
                }
            ),
            Tool(
                name="watch_directory",
                description="Add a directory to watch for changes (temporary - resets on restart). To persist, edit config.json",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the directory to watch"
                        },
                        "auto_index": {
                            "type": "boolean",
                            "description": "Automatically index the directory on add",
                            "default": True
                        }
                    },
                    "required": ["path"]
                }
            ),
            Tool(
                name="get_index_status",
                description="Get current status of the indexer and watched directories",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            )
        ]
    
    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Handle tool calls"""
        
        try:
            if name == "index_directory":
                path = Path(arguments["path"]).resolve()
                if not path.exists():
                    return [{
                        "type": "text",
                        "text": f"Directory not found: {arguments['path']}"
                    }]
                
                # Index directory
                stats = await indexer.index_directory(
                    str(path),
                    extensions=arguments.get("extensions"),
                    force_reindex=arguments.get("force_reindex", False)
                )
                
                return [{
                    "type": "text",
                    "text": f"Indexed {stats['files_processed']} files, "
                            f"{stats['chunks_created']} chunks created. "
                            f"Skipped {stats['files_skipped']} unchanged files."
                }]
            
            elif name == "search_codebase":
                # Get collection name from file path if provided
                collection_name = arguments.get("collection")
                
                # If collection specified, switch to it
                if collection_name:
                    vectordb.switch_collection(collection_name)
                else:
                    # Try to detect from current working directory
                    import os
                    import re
                    cwd = Path(os.getcwd()).resolve()
                    # Check if cwd is in watched directories
                    for watched_dir in watched_dirs:
                        watched_path = Path(watched_dir).resolve()
                        if cwd == watched_path or watched_path in cwd.parents:
                            collection_name = re.sub(r'[^a-zA-Z0-9_-]', '_', watched_path.name)
                            if collection_name:
                                vectordb.switch_collection(collection_name)
                            break
                
                results = await search_engine.search(
                    query=arguments["query"],
                    limit=arguments.get("limit", 10),
                    file_type=arguments.get("file_type")
                )
                
                if not results:
                    return [{
                        "type": "text",
                        "text": "No results found. Make sure to index directories first."
                    }]
                
                # Format results
                formatted = []
                for i, result in enumerate(results, 1):
                    formatted.append(
                        f"{i}. {result['file_path']} (score: {result['score']:.3f})\n"
                        f"   Lines {result['start_line']}-{result['end_line']}\n"
                        f"   Preview: {result['preview'][:200]}..."
                    )
                
                return [{
                    "type": "text",
                    "text": "\n\n".join(formatted)
                }]
            
            elif name == "get_file_context":
                path = Path(arguments["file_path"]).resolve()
                if not path.exists():
                    return [{
                        "type": "text",
                        "text": f"File not found: {arguments['file_path']}"
                    }]
                
                with open(path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                line_num = arguments.get("line_number")
                context_lines = arguments.get("context_lines", 50)
                
                if line_num:
                    start = max(0, line_num - context_lines // 2)
                    end = min(len(lines), line_num + context_lines // 2)
                    
                    context = []
                    for i in range(start, end):
                        prefix = ">>> " if i == line_num - 1 else "    "
                        context.append(f"{i+1:4d}{prefix}{lines[i].rstrip()}")
                    
                    text = "\n".join(context)
                else:
                    text = f"File: {path.name}\n"
                    text += f"Total lines: {len(lines)}\n"
                    text += f"Size: {path.stat().st_size} bytes\n\n"
                    text += "First 20 lines:\n"
                    text += "".join(lines[:20])
                
                return [{
                    "type": "text",
                    "text": text
                }]
            
            elif name == "find_similar":
                path = Path(arguments["file_path"]).resolve()
                if not path.exists():
                    return [{
                        "type": "text",
                        "text": f"File not found: {arguments['file_path']}"
                    }]
                
                similar = await search_engine.find_similar_files(
                    str(path),
                    limit=arguments.get("limit", 5)
                )
                
                if not similar:
                    return [{
                        "type": "text",
                        "text": "No similar files found. Make sure the file is indexed."
                    }]
                
                formatted = [f"Files similar to {path.name}:\n"]
                for i, file_info in enumerate(similar, 1):
                    formatted.append(
                        f"{i}. {file_info['path']} "
                        f"(similarity: {file_info['similarity']:.3f})\n"
                        f"   {file_info['description']}"
                    )
                
                return [{
                    "type": "text",
                    "text": "\n".join(formatted)
                }]
            
            elif name == "watch_directory":
                path = Path(arguments["path"]).resolve()
                if not path.exists():
                    return [{
                        "type": "text",
                        "text": f"Directory not found: {arguments['path']}"
                    }]
                
                # Add directory to watched_dirs for this session
                if str(path) not in watched_dirs:
                    watched_dirs.add(str(path))
                    status_text = f"Directory {path} added to watch list (temporary - will reset on restart).\n"
                    status_text += "To persist, add to config.json's watch_directories or use MCP_WATCH_DIR_* env vars."
                else:
                    status_text = f"Directory {path} is already being watched."
                
                return [{
                    "type": "text",
                    "text": status_text
                }]
            
            elif name == "get_index_status":
                # Get index status
                status_text = "Index Status:\n"
                status_text += f"Periodic re-indexing: Every {reindex_interval} seconds\n"
                status_text += f"Watched directories: {len(watched_dirs)}\n"
                
                if watched_dirs:
                    status_text += "\nWatched directories:\n"
                    for dir in watched_dirs:
                        status_text += f"  - {dir}\n"
                
                # Get available collections
                try:
                    import re
                    collections = vectordb.client.list_collections()
                    if collections:
                        status_text += f"\nAvailable collections ({len(collections)}):\n"
                        for collection in collections:
                            # Try to match collection name to watched directory
                            matched_dir = None
                            for watched_dir in watched_dirs:
                                watched_path = Path(watched_dir).resolve()
                                collection_pattern = re.sub(r'[^a-zA-Z0-9_-]', '_', watched_path.name)
                                if collection.name == collection_pattern:
                                    matched_dir = watched_dir
                                    break
                            
                            if matched_dir:
                                status_text += f"  - {collection.name} (from {matched_dir})\n"
                            else:
                                status_text += f"  - {collection.name}\n"
                except Exception as e:
                    logger.debug(f"Could not list collections: {e}")
                
                # Get index statistics from file_metadata.json
                try:
                    metadata_path = Path(config.get('index_path', './data/index')) / 'file_metadata.json'
                    if metadata_path.exists():
                        with open(metadata_path) as f:
                            file_metadata = json.load(f)
                            status_text += f"\nIndex statistics:\n"
                            status_text += f"  Indexed files: {len(file_metadata)}\n"
                            total_chunks = sum(m.get('chunks', 0) for m in file_metadata.values())
                            status_text += f"  Total chunks: {total_chunks}\n"
                except Exception as e:
                    logger.debug(f"Could not read index stats: {e}")
                
                return [{
                    "type": "text",
                    "text": status_text
                }]
            
            else:
                return [{
                    "type": "text",
                    "text": f"Unknown tool: {name}"
                }]
                
        except Exception as e:
            logger.error(f"Error calling tool {name}: {e}", exc_info=True)
            return [{
                "type": "text",
                "text": f"Error: {str(e)}"
            }]
    
    # Run the server with stdio
    from mcp.server.models import InitializationOptions
    from mcp.types import ServerCapabilities
    
    server_task = None
    shutdown_requested = False
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        nonlocal shutdown_requested, server_task
        if not shutdown_requested:
            shutdown_requested = True
            logger.info(f"Received signal {signum}, shutting down gracefully...")
            shutdown_event.set()
            # Cancel the server task if it exists
            if server_task and not server_task.done():
                server_task.cancel()
            # Force exit after timeout if still hanging
            import threading
            def force_exit():
                import time
                time.sleep(3)
                logger.warning("Shutdown timeout, forcing exit...")
                import os
                os._exit(0)
            threading.Thread(target=force_exit, daemon=True).start()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        async with stdio_server() as streams:
            init_options = InitializationOptions(
                server_name="mcp-local-rag",
                server_version="0.1.0",
                capabilities=ServerCapabilities(
                    tools={}
                )
            )
            # Store the server task so we can cancel it on shutdown
            server_task = asyncio.current_task()
            await server.run(*streams, init_options)
    except asyncio.CancelledError:
        logger.info("Server task cancelled, shutting down...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        logger.info("Server shutting down...")
        shutdown_event.set()  # Ensure background tasks stop
        
        # Cancel all remaining tasks except current
        tasks = [t for t in asyncio.all_tasks() 
                if t is not asyncio.current_task() and not t.done()]
        for task in tasks:
            task.cancel()
        
        # Wait for tasks to complete cancellation
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info("Server stopped.")


if __name__ == "__main__":
    asyncio.run(main())