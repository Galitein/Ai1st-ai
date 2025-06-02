import os
import logging
from dotenv import load_dotenv

import torch

from txtai import Embeddings
from txtai.pipeline import Similarity

load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("vector_search.log"),  # Updated log file name
        logging.StreamHandler()
    ]
)

# Configuration
MODEL_NAME = os.getenv("MODEL_NAME")
INDEX_DIR = os.getenv("INDEX_DIR")
SIMILARITY_MODEL = os.getenv("SIMILARITY_MODEL")

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
logging.info(f"Using device: {device}")
similarity = Similarity(SIMILARITY_MODEL)

# def search(index, query, limit=10):
#     """
#     Searches the index for the given query.

#     Args:
#         index (Embeddings): The txtai index object.
#         query (str): The search query.
#         limit (int): The maximum number of results to return.

#     Returns:
#         list: A list of tuples containing the score and text of the results.
#     """
#     try:
#         results = index.search(query, limit=limit)
#         return [(result["score"], result["text"]) for result in results]
#     except Exception as e:
#         logging.error(f"Error during search: {e}")
#         return []

# def ranksearch(index, query, limit=10):
#     """
#     Ranks the search results using a similarity pipeline.

#     Args:
#         index (Embeddings): The txtai index object.
#         query (str): The search query.
#         limit (int): The maximum number of results to return.

#     Returns:
#         list: A list of ranked results.
#     """
#     try:
#         results = [text for _, text in search(index, query, limit)]
#         return [results[x] for x, _ in similarity(query, results)]
#     except Exception as e:
#         logging.error(f"Error during rank search: {e}")
#         return []

def search(index, query, limit=10, similarity_threshold=0.5):
    """
    Searches the index for the given query and filters results based on a similarity threshold.

    Args:
        index (Embeddings): The txtai index object.
        query (str): The search query.
        limit (int): The maximum number of results to return.
        similarity_threshold (float): The minimum similarity score to include a result.

    Returns:
        list: A list of tuples containing the score and text of the results.
    """
    try:
        results = index.search(query, limit=limit)
        # Filter results based on the similarity threshold
        filtered_results = [
            (result["score"], result["text"]) for result in results if result["score"] >= similarity_threshold
        ]
        logging.info(f"Found {filtered_results} results after filtering with threshold {similarity_threshold}.")

        return {'status':True, 'filtered_results':filtered_results}
    except Exception as e:
        logging.error(f"Error during search: {e}")
        return {'status':False, 'filtered_results':[]}

def ranksearch(index, query, limit=10, similarity_threshold=0.5):
    """
    Ranks the search results using a similarity pipeline and filters results based on a similarity threshold.

    Args:
        index (Embeddings): The txtai index object.
        query (str): The search query.
        limit (int): The maximum number of results to return.
        similarity_threshold (float): The minimum similarity score to include a result.

    Returns:
        list: A list of ranked results.
    """
    try:
        # Perform the initial search with the similarity threshold
        search_results = search(index, query, limit, similarity_threshold)
        if search_results.get('status') and len(search_results.get('filtered_results')) > 0:
            results = [(score, text) for score, text in search_results.get('filtered_results')]
            texts = [text for _, text in results]
            # Rank the filtered results using the similarity pipeline
            ranked_results = [texts[x] for x, _ in similarity(query, texts)]
            return {'status':True, 'ranked_results':ranked_results}
        else:
            logging.info("No results found after applying similarity threshold.")
            return {'status':True, 'ranked_results':[]}
    except Exception as e:
        logging.error(f"Error during rank search: {e}")
        return {'status':False, 'ranked_results':[]}

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