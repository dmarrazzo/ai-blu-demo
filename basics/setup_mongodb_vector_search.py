from pymongo import MongoClient
from pymongo.errors import CollectionInvalid
from pymongo.operations import SearchIndexModel
from dotenv import load_dotenv
import os

# 1. Load configuration
# load_dotenv() will look for a .env file. 
# In K8s, these are already in os.environ, so this remains safe.
load_dotenv()

# --- Configuration ---
CONNECTION_STRING = os.getenv("CONNECTION_STRING")
DB_NAME = os.getenv("DB_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")
INDEX_NAME = os.getenv("INDEX_NAME")

def setup_mongodb_vector_search():
    # 1. Initialize Client
    client = MongoClient(CONNECTION_STRING)
    db = client[DB_NAME]
    
    # 2. Ensure Collection Exists
    # In MongoDB, collections are created automatically when data is inserted,
    # but we can explicitly access it here.
    try:
        db.create_collection(COLLECTION_NAME)
        print(f"✨ Created new collection: {COLLECTION_NAME}")
    except CollectionInvalid:
        # This error triggers if the collection already exists
        print(f"✅ Collection {COLLECTION_NAME} already exists.")

    collection = db[COLLECTION_NAME]

    # 3. Define the Vector Search Index
    # We define the field name (e.g., 'embedding'), dimensions, and similarity function
    search_index_definition = {
        "fields": [
            {
                "type": "vector",
                "path": "embedding",
                "numDimensions": 1536, # Standard for OpenAI text-embedding-3-small
                "similarity": "cosine" # Options: "cosine", "euclidean", "dotProduct"
            }
        ]
    }

    # 4. Create the Index Model
    index_model = SearchIndexModel(
        definition=search_index_definition,
        name=INDEX_NAME,
        type="vectorSearch"
    )

    try:
        # 5. Execute Creation
        print(f"🚀 Creating vector search index '{INDEX_NAME}'...")
        result = collection.create_search_index(model=index_model)
        print(f"✨ Index creation initiated: {result}")
        
        # Note: Indexing takes a few minutes on Atlas to become 'READY'
        print("ℹ️ Note: It may take a few minutes for the index to be queryable.")
        
    except Exception as e:
        print(f"❌ Error creating index: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    setup_mongodb_vector_search()