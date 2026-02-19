import os
import json
import time
from pathlib import Path
from pymongo import MongoClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/?directConnection=true")
DB_NAME = "knowledge_base"
COLLECTION_NAME = "documents"
PVC_MOUNT = Path(os.getenv("PVC_MOUNT", "/mnt/data"))
STAGING_DIR = Path(PVC_MOUNT / "staging")

def run_ingestion():
    client = MongoClient(MONGO_URI)
    collection = client[DB_NAME][COLLECTION_NAME]
    
    # Clean for fresh ingest (optional)
    collection.delete_many({})
    
    enriched_files = list(STAGING_DIR.glob("*_enriched.json"))
    for e_file in enriched_files:
        with open(e_file, "r") as f:
            data = json.load(f)
            
        payload = [
            {
                "file_name": data["file_name"],
                "chunk_id": i,
                "text": text,
                "embedding": data["embeddings"][i],
                "ingested_at": time.time(),
            }
            for i, text in enumerate(data["chunks"])
        ]
        
        if payload:
            collection.insert_many(payload)
            print(f"🚀 Ingested {len(payload)} chunks from {data['file_name']}")
        
        e_file.unlink() # Cleanup PVC

if __name__ == "__main__":
    run_ingestion()