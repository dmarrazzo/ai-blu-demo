import os
from pymongo import MongoClient

# --- CONFIGURATION ---
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/?directConnection=true")
DB_NAME = "knowledge_base"
COLLECTION_NAME = "documents"

def diagnose_db():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

    print(f"--- 🩺 Database Diagnostics ---")
    
    # 1. Check Document Count
    count = collection.count_documents({})
    print(f"📊 Total documents in [{DB_NAME}.{COLLECTION_NAME}]: {count}")

    if count == 0:
        print("❌ ERROR: The collection is empty. Check your 'data' folder and re-run ingestion.")
        return

    # 2. Peek at 2 Chunks
    print("\n📄 Peeking at the first 2 documents:")
    chunks = list(collection.find().limit(2))
    for i, doc in enumerate(chunks):
        print(f"\n--- Chunk {i+1} ---")
        print(f"File: {doc.get('file_name', 'Unknown')}")
        # Show first 100 chars of text
        print(f"Text Snippet: {doc.get('text', 'NO TEXT FIELD FOUND')[:100]}...")
        # Check if embedding exists
        has_vector = "embedding" in doc
        vector_len = len(doc['embedding']) if has_vector else 0
        print(f"Vector Present: {has_vector} (Size: {vector_len})")

    # 3. Check Index Status (Crucial for $vectorSearch)
    print("\n⚙️ Checking Search Index Status...")
    try:
        indexes = list(collection.list_search_indexes())
        if not indexes:
            print("❌ ERROR: No Search Indexes found. Vector search will fail.")
        else:
            for idx in indexes:
                name = idx.get("name")
                status = idx.get("status")
                print(f"Index: {name} | Status: {status}")
                if status != "STEADY":
                    print(f"   ⚠️  Warning: Index is {status}. Wait until it is STEADY.")
    except Exception as e:
        print(f"❌ Could not retrieve index status: {e}")

if __name__ == "__main__":
    diagnose_db()