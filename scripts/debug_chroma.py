#!/usr/bin/env python3
"""
Debug ChromaDB content
"""

import asyncio
from src.vectordb import VectorDB
from src.utils import load_config

async def debug_chroma():
    """Debug what's actually in the ChromaDB"""
    config = load_config()
    vectordb = VectorDB(config)
    
    # Get all documents
    try:
        collection = vectordb.collection
        result = collection.get()
        
        print(f"Total documents in ChromaDB: {len(result['ids'])}")
        print(f"\nDocument IDs (first 10):")
        for i, doc_id in enumerate(result['ids'][:10]):
            print(f"  {i+1}. {doc_id}")
        
        print(f"\nDocument metadata (first 5):")
        for i, metadata in enumerate(result['metadatas'][:5]):
            print(f"  {i+1}. {metadata}")
            
        print(f"\nDocument content preview (first 3):")
        for i, document in enumerate(result['documents'][:3]):
            print(f"  {i+1}. {document[:100]}...")
            
        # Search for specific patterns in all documents
        print(f"\nSearching for 'NEW_FILE_MARKER_19_35' in all documents...")
        found_count = 0
        for i, document in enumerate(result['documents']):
            if 'NEW_FILE_MARKER_19_35' in document:
                found_count += 1
                print(f"  Found in document {i}: {result['metadatas'][i].get('file_path', 'unknown')}")
                print(f"    Content: {document[:200]}...")
        
        if found_count == 0:
            print("  Not found in any document!")
            
        print(f"\nSearching for 'test_new_file.py' in all documents...")
        found_count = 0
        for i, document in enumerate(result['documents']):
            if 'test_new_file.py' in document:
                found_count += 1
                print(f"  Found in document {i}: {result['metadatas'][i].get('file_path', 'unknown')}")
                print(f"    Content: {document[:200]}...")
        
        if found_count == 0:
            print("  Not found in any document!")
            
    except Exception as e:
        print(f"Error accessing ChromaDB: {e}")

if __name__ == "__main__":
    asyncio.run(debug_chroma())