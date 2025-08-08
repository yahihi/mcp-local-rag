"""
Utility functions for MCP Local RAG
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional, Any

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration from file or environment"""
    
    # Load environment variables
    load_dotenv()
    
    # Default configuration
    default_config = {
        "embedding_model": "local",  # "openai" or "local"
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
        "openai_embedding_model": "text-embedding-3-small",
        "local_embedding_model": "all-MiniLM-L6-v2",
        "index_path": "./data/index",
        "chunk_size": 1000,
        "chunk_overlap": 200,
        "collection_name": "codebase",
        "search_limit": 10,
        "similarity_threshold": 0.5,
        "file_extensions": [
            ".py", ".js", ".jsx", ".ts", ".tsx",
            ".java", ".cpp", ".c", ".h", ".hpp",
            ".cs", ".go", ".rs", ".php", ".rb",
            ".swift", ".kt", ".scala", ".sh",
            ".md", ".txt", ".json", ".yaml", ".yml"
        ],
        "exclude_dirs": [
            ".git", "node_modules", "__pycache__",
            ".venv", "venv", "env", ".env",
            "dist", "build", ".next", "target",
            ".pytest_cache", ".mypy_cache"
        ]
    }
    
    # Load from config file if provided
    if config_path:
        config_file = Path(config_path)
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    file_config = json.load(f)
                    # Merge with defaults
                    default_config.update(file_config)
                    logger.info(f"Loaded configuration from {config_path}")
            except Exception as e:
                logger.error(f"Error loading config file: {e}")
    else:
        # Try to find config.json in common locations
        search_paths = [
            Path.cwd() / "config.json",
            Path.cwd() / "mcp-local-rag" / "config.json",
            Path.home() / ".mcp-local-rag" / "config.json",
            Path(__file__).parent.parent / "config.json"
        ]
        
        for search_path in search_paths:
            if search_path.exists():
                try:
                    with open(search_path, 'r') as f:
                        file_config = json.load(f)
                        default_config.update(file_config)
                        logger.info(f"Found configuration at {search_path}")
                        break
                except Exception as e:
                    logger.error(f"Error loading config from {search_path}: {e}")
    
    # Override with environment variables
    env_overrides = {
        "embedding_model": os.getenv("MCP_EMBEDDING_MODEL"),
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
        "index_path": os.getenv("MCP_INDEX_PATH"),
        "chunk_size": os.getenv("MCP_CHUNK_SIZE"),
        "chunk_overlap": os.getenv("MCP_CHUNK_OVERLAP"),
    }
    
    # Collect watch directories from numbered environment variables
    watch_directories = []
    for i in range(1, 20):  # Support up to 20 directories
        watch_dir = os.getenv(f'MCP_WATCH_DIR_{i}')
        if watch_dir:
            watch_directories.append(watch_dir)
        else:
            break  # Stop at first missing number
    
    if watch_directories:
        default_config['watch_directories'] = watch_directories
        logger.info(f"Using watch directories from MCP_WATCH_DIR_* env vars: {watch_directories}")
    
    for key, value in env_overrides.items():
        if value is not None:
            if key in ["chunk_size", "chunk_overlap"]:
                try:
                    default_config[key] = int(value)
                except ValueError:
                    logger.warning(f"Invalid value for {key}: {value}")
            else:
                default_config[key] = value
    
    return default_config


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def get_language_from_extension(file_path: str) -> str:
    """Get programming language from file extension"""
    ext_to_lang = {
        '.py': 'Python',
        '.js': 'JavaScript',
        '.jsx': 'JavaScript',
        '.ts': 'TypeScript',
        '.tsx': 'TypeScript',
        '.java': 'Java',
        '.cpp': 'C++',
        '.c': 'C',
        '.h': 'C/C++',
        '.hpp': 'C++',
        '.cs': 'C#',
        '.go': 'Go',
        '.rs': 'Rust',
        '.php': 'PHP',
        '.rb': 'Ruby',
        '.swift': 'Swift',
        '.kt': 'Kotlin',
        '.scala': 'Scala',
        '.sh': 'Shell',
        '.bash': 'Bash',
        '.zsh': 'Zsh',
        '.fish': 'Fish',
        '.ps1': 'PowerShell',
        '.r': 'R',
        '.R': 'R',
        '.m': 'MATLAB',
        '.sql': 'SQL',
        '.md': 'Markdown',
        '.mdx': 'MDX',
        '.txt': 'Text',
        '.rst': 'reStructuredText',
        '.yml': 'YAML',
        '.yaml': 'YAML',
        '.json': 'JSON',
        '.xml': 'XML',
        '.html': 'HTML',
        '.htm': 'HTML',
        '.css': 'CSS',
        '.scss': 'SCSS',
        '.sass': 'Sass',
        '.less': 'Less',
        '.vue': 'Vue',
        '.svelte': 'Svelte',
    }
    
    path = Path(file_path)
    ext = path.suffix.lower()
    return ext_to_lang.get(ext, 'Unknown')


def is_binary_file(file_path: str) -> bool:
    """Check if a file is binary"""
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(1024)
            # Check for null bytes
            if b'\x00' in chunk:
                return True
            # Check for high proportion of non-text characters
            text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)))
            non_text = sum(1 for byte in chunk if byte not in text_chars)
            return non_text / len(chunk) > 0.3
    except Exception:
        return True


def sanitize_path(path: str) -> str:
    """Sanitize and normalize file path"""
    # Resolve to absolute path
    abs_path = Path(path).resolve()
    
    # Check if path exists
    if not abs_path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")
    
    return str(abs_path)


def create_file_summary(file_path: str, max_lines: int = 50) -> Dict[str, Any]:
    """Create a summary of a file"""
    path = Path(file_path)
    
    if not path.exists():
        return {"error": "File not found"}
    
    try:
        stats = path.stat()
        
        summary = {
            "name": path.name,
            "path": str(path),
            "size": stats.st_size,
            "size_formatted": format_file_size(stats.st_size),
            "language": get_language_from_extension(str(path)),
            "is_binary": is_binary_file(str(path))
        }
        
        if not summary["is_binary"]:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                summary["total_lines"] = len(lines)
                summary["preview"] = ''.join(lines[:max_lines])
        
        return summary
        
    except Exception as e:
        return {"error": str(e)}