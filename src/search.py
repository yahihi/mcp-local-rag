"""
Search engine for RAG system
"""

import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Any

from embeddings import EmbeddingGenerator
from vectordb import VectorDB

logger = logging.getLogger(__name__)


class SearchEngine:
    """Search engine for querying indexed codebase"""
    
    def __init__(self, vectordb: VectorDB, config: Dict):
        self.vectordb = vectordb
        self.config = config
        self.embeddings = EmbeddingGenerator(config)
        
        # Search parameters
        self.default_limit = config.get('search_limit', 10)
        self.similarity_threshold = config.get('similarity_threshold', 0.5)
    
    async def search(
        self,
        query: str,
        limit: Optional[int] = None,
        file_type: Optional[str] = None,
        file_path_pattern: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for relevant code chunks"""
        try:
            # Generate query embedding
            query_embedding = await self.embeddings.generate(query)
            
            # Build filter
            filter_dict = {}
            if file_type:
                filter_dict['language'] = file_type
            
            # Search in vector database
            results = await self.vectordb.search(
                query_embedding=query_embedding,
                limit=limit or self.default_limit,
                filter=filter_dict if filter_dict else None
            )
            
            # Filter by file path pattern if specified
            if file_path_pattern:
                results = [
                    r for r in results
                    if file_path_pattern in r['metadata'].get('file_path', '')
                ]
            
            # Format results
            formatted_results = []
            for result in results:
                # Get score (already normalized 0-1 from vectordb)
                score = result.get('score', 0)
                
                # Skip results below threshold
                if score < self.similarity_threshold:
                    continue
                
                metadata = result.get('metadata', {})
                formatted_results.append({
                    'file_path': metadata.get('file_path', 'unknown'),
                    'start_line': metadata.get('start_line', 0),
                    'end_line': metadata.get('end_line', 0),
                    'language': metadata.get('language', 'unknown'),
                    'score': score,
                    'preview': self._create_preview(result.get('content', '')),
                    'chunk_id': result.get('id', '')
                })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []
    
    async def get_file_context(
        self,
        file_path: str,
        line_number: int = 0,
        context_lines: int = 50
    ) -> Dict[str, Any]:
        """Get context around a specific line in a file"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            total_lines = len(lines)
            
            # Calculate start and end lines
            if line_number <= 0:
                # If no line number specified, return beginning of file
                start_line = 0
                end_line = min(context_lines, total_lines)
            else:
                # Center context around the specified line
                start_line = max(0, line_number - context_lines)
                end_line = min(line_number + context_lines, total_lines)
            
            # Extract content
            context_content = ''.join(lines[start_line:end_line])
            
            return {
                'file_path': file_path,
                'content': context_content,
                'start_line': start_line + 1,  # Convert to 1-based
                'end_line': end_line,
                'total_lines': total_lines
            }
            
        except Exception as e:
            logger.error(f"Error getting file context: {e}")
            return {
                'file_path': file_path,
                'content': '',
                'start_line': 0,
                'end_line': 0,
                'total_lines': 0,
                'error': str(e)
            }
    
    async def find_similar_files(
        self,
        file_path: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Find files similar to a given file"""
        try:
            path = Path(file_path)
            if not path.exists():
                logger.warning(f"File not found: {file_path}")
                return []
            
            # Read file content
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Limit content for embedding (take first 2000 characters)
            content_sample = content[:2000]
            
            # Generate embedding for the file sample
            file_embedding = await self.embeddings.generate(content_sample)
            
            # Search for similar chunks
            results = await self.vectordb.search(
                query_embedding=file_embedding,
                limit=limit * 3  # Get more results to aggregate by file
            )
            
            # Aggregate by file
            file_scores = defaultdict(list)
            for result in results:
                file_path = result['metadata'].get('file_path')
                if file_path and file_path != str(path):
                    score = result.get('score', 0.0)
                    file_scores[file_path].append(score)
            
            # Calculate average score per file
            similar_files = []
            for file_path, scores in file_scores.items():
                avg_score = sum(scores) / len(scores)
                similar_files.append({
                    'path': file_path,
                    'similarity': avg_score,
                    'description': self._get_file_description(file_path)
                })
            
            # Sort by similarity and return top results
            similar_files.sort(key=lambda x: x['similarity'], reverse=True)
            return similar_files[:limit]
            
        except Exception as e:
            logger.error(f"Error finding similar files: {e}")
            return []
    
    async def find_related_chunks(
        self,
        file_path: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Find chunks related to a specific file"""
        try:
            # Get all chunks from the file
            file_results = await self.vectordb.collection.get(
                where={"file_path": file_path}
            )
            
            if not file_results['ids']:
                return []
            
            # Use the first chunk's embedding to find related chunks
            # In production, might want to aggregate multiple chunks
            first_chunk = file_results['embeddings'][0] if file_results['embeddings'] else None
            
            if not first_chunk:
                return []
            
            # Search for similar chunks from other files
            results = await self.vectordb.search(
                query_embedding=first_chunk,
                limit=limit + len(file_results['ids']),  # Extra to filter out same file
                filter=None
            )
            
            # Filter out chunks from the same file
            related = []
            for result in results:
                metadata = result.get('metadata', {})
                if metadata.get('file_path') != file_path:
                    related.append({
                        'file_path': metadata.get('file_path'),
                        'start_line': metadata.get('start_line'),
                        'end_line': metadata.get('end_line'),
                        'preview': self._create_preview(result.get('content', ''))
                    })
                    
                    if len(related) >= limit:
                        break
            
            return related
            
        except Exception as e:
            logger.error(f"Error finding related chunks: {e}")
            return []
    
    async def semantic_code_search(
        self,
        query: str,
        context_lines: int = 3
    ) -> List[Dict[str, Any]]:
        """Advanced semantic search with context"""
        try:
            # First, do a regular search
            initial_results = await self.search(query, limit=self.default_limit * 2)
            
            # Group results by file
            file_groups = defaultdict(list)
            for result in initial_results:
                file_groups[result['file_path']].append(result)
            
            # Merge adjacent chunks and add context
            enhanced_results = []
            for file_path, chunks in file_groups.items():
                # Sort chunks by start line
                chunks.sort(key=lambda x: x['start_line'])
                
                # Merge adjacent or overlapping chunks
                merged_chunks = []
                current_chunk = None
                
                for chunk in chunks:
                    if current_chunk is None:
                        current_chunk = chunk.copy()
                    elif chunk['start_line'] <= current_chunk['end_line'] + context_lines:
                        # Merge chunks
                        current_chunk['end_line'] = max(current_chunk['end_line'], chunk['end_line'])
                        current_chunk['score'] = max(current_chunk['score'], chunk['score'])
                    else:
                        merged_chunks.append(current_chunk)
                        current_chunk = chunk.copy()
                
                if current_chunk:
                    merged_chunks.append(current_chunk)
                
                # Add context to each merged chunk
                for chunk in merged_chunks:
                    chunk['context'] = await self._get_chunk_context(
                        file_path,
                        chunk['start_line'],
                        chunk['end_line'],
                        context_lines
                    )
                
                enhanced_results.extend(merged_chunks)
            
            # Sort by score and return top results
            enhanced_results.sort(key=lambda x: x['score'], reverse=True)
            return enhanced_results[:self.default_limit]
            
        except Exception as e:
            logger.error(f"Semantic search error: {e}")
            return []
    
    async def _get_chunk_context(
        self,
        file_path: str,
        start_line: int,
        end_line: int,
        context_lines: int
    ) -> Dict[str, Any]:
        """Get context around a chunk"""
        try:
            path = Path(file_path)
            if not path.exists():
                return {}
            
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            # Calculate context boundaries
            context_start = max(0, start_line - context_lines - 1)
            context_end = min(len(lines), end_line + context_lines)
            
            return {
                'before': ''.join(lines[context_start:start_line-1]),
                'chunk': ''.join(lines[start_line-1:end_line]),
                'after': ''.join(lines[end_line:context_end])
            }
            
        except Exception as e:
            logger.error(f"Error getting chunk context: {e}")
            return {}
    
    def _create_preview(self, text: str, max_length: int = 200) -> str:
        """Create a preview of text"""
        if not text:
            return ""
        
        # Clean up whitespace
        preview = ' '.join(text.split())
        
        # Truncate if needed
        if len(preview) > max_length:
            preview = preview[:max_length] + "..."
        
        return preview
    
    def _get_file_description(self, file_path: str) -> str:
        """Get a brief description of a file"""
        path = Path(file_path)
        
        # Get file extension and type
        ext = path.suffix.lower()
        file_type = "file"
        
        if ext in ['.py']:
            file_type = "Python module"
        elif ext in ['.js', '.jsx']:
            file_type = "JavaScript file"
        elif ext in ['.ts', '.tsx']:
            file_type = "TypeScript file"
        elif ext in ['.md']:
            file_type = "Markdown document"
        elif ext in ['.json']:
            file_type = "JSON configuration"
        elif ext in ['.yaml', '.yml']:
            file_type = "YAML configuration"
        
        return f"{file_type}: {path.name}"