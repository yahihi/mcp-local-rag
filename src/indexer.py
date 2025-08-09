"""
File Indexer for RAG System
"""

import hashlib
import fnmatch
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import tiktoken
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from embeddings import EmbeddingGenerator
from vectordb import VectorDB

logger = logging.getLogger(__name__)


class FileChunk:
    """Represents a chunk of a file"""
    
    def __init__(
        self,
        content: str,
        file_path: str,
        start_line: int,
        end_line: int,
        chunk_index: int,
        metadata: Optional[Dict] = None
    ):
        self.content = content
        self.file_path = file_path
        self.start_line = start_line
        self.end_line = end_line
        self.chunk_index = chunk_index
        self.metadata = metadata or {}
        
        # Generate unique ID
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        self.id = f"{file_path}:{chunk_index}:{content_hash}"
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage"""
        return {
            "id": self.id,
            "content": self.content,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "chunk_index": self.chunk_index,
            "metadata": self.metadata
        }


class FileIndexer:
    """Indexes files for RAG retrieval"""
    
    SUPPORTED_EXTENSIONS = {
        '.py': 'python',
        '.js': 'javascript',
        '.jsx': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'typescript',
        '.java': 'java',
        '.cpp': 'cpp',
        '.c': 'c',
        '.h': 'c',
        '.hpp': 'cpp',
        '.cs': 'csharp',
        '.go': 'go',
        '.rs': 'rust',
        '.php': 'php',
        '.rb': 'ruby',
        '.swift': 'swift',
        '.kt': 'kotlin',
        '.scala': 'scala',
        '.sh': 'shell',
        '.bash': 'shell',
        '.zsh': 'shell',
        '.fish': 'shell',
        '.ps1': 'powershell',
        '.r': 'r',
        '.R': 'r',
        '.m': 'matlab',
        '.sql': 'sql',
        '.md': 'markdown',
        '.mdx': 'markdown',
        '.txt': 'text',
        '.rst': 'restructuredtext',
        '.yml': 'yaml',
        '.yaml': 'yaml',
        '.json': 'json',
        '.xml': 'xml',
        '.html': 'html',
        '.htm': 'html',
        '.css': 'css',
        '.scss': 'scss',
        '.sass': 'sass',
        '.less': 'less',
        '.vue': 'vue',
        '.svelte': 'svelte',
    }
    
    def __init__(self, config: Dict):
        self.config = config
        self.chunk_size = config.get('chunk_size', 1000)
        self.chunk_overlap = config.get('chunk_overlap', 200)
        self.index_path = Path(config.get('index_path', './data/index'))
        self.index_path.mkdir(parents=True, exist_ok=True)
        self.progress_interval = int(config.get('progress_interval', 200))
        
        # Initialize components
        self.vectordb = VectorDB(config)
        self.embeddings = EmbeddingGenerator(config)
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
        # File metadata cache
        self.file_metadata_path = self.index_path / 'file_metadata.json'
        self.file_metadata = self._load_file_metadata()
        
        # File watcher
        self.observer = None

        # Exclude directory patterns from config (fallback to sensible defaults)
        default_excludes = {
            '.git', 'node_modules', '__pycache__', '.venv', 'venv', 'env', '.env',
            'dist', 'build', '.next', 'target'
        }
        self.exclude_dir_patterns = set(config.get('exclude_dirs', list(default_excludes)))

    def _is_excluded(self, path: Path) -> bool:
        """Return True if any path component matches an exclude pattern."""
        for part in path.parts:
            for pat in self.exclude_dir_patterns:
                try:
                    if fnmatch.fnmatch(part, pat):
                        return True
                except Exception:
                    # In case of an invalid pattern, skip matching
                    continue
        return False
    
    def _load_file_metadata(self) -> Dict:
        """Load file metadata cache"""
        if self.file_metadata_path.exists():
            with open(self.file_metadata_path, 'r') as f:
                return json.load(f)
        return {}
    
    def _save_file_metadata(self):
        """Save file metadata cache"""
        with open(self.file_metadata_path, 'w') as f:
            json.dump(self.file_metadata, f, indent=2)
    
    def _get_file_hash(self, file_path: str) -> str:
        """Get hash of file content"""
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    
    def _should_index_file(self, file_path: str, force: bool = False) -> bool:
        """Check if file should be indexed"""
        if force:
            return True
        
        if file_path not in self.file_metadata:
            return True
        
        current_hash = self._get_file_hash(file_path)
        stored_hash = self.file_metadata[file_path].get('hash')
        
        return current_hash != stored_hash
    
    def _chunk_text(self, text: str, file_path: str) -> List[FileChunk]:
        """Split text into overlapping chunks"""
        lines = text.split('\n')
        chunks = []
        
        current_chunk = []
        current_tokens = 0
        start_line = 0
        chunk_index = 0
        
        for i, line in enumerate(lines):
            line_tokens = len(self.tokenizer.encode(line))
            
            if current_tokens + line_tokens > self.chunk_size and current_chunk:
                # Create chunk
                chunk_content = '\n'.join(current_chunk)
                chunks.append(FileChunk(
                    content=chunk_content,
                    file_path=file_path,
                    start_line=start_line + 1,
                    end_line=i,
                    chunk_index=chunk_index
                ))
                
                # Start new chunk with overlap
                overlap_lines = []
                overlap_tokens = 0
                for j in range(len(current_chunk) - 1, -1, -1):
                    line_tokens = len(self.tokenizer.encode(current_chunk[j]))
                    if overlap_tokens + line_tokens <= self.chunk_overlap:
                        overlap_lines.insert(0, current_chunk[j])
                        overlap_tokens += line_tokens
                    else:
                        break
                
                current_chunk = overlap_lines
                current_tokens = overlap_tokens
                start_line = i - len(overlap_lines) + 1
                chunk_index += 1
            
            current_chunk.append(line)
            current_tokens += line_tokens
        
        # Add final chunk
        if current_chunk:
            chunk_content = '\n'.join(current_chunk)
            chunks.append(FileChunk(
                content=chunk_content,
                file_path=file_path,
                start_line=start_line + 1,
                end_line=len(lines),
                chunk_index=chunk_index
            ))
        
        return chunks
    
    async def index_file(self, file_path: str, force_reindex: bool = False, collection_name: Optional[str] = None) -> int:
        """Index a single file"""
        path = Path(file_path)
        
        # If collection_name is provided, switch to it
        if collection_name:
            self.vectordb.switch_collection(collection_name)
        
        # Check if file should be indexed
        if not self._should_index_file(str(path), force_reindex):
            logger.debug(f"Skipping unchanged file: {path}")
            return 0
        
        # Get file extension and language
        ext = path.suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            logger.warning(f"Unsupported file type: {ext}")
            return 0
        
        language = self.SUPPORTED_EXTENSIONS[ext]
        
        try:
            # Read file content
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Create chunks
            chunks = self._chunk_text(content, str(path))

            # Batch-generate embeddings for all chunks of this file
            texts = [chunk.content for chunk in chunks]
            embeddings_out: List[List[float]] = []
            if texts:
                embeddings_out = await self.embeddings.batch_generate(texts)

            # Prepare for storage
            documents = []
            embeddings_list = []
            metadatas = []
            ids = []

            for chunk, embedding in zip(chunks, embeddings_out):
                documents.append(chunk.content)
                embeddings_list.append(embedding)
                ids.append(chunk.id)
                metadatas.append({
                    "file_path": chunk.file_path,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "chunk_index": chunk.chunk_index,
                    "language": language,
                    "file_size": path.stat().st_size,
                    "modified_at": datetime.fromtimestamp(
                        path.stat().st_mtime
                    ).isoformat()
                })
            
            # If updating existing file, delete old chunks first
            if str(path) in self.file_metadata:
                logger.info(f"Deleting old chunks for {path}")
                await self.vectordb.delete_by_file(str(path))
            
            # Store in vector database
            docs_to_add = []
            for i in range(len(documents)):
                docs_to_add.append({
                    'id': ids[i],
                    'content': documents[i],
                    'embedding': embeddings_list[i],
                    'metadata': metadatas[i]
                })
            
            await self.vectordb.add_documents(docs_to_add)
            
            # Update file metadata
            self.file_metadata[str(path)] = {
                "hash": self._get_file_hash(str(path)),
                "chunks": len(chunks),
                "language": language,
                "indexed_at": datetime.now().isoformat()
            }
            self._save_file_metadata()
            
            logger.info(f"Indexed {path}: {len(chunks)} chunks")
            return len(chunks)
            
        except Exception as e:
            logger.error(f"Error indexing file {path}: {e}")
            return 0
    
    async def index_directory(
        self,
        directory: str,
        extensions: Optional[List[str]] = None,
        force_reindex: bool = False
    ) -> Dict[str, int]:
        """Index all files in a directory"""
        stats = {
            "files_processed": 0,
            "files_skipped": 0,
            "chunks_created": 0,
            "errors": 0
        }
        
        path = Path(directory).resolve()
        if not path.exists():
            raise ValueError(f"Directory not found: {directory}")
        
        # Use project directory name as collection name
        # Remove special characters and use underscore
        import re
        collection_name = re.sub(r'[^a-zA-Z0-9_-]', '_', path.name)
        if not collection_name:
            collection_name = "default"
        
        # Switch to project-specific collection
        logger.info(f"Using collection '{collection_name}' for project: {path}")
        self.vectordb.switch_collection(collection_name)
        
        # Determine extensions to process
        if extensions:
            valid_extensions = [ext for ext in extensions if ext in self.SUPPORTED_EXTENSIONS]
        else:
            valid_extensions = list(self.SUPPORTED_EXTENSIONS.keys())
        
        # Find all files to index
        files_to_index = []
        for ext in valid_extensions:
            files_to_index.extend(path.rglob(f"*{ext}"))
        
        # Exclude directories based on configured patterns
        files_to_index = [f for f in files_to_index if not self._is_excluded(f)]
        
        logger.info(f"Found {len(files_to_index)} files to process")
        
        # Index each file
        total = len(files_to_index)
        for i, file_path in enumerate(files_to_index, start=1):
            try:
                chunks = await self.index_file(str(file_path), force_reindex)
                if chunks > 0:
                    stats["files_processed"] += 1
                    stats["chunks_created"] += chunks
                else:
                    stats["files_skipped"] += 1
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                stats["errors"] += 1
            # Heartbeat progress
            if self.progress_interval and i % self.progress_interval == 0:
                logger.info(
                    f"Progress: {i}/{total} files, processed={stats['files_processed']}, "
                    f"skipped={stats['files_skipped']}, errors={stats['errors']}, "
                    f"chunks={stats['chunks_created']}"
                )
        
        logger.info(f"Indexing complete: {stats}")
        return stats
    
    def start_watching(self, directory: str):
        """Start watching directory for changes"""
        if self.observer:
            self.observer.stop()
        
        event_handler = FileChangeHandler(self)
        self.observer = Observer()
        self.observer.schedule(event_handler, directory, recursive=True)
        self.observer.start()
        logger.info(f"Started watching directory: {directory}")
    
    def stop_watching(self):
        """Stop watching directory"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            logger.info("Stopped watching directory")


class FileChangeHandler(FileSystemEventHandler):
    """Handle file system events for auto-indexing"""
    
    def __init__(self, indexer: FileIndexer):
        self.indexer = indexer
    
    def on_modified(self, event):
        if not event.is_directory:
            file_path = Path(event.src_path)
            if file_path.suffix.lower() in FileIndexer.SUPPORTED_EXTENSIONS:
                logger.info(f"File modified: {file_path}")
                # Schedule reindexing (in production, use async task queue)
                # asyncio.create_task(self.indexer.index_file(str(file_path)))
    
    def on_created(self, event):
        if not event.is_directory:
            file_path = Path(event.src_path)
            if file_path.suffix.lower() in FileIndexer.SUPPORTED_EXTENSIONS:
                logger.info(f"File created: {file_path}")
                # Schedule indexing
    
    def on_deleted(self, event):
        if not event.is_directory:
            file_path = Path(event.src_path)
            logger.info(f"File deleted: {file_path}")
            # Remove from index
