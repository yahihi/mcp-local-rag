"""
File discovery and filtering utilities for MCP Local RAG
"""

import fnmatch
import json
import logging
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any, Iterable, Sequence

logger = logging.getLogger(__name__)


def resolve_project_config(base_config: Dict[str, Any], dir_path: Path) -> Dict[str, Any]:
    """Merge base_config with <dir_path>/.mcp-local-rag.json if present (shallow)."""
    cfg = dict(base_config)
    project_cfg_path = Path(dir_path) / ".mcp-local-rag.json"
    if project_cfg_path.exists():
        try:
            with open(project_cfg_path) as f:
                project_cfg = json.load(f)
            if isinstance(project_cfg, dict):
                cfg.update(project_cfg)
        except Exception as e:
            logger.debug(f"Could not load project config {project_cfg_path}: {e}")
    return cfg


def effective_filters(config: Dict[str, Any], supported_extensions: Iterable[str]) -> Tuple[Set[str], Set[str]]:
    """Return (enabled_extensions, exclude_dirs) based on config and supported set."""
    supported_set = set(supported_extensions)
    raw_exts = [str(e).lower() for e in config.get("file_extensions", []) if isinstance(e, str)]
    raw_exts = [e for e in raw_exts if e.startswith('.')]
    enabled = {e for e in raw_exts if e in supported_set}
    if not enabled:
        enabled = set(supported_set)
    excludes = set(config.get('exclude_dirs', []) or [])
    return enabled, excludes


def _is_excluded_parts(path: Path, exclude_dir_patterns: Sequence[str]) -> bool:
    """Check if any path component matches an exclude pattern."""
    for part in path.parts:
        for pat in exclude_dir_patterns:
            try:
                if fnmatch.fnmatch(part, pat):
                    return True
            except Exception:
                continue
    return False


def discover_files(
    dir_path: Path,
    enabled_extensions: Set[str],
    exclude_dirs: Set[str],
    changed_within_seconds: Optional[int] = None,
    since_timestamp_file: Optional[Path] = None,
) -> List[Path]:
    """Discover files under dir_path using config filters.

    - Full scans (changed_within_seconds is None) use Python rglob for deterministic tests.
    - Changed scans prefer fd (--changed-within). If unavailable and a timestamp file is provided, try find -newer.
      Otherwise fall back to Python mtime filtering over extension-limited rglob.
    Always apply exclude patterns and extension filters.
    """
    dir_path = Path(dir_path)
    enabled = {e.lower() for e in enabled_extensions}
    excludes = list(exclude_dirs)
    
    # Load ignore patterns from .mcp-local-rag-ignore if exists
    ignore_patterns = set()
    ignore_file = dir_path / '.mcp-local-rag-ignore'
    if ignore_file.exists():
        with open(ignore_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    ignore_patterns.add(line)
        logger.info(f"Loaded {len(ignore_patterns)} ignore patterns from {ignore_file}")

    def finalize(paths: Iterable[Path]) -> List[Path]:
        out: List[Path] = []
        for p in paths:
            try:
                p = Path(p)
                if _is_excluded_parts(p, excludes):
                    continue
                
                # Check ignore patterns
                should_ignore = False
                if ignore_patterns:
                    file_name = p.name
                    for pattern in ignore_patterns:
                        # Check filename match
                        if fnmatch.fnmatch(file_name, pattern):
                            should_ignore = True
                            logger.debug(f"Ignoring {p.name} (matches pattern: {pattern})")
                            break
                        # Check path component match
                        for part in p.parts:
                            if fnmatch.fnmatch(part, pattern.rstrip('/')):
                                should_ignore = True
                                logger.debug(f"Ignoring {p} (path component matches: {pattern})")
                                break
                        if should_ignore:
                            break
                
                if should_ignore:
                    continue
                    
                if p.suffix.lower() in enabled:
                    out.append(p)
            except Exception:
                continue
        return out

    if changed_within_seconds is None:
        files: List[Path] = []
        for ext in enabled:
            try:
                files.extend(dir_path.rglob(f"*{ext}"))
            except Exception:
                continue
        return finalize(files)

    delta = int(changed_within_seconds)
    # Try fd first
    if shutil.which('fd'):
        names = sorted(e.lstrip('.') for e in enabled)
        pattern = f"*.{{{','.join(names)}}}" if names else '*'
        cmd = ['fd', '--type', 'f', '--changed-within', f"{delta}s", '--glob', '--ignore-case']
        for exc in excludes:
            cmd.extend(['--exclude', str(exc)])
        cmd.extend([pattern, str(dir_path)])
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if res.returncode == 0 and res.stdout:
                return finalize(Path(line) for line in res.stdout.splitlines() if line)
        except Exception:
            pass

    # Try find with timestamp, if provided
    if shutil.which('find') and since_timestamp_file and Path(since_timestamp_file).exists():
        cmd = ['find', str(dir_path), '-type', 'f', '-newer', str(since_timestamp_file)]
        if enabled:
            name_group: List[str] = []
            for ext in enabled:
                name_group.extend(['-name', f"*{ext}", '-o'])
            if name_group:
                name_group = name_group[:-1]
                cmd.extend(['\('] + name_group + ['\)'])
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if res.returncode == 0 and res.stdout:
                return finalize(Path(line) for line in res.stdout.splitlines() if line)
        except Exception:
            pass

    # Fallback to Python mtime filter
    now = time.time()
    files: List[Path] = []
    for ext in enabled:
        try:
            files.extend(dir_path.rglob(f"*{ext}"))
        except Exception:
            continue
    recent = []
    for p in files:
        try:
            if (now - Path(p).stat().st_mtime) <= delta:
                recent.append(p)
        except Exception:
            continue
    return finalize(recent)