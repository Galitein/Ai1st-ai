import os
from txtai.embeddings import Embeddings
from txtai.pipeline import Segmentation

# ----------- CONFIG -----------
DATA_DIR = "data"
INDEX_DIR = "index"
CHUNK_BY = "paragraphs"  # or "sentences"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
# ------------------------------

# Step 1: Load and chunk documents
def load_and_chunk_documents(data_dir):
    splitter = Segmentation({CHUNK_BY: True})
    documents = []

    for filename in os.listdir(data_dir):
        if filename.endswith(".txt"):
            path = os.path.join(data_dir, filename)
            with open(path, "r", encoding="utf-8") as file:
                text = file.read()
                chunks = splitter(text)
                for i, chunk in enumerate(chunks):
                    doc_id = f"{filename}_chunk{i}"
                    documents.append((doc_id, chunk))
    return documents

# Step 2: Create and populate txtai index
def build_index(documents, model=MODEL_NAME, save_path=INDEX_DIR):
    index = Embeddings({"path": model})
    for uid, chunk in documents:
        index.index(uid, chunk)
    index.save(save_path)
    return index

# Step 3: Load index and query
def query_index(index, query, topk=3):
    results = index.search(query, topk)
    return [(uid, score, index[uid]) for uid, score in results]

if __name__ == "__main__":
    os.makedirs(INDEX_DIR, exist_ok=True)

    # Load and chunk
    docs = load_and_chunk_documents(DATA_DIR)
    print(f"✅ Loaded and chunked {len(docs)} total chunks from documents.")

    # Build index
    index = build_index(docs)
    print(f"✅ Embedding index built and saved.")

    # Load and test query
    index.load(INDEX_DIR)
    query = input("🔍 Enter your query: ")
    results = query_index(index, query)

    print("\n🔎 Top matching chunks:")
    for uid, score, text in results:
        print(f"\n📄 {uid} (score={score:.4f})\n{text}\n{'-'*80}")
