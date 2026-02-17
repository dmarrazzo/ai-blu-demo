import os
from sentence_transformers import SentenceTransformer
from pymongo import MongoClient

# --- CONFIGURATION ---
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/?directConnection=true")
DB_NAME = "knowledge_base"
COLLECTION_NAME = "documents"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
# EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2" 

class VectorProbe:
    def __init__(self):
        self.model = SentenceTransformer(EMBEDDING_MODEL)
        self.client = MongoClient(MONGO_URI)
        self.collection = self.client[DB_NAME][COLLECTION_NAME]

    def hybrid_search(self, query_text, limit=3):
        # 1. Generate query vector
        query_vector = self.model.encode(query_text).tolist()

        # 2. Define the Hybrid Aggregation Pipeline
        # Note: Requires MongoDB 8.0+ or Atlas for native $rankFusion
        pipeline = [
            {
                "$rankFusion": {
                    "input": {
                        "pipelines": {
                            # Path A: Semantic Search (Vector)
                            "vector_path": [
                                {
                                    "$vectorSearch": {
                                        "index": "vector_index",
                                        "path": "embedding",
                                        "queryVector": query_vector,
                                        "numCandidates": 50,
                                        "limit": limit
                                    }
                                }
                            ],
                            # Path B: Keyword Search (BM25)
                            "keyword_path": [
                                {
                                    "$search": {
                                        "index": "keyword_index", # Requires a standard Search Index
                                        "text": {
                                            "query": query_text,
                                            "path": "text"
                                        }
                                    }
                                },
                                {"$limit": limit}
                            ]
                        }
                    },
                    # Weight Vector slightly higher
                    "combination": { 
                        "weights": {
                            "vector_path": 0.6,
                            "keyword_path": 0.4
                        }
                    }
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "file_name": 1,
                    "text": 1,
                    "score": { "$meta": "searchScore" }
                }
            }
        ]

        results = list(self.collection.aggregate(pipeline))
        
        print(f"\n--- Results for: '{query_text}' ---")
        
        # --- Update your print loop inside hybrid_search ---
        for i, res in enumerate(results):
            score = res.get('score')
            # Check if score is a float/int before formatting
            score_display = f"{score:.4f}" if isinstance(score, (int, float)) else "N/A"
            
            print(f"\n[Result {i+1}] (Score: {score_display})")
            print(f"Source: {res.get('file_name')}")
            print(f"Chunk: {res.get('text')}")
        return results
    

if __name__ == "__main__":
    probe = VectorProbe()
    user_query = input("Enter your search query: ")
    probe.hybrid_search(user_query)