import os
import json
from pathlib import Path
from sentence_transformers import SentenceTransformer

PVC_MOUNT = Path(os.getenv("PVC_MOUNT", "/mnt/data"))
STAGING_DIR = Path(PVC_MOUNT / "staging")
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

def run_embedding():
    model = SentenceTransformer(EMBEDDING_MODEL)
    # Find all chunk files from Stage 1
    chunk_files = list(STAGING_DIR.glob("*_chunks.json"))
    
    for c_file in chunk_files:
        with open(c_file, "r") as f:
            data = json.load(f)
        
        print(f"🧠 Embedding {len(data['chunks'])} chunks for {data['file_name']}...")
        embeddings = model.encode(data['chunks']).tolist()
        
        # Add embeddings to the data structure
        data["embeddings"] = embeddings
        
        # Save enriched data for Stage 3
        enriched_file = STAGING_DIR / f"{c_file.stem}_enriched.json"
        with open(enriched_file, "w") as f:
            json.dump(data, f)
        
        # Optional: cleanup the raw chunk file to save space on PVC
        c_file.unlink()

if __name__ == "__main__":
    run_embedding()