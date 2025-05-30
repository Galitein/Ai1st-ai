import os
import logging

import torch

from txtai import Embeddings
from txtai.pipeline import Similarity

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("google_oauth.log"),
        logging.StreamHandler()
    ]
)

# Configuration
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
INDEX_DIR = "index"
# Check if CUDA is available and set the device
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
logging.info(f"Using device: {device}")
similarity = Similarity("valhalla/distilbart-mnli-12-3")

def search(index, query, limit=20):
    """
    Searches the index for the given query.

    Args:
        index (Embeddings): The txtai index object.
        query (str): The search query.
        limit (int): The maximum number of results to return.

    Returns:
        list: A list of tuples containing the score and text of the results.
    """
    try:
        results = index.search(query, limit=limit)
        return [(result["score"], result["text"]) for result in results]
    except Exception as e:
        logging.error(f"Error during search: {e}")
        return []

def ranksearch(index, query, limit=20):
    """
    Ranks the search results using a similarity pipeline.

    Args:
        index (Embeddings): The txtai index object.
        query (str): The search query.
        limit (int): The maximum number of results to return.

    Returns:
        list: A list of ranked results.
    """
    try:
        results = [text for _, text in search(index, query, limit)]
        return [results[x] for x, _ in similarity(query, results)]
    except Exception as e:
        logging.error(f"Error during rank search: {e}")
        return []

def load_index(index_dir=INDEX_DIR, model=MODEL_NAME):
    """
    Loads the txtai index from the specified directory.

    Args:
        index_dir (str): The directory where the index is stored.
        model (str): The model path for embeddings.

    Returns:
        Embeddings: The loaded txtai index object.
    """
    try:
        index = Embeddings({"path": model, "content": True, "metric": "cosine"})
        index.load(index_dir)
        logging.info(f"Index loaded from {index_dir}")
        return index
    except Exception as e:
        logging.error(f"Error loading index: {e}")
        return None

# import torch
# print(torch.cuda.is_available())  # Should return True
# print(torch.cuda.get_device_name(0))