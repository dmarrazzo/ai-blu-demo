import os
import time
import io
from pathlib import Path
from typing import List

import boto3

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions

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
DB_NAME = os.getenv("DB_NAME", "knowledge_base")
COLLECTION_NAME = "documents"

# S3 Configuration
S3_BUCKET = os.getenv("AWS_S3_BUCKET")
S3_PREFIX = os.getenv("S3_PREFIX", "")  # e.g., "uploads/"
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
# Get the endpoint from env, default to None for real AWS
S3_ENDPOINT = os.getenv("AWS_S3_ENDPOINT")


class RAGPipeline:
    def __init__(self):
        print(f"--- Initializing Pipeline with {EMBEDDING_MODEL} ---")

        self.embed_model = SentenceTransformer(EMBEDDING_MODEL)
        self.client = MongoClient(MONGO_URI)
        self.collection = self.client[DB_NAME][COLLECTION_NAME]

        # 1. PDF pipeline options (e.g. disable OCR for text-only PDFs)
        pdf_options = PdfPipelineOptions(do_ocr=False)

        # 2. Initialize the converter: format_options must map to FormatOption
        #    (e.g. PdfFormatOption), not to PdfPipelineOptions directly.
        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options)
            }
        )

        # Initialize S3 client only if bucket is provided
        self.s3_client = (
            boto3.client(
                "s3",
                aws_access_key_id=AWS_ACCESS_KEY,
                aws_secret_access_key=AWS_SECRET_KEY,
                region_name=AWS_REGION,
                endpoint_url=S3_ENDPOINT,  # <--- CRITICAL for MinIO
            )
            if S3_BUCKET
            else None
        )

    def ensure_collection(self):
        """Ensure the collection exists before creating indexes."""
        db = self.client[DB_NAME]
        if COLLECTION_NAME not in db.list_collection_names():
            db.create_collection(COLLECTION_NAME)
            print(f"📁 Created collection '{COLLECTION_NAME}'.")

    def create_indexes(self):
        """Creates the necessary Search Indexes for BM25 and Vector Search."""
        self.ensure_collection()
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

    def ingest_from_s3(self):
        """Downloads PDFs from S3 and processes them."""
        if not self.s3_client or not S3_BUCKET:
            print("❌ S3 Bucket not configured. Skipping S3 ingestion.")
            return

        print(f"☁️  Fetching files from s3://{S3_BUCKET}/{S3_PREFIX}...")

        # List objects in bucket
        response = self.s3_client.list_objects_v2(Bucket=S3_BUCKET, Prefix=S3_PREFIX)

        if "Contents" not in response:
            print("⚠️ No files found in S3 bucket.")
            return

        # Clean existing data before fresh ingest
        self.collection.delete_many({})

        for obj in response["Contents"]:
            key = obj["Key"]
            if not key.lower().endswith(".pdf"):
                continue

            t0 = time.perf_counter()
            print(f"📄 Processing S3 file: {key}...")

            # Download file into memory
            file_stream = io.BytesIO()
            self.s3_client.download_fileobj(S3_BUCKET, key, file_stream)
            file_stream.seek(0)

            # Docling can accept bytes/streams depending on version,
            # but writing to a temp local file is most compatible
            temp_path = Path(f"temp_{Path(key).name}")
            with open(temp_path, "wb") as f:
                f.write(file_stream.read())

            self._process_and_store(temp_path, key)

            # Cleanup temp file
            if temp_path.exists():
                temp_path.unlink()

            elapsed = time.perf_counter() - t0
            print(f"   ⏱️  {key}: {elapsed:.2f}s")

    def _process_and_store(self, file_path: Path, original_name: str):
        """Internal helper to convert, chunk, and save to MongoDB."""
        result = self.converter.convert(str(file_path))
        markdown_content = result.document.export_to_markdown()
        chunks = self.chunk_text(markdown_content)

        if not chunks:
            return

        # Vectorize all chunks in one batch for speed
        embeddings = self.embed_model.encode(chunks).tolist()

        payload = [
            {
                "file_name": original_name,
                "chunk_id": i,
                "text": text,
                "embedding": embeddings[i],
                "ingested_at": time.time(),
            }
            for i, text in enumerate(chunks)
        ]

        self.collection.insert_many(payload)
        print(f"✅ Loaded {len(payload)} chunks from {original_name}.")

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
        pdf_files = list(Path(DATA_DIR).glob("*.pdf"))
        if not pdf_files:
            return

        self.collection.delete_many({})

        for pdf in pdf_files:
            t0 = time.perf_counter()
            print(f"📄 Processing {pdf.name} (Text-only)...")
            result = self.converter.convert(str(pdf))
            markdown_content = result.document.export_to_markdown()

            chunks = self.chunk_text(markdown_content, max_chars=800, overlap=150)

            if chunks:
                # Batch encode for massive speedup
                embeddings = self.embed_model.encode(chunks).tolist()
                payload = [
                    {
                        "file_name": pdf.name,
                        "chunk_id": i,
                        "text": text,
                        "embedding": embeddings[i],
                    }
                    for i, text in enumerate(chunks)
                ]
                self.collection.insert_many(payload)
                elapsed = time.perf_counter() - t0
                print(f"✅ Loaded {len(payload)} chunks in {elapsed:.2f}s.")
            else:
                elapsed = time.perf_counter() - t0
                print(f"   ⏱️  {pdf.name}: {elapsed:.2f}s (no chunks)")

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
    pipeline.create_indexes()

    # Decide between S3 or Local based on ENV
    if S3_BUCKET:
        pipeline.ingest_from_s3()
    else:
        pipeline.ingest_data()


    # Give the index a moment to initialize if it's the first run
    print("\nWaiting 5 seconds for index sync...")
    time.sleep(5)

    pipeline.check_index()
    # Test Query
    pipeline.probe_search("What is the main topic of the uploaded documents?")
