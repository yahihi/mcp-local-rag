"""
Vector Database management using ChromaDB
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

logger = logging.getLogger(__name__)


class VectorDB:
    """Vector database for storing and searching embeddings"""
    
    def __init__(self, config: Dict, collection_name: Optional[str] = None):
        self.config = config
        self.index_path = Path(config.get('index_path', './data/index'))
        self.index_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(self.index_path / 'chroma'),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Get or create collection
        self.collection_name = collection_name or config.get('collection_name', 'codebase')
        self._init_collection()
        self.collections_cache = {}
    
    def _init_collection(self):
        """Initialize or get existing collection"""
        try:
            # Try to get existing collection
            self.collection = self.client.get_collection(
                name=self.collection_name
            )
            logger.info(f"Using existing collection: {self.collection_name}")
        except Exception:
            # Create new collection
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "Local codebase RAG index"}
            )
            logger.info(f"Created new collection: {self.collection_name}")
    
    def switch_collection(self, collection_name: str):
        """Switch to a different collection"""
        self.collection_name = collection_name
        self._init_collection()
        logger.info(f"Switched to collection: {collection_name}")
    
    def get_or_create_collection(self, collection_name: str):
        """Get or create a collection by name"""
        if collection_name in self.collections_cache:
            return self.collections_cache[collection_name]
        
        try:
            collection = self.client.get_collection(name=collection_name)
            logger.info(f"Using existing collection: {collection_name}")
        except Exception:
            collection = self.client.create_collection(
                name=collection_name,
                metadata={"description": f"Project index: {collection_name}"}
            )
            logger.info(f"Created new collection: {collection_name}")
        
        self.collections_cache[collection_name] = collection
        return collection
    
    def list_collections(self) -> List[str]:
        """List all available collections"""
        collections = self.client.list_collections()
        return [col.name for col in collections]
    
    async def add_documents(
        self,
        documents: List[Dict[str, Any]],
        collection_name: Optional[str] = None
    ) -> None:
        """Add documents with embeddings to the database"""
        try:
            # Get the target collection
            collection = self.get_or_create_collection(collection_name) if collection_name else self.collection
            
            # Extract data from documents
            ids = [doc['id'] for doc in documents]
            contents = [doc['content'] for doc in documents]
            embeddings = [doc['embedding'] for doc in documents]
            metadatas = [doc.get('metadata', {}) for doc in documents]
            
            # Add to collection
            collection.add(
                ids=ids,
                documents=contents,
                embeddings=embeddings,
                metadatas=metadatas
            )
            
            logger.info(f"Added {len(documents)} documents to collection")
            
        except Exception as e:
            logger.error(f"Error adding documents: {e}")
            raise
    
    async def search(
        self,
        query_embedding: List[float],
        limit: int = 10,
        filter: Optional[Dict] = None,
        collection_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar documents"""
        try:
            # Get the target collection
            collection = self.get_or_create_collection(collection_name) if collection_name else self.collection
            
            # Perform search
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=limit,
                where=filter
            )
            
            # Format results
            formatted_results = []
            
            if results['ids'] and results['ids'][0]:
                for i in range(len(results['ids'][0])):
                    formatted_results.append({
                        'id': results['ids'][0][i],
                        'content': results['documents'][0][i] if results['documents'] else '',
                        'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                        'score': 1 - results['distances'][0][i] if results['distances'] else 0
                    })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error searching documents: {e}")
            return []
    
    async def get_document_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific document by ID"""
        try:
            results = self.collection.get(ids=[doc_id])
            
            if results['ids']:
                return {
                    'id': results['ids'][0],
                    'document': results['documents'][0] if results['documents'] else None,
                    'metadata': results['metadatas'][0] if results['metadatas'] else {}
                }
            return None
            
        except Exception as e:
            logger.error(f"Error getting document: {e}")
            return None
    
    async def delete_documents(self, ids: List[str]) -> bool:
        """Delete documents by IDs"""
        try:
            self.collection.delete(ids=ids)
            logger.info(f"Deleted {len(ids)} documents")
            return True
        except Exception as e:
            logger.error(f"Error deleting documents: {e}")
            return False
    
    async def delete_by_file(self, file_path: str, collection_name: Optional[str] = None) -> int:
        """Delete all chunks from a specific file"""
        try:
            # Get the target collection
            collection = self.get_or_create_collection(collection_name) if collection_name else self.collection
            
            # Delete by metadata filter
            collection.delete(
                where={"file_path": file_path}
            )
            logger.info(f"Deleted chunks from {file_path}")
            return 0  # ChromaDB doesn't return delete count
            
        except Exception as e:
            logger.error(f"Error deleting file chunks: {e}")
            return 0
    
    async def get_all_files(self, collection_name: Optional[str] = None) -> List[str]:
        """Get all unique file paths in the collection"""
        try:
            # Get the target collection
            collection = self.get_or_create_collection(collection_name) if collection_name else self.collection
            
            # Get all documents' metadata
            results = collection.get()
            
            # Extract unique file paths
            file_paths = set()
            if results['metadatas']:
                for metadata in results['metadatas']:
                    if metadata and 'file_path' in metadata:
                        file_paths.add(metadata['file_path'])
            
            return list(file_paths)
            
        except Exception as e:
            logger.error(f"Error getting all files: {e}")
            return []
    
    async def clear(self, collection_name: Optional[str] = None) -> None:
        """Clear all documents from the collection"""
        try:
            collection_name = collection_name or self.collection_name
            
            # Delete the collection
            self.client.delete_collection(name=collection_name)
            logger.info(f"Deleted collection: {collection_name}")
            
            # Recreate it
            self._init_collection()
            logger.info(f"Recreated collection: {collection_name}")
            
        except Exception as e:
            logger.error(f"Error clearing collection: {e}")
            raise
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the collection"""
        try:
            # Get total document count
            count = self.collection.count()
            
            # Get sample of documents to analyze
            sample = self.collection.get(limit=100)
            
            # Analyze file types
            file_types = {}
            unique_files = set()
            
            if sample['metadatas']:
                for metadata in sample['metadatas']:
                    if 'language' in metadata:
                        lang = metadata['language']
                        file_types[lang] = file_types.get(lang, 0) + 1
                    if 'file_path' in metadata:
                        unique_files.add(metadata['file_path'])
            
            return {
                'total_chunks': count,
                'file_types': file_types,
                'unique_files_sampled': len(unique_files),
                'collection_name': self.collection_name
            }
            
        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            return {}
    
    def reset_collection(self) -> bool:
        """Reset (delete and recreate) the collection"""
        try:
            self.client.delete_collection(name=self.collection_name)
            self._init_collection()
            logger.info(f"Reset collection: {self.collection_name}")
            return True
        except Exception as e:
            logger.error(f"Error resetting collection: {e}")
            return False
    
    async def update_metadata(self, doc_id: str, metadata: Dict) -> bool:
        """Update metadata for a document"""
        try:
            self.collection.update(
                ids=[doc_id],
                metadatas=[metadata]
            )
            return True
        except Exception as e:
            logger.error(f"Error updating metadata: {e}")
            return False