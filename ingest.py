import os
from pathlib import Path
import time
from docling.document_converter import DocumentConverter
from sentence_transformers import SentenceTransformer
from pymongo import MongoClient
from pymongo.operations import SearchIndexModel

# --- CONFIGURATION ---
DATA_DIR = "data"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
# EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
NUM_DIMENSIONS = 384
# The 'directConnection=true' is often helpful for local single-node Atlas containers
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/?directConnection=true")
DB_NAME = "knowledge_base"
COLLECTION_NAME = "documents"


class RAGPipeline:
    def __init__(self):
        print(f"--- Initializing Pipeline with {EMBEDDING_MODEL} ---")
        self.converter = DocumentConverter()
        self.embed_model = SentenceTransformer(EMBEDDING_MODEL)
        self.client = MongoClient(MONGO_URI)
        self.collection = self.client[DB_NAME][COLLECTION_NAME]

    def setup_database(self):
        """Creates the necessary Search Indexes for BM25 and Vector Search."""
        print("🛠️  Configuring Atlas Search Indexes...")

        indexes = [
            SearchIndexModel(
                name="keyword_index",
                definition={
                    "mappings": {
                        "dynamic": False,
                        "fields": {
                            "text": {
                                "type": "string",
                                "analyzer": "lucene.standard",
                            }
                        },
                    }
                },
            ),
            SearchIndexModel(
                name="vector_index",
                type="vectorSearch",
                definition={
                    "fields": [
                        {
                            "type": "vector",
                            "path": "embedding",
                            "numDimensions": NUM_DIMENSIONS,
                            "similarity": "cosine",
                        }
                    ]
                },
            ),
        ]

        try:
            self.collection.create_search_indexes(models=indexes)
            print("⏳ Indexes requested. They will build in the background.")
        except Exception as e:
            print(f"⚠️ Index setup note: {e}")

    def chunk_text(self, text, max_chars=800, overlap=100):
        """
        Splits text into chunks of max_chars with a specific overlap.
        """
        chunks = []
        start = 0
        
        # Ensure we don't get stuck in an infinite loop if text is tiny
        if len(text) <= max_chars:
            return [text.strip()] if len(text.strip()) > 20 else []

        while start < len(text):
            # Define the end point of the chunk
            end = start + max_chars
            
            # If we aren't at the end of the string, try to snap to the 
            # nearest previous space so we don't cut a word in half.
            if end < len(text):
                last_space = text.rfind(" ", start, end)
                if last_space != -1:
                    end = last_space

            chunk = text[start:end].strip()
            if len(chunk) > 20:
                chunks.append(chunk)
            
            # Move the start pointer back by the overlap amount
            start = end - overlap
            
            # Safety check: ensure start always advances to avoid infinite loops
            if start >= end:
                start = end + 1
                
        return chunks

    def ingest_data(self):
        """Parses all PDFs in the data directory and loads them into Mongo."""
        pdf_files = list(Path(DATA_DIR).glob("*.pdf"))
        if not pdf_files:
            print(f"❌ No PDFs found in ./{DATA_DIR}")
            return

        # delete old data
        self.collection.delete_many({})

        for pdf in pdf_files:
            print(f"📄 Processing {pdf.name}...")
            result = self.converter.convert(str(pdf))
            markdown_content = result.document.export_to_markdown()

            chunks = self.chunk_text(markdown_content, max_chars=800, overlap=150)
            
            payload = []
            for i, text in enumerate(chunks):
                payload.append(
                    {
                        "file_name": pdf.name,
                        "chunk_id": i,
                        "text": text,
                        "embedding": self.embed_model.encode(text).tolist(),
                    }
                )

            if payload:
                self.collection.insert_many(payload)
                print(f"✅ Loaded {len(payload)} chunks.")

    def probe_search(self, query):
        """Demonstrates a simple Vector Search (Similarity)."""
        query_vector = self.embed_model.encode(query).tolist()

        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "embedding",
                    "queryVector": query_vector,
                    "numCandidates": 10,
                    "limit": 3,
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "text": 1,
                    "file_name": 1,
                    "score": {"$meta": "vectorSearchScore"},
                }
            },
        ]

        results = list(self.collection.aggregate(pipeline))
        print(f"\n🔍 Top results for: '{query}'")
        for res in results:
            print(
                f"[{res['file_name']}] Score: {res['score']:.4f}\nText: {res['text']}\n"
            )

    def check_index(self):
        print("\n--- Atlas Search & Vector Indexes ---")
        search_indexes = self.collection.list_search_indexes()
        for index in search_indexes:
            print(f"Name: {index.get('name')}")
            print(f"Type: {index.get('type', 'search')}")  # search or vectorSearch
            print(f"Status: {index.get('status')}")
            print(f"Definition: {index.get('latestDefinition')}")
            print("-" * 20)


# --- EXECUTION ---
if __name__ == "__main__":
    # Ensure data dir exists
    Path(DATA_DIR).mkdir(exist_ok=True)

    pipeline = RAGPipeline()
    pipeline.setup_database()
    pipeline.ingest_data()

    # Give the index a moment to initialize if it's the first run
    print("\nWaiting 5 seconds for index sync...")
    time.sleep(5)

    pipeline.check_index()
    # Test Query
    pipeline.probe_search("What is the main topic of the uploaded documents?")
